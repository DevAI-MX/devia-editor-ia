#!/bin/bash
source "$(dirname "$0")/entorno.sh"
# cortar.sh — corte de silencios en UNA pasada de ffmpeg + transcript por palabra.
# Salida: <nombre>_cut.mp4 (una sola pieza) + <nombre>.srt + <nombre>_cortes.json
#
# Por que una sola pieza y no N clips en HyperFrames:
#   medido en esta maquina (M5, 1080x1920@30) -> 1 clip de video: 18s de render por 12s de salida.
#   3 clips del mismo source: 99s de render por 9s de salida (11x mas fresco por segundo).
#   El corte se resuelve aqui, en ffmpeg, que va a ~5x tiempo real.
#
# Uso: bin/cortar.sh input/video.mp4 [umbral_dB] [dur_min_silencio]

set -euo pipefail

FFMPEG=ffmpeg
FFPROBE=ffprobe
RAIZ_BIN="$KIT_RAIZ/bin"

SRC="${1:?falta el video de entrada}"
DB="${2:-$("$PY" "$RAIZ_BIN/leer.py" cortes.silencio_db -32)}"
MINSIL="${3:-$("$PY" "$RAIZ_BIN/leer.py" cortes.silencio_min 0.28)}"
PAD=$("$PY" "$RAIZ_BIN/leer.py" cortes.aire 0.10)          # aire que se deja a cada lado del habla
MINSEG=$("$PY" "$RAIZ_BIN/leer.py" cortes.segmento_min 0.20)       # segmentos mas cortos que esto se descartan

[ -f "$SRC" ] || { echo "No existe: $SRC" >&2; exit 1; }

DIR=$(ruta_absoluta "$(dirname "$SRC")")
BASE=$(basename "${SRC%.*}")
OUT_DIR="${OUT_DIR:-$DIR}"
mkdir -p "$OUT_DIR"

DUR=$($FFPROBE -v error -show_entries format=duration -of csv=p=0 "$SRC")
W=$($FFPROBE -v error -select_streams v:0 -show_entries stream=width -of csv=p=0 "$SRC")
H=$($FFPROBE -v error -select_streams v:0 -show_entries stream=height -of csv=p=0 "$SRC")
FPS=$($FFPROBE -v error -select_streams v:0 -show_entries stream=r_frame_rate -of csv=p=0 "$SRC" | awk -F/ '{printf "%.3f", $1/$2}')
echo "fuente: ${W}x${H} @ ${FPS}fps  ${DUR}s"

# --- 1. mapa de silencios -------------------------------------------------
# El umbral es ABSOLUTO, asi que primero se normaliza una copia solo para analizar.
# Sin esto, en material grabado bajo (este venia a -39.9 LUFS) el umbral cae por
# encima de parte del habla y el corte entra DENTRO de las palabras: el transcript
# sale lleno de silabas partidas.
echo "normalizando para analizar (el umbral de silencio es absoluto)..."
$FFMPEG -v error -i "$SRC" -vn -af "loudnorm=I=-16:TP=-1.5:LRA=11" \
  -ar 48000 -ac 1 "$OUT_DIR/${BASE}_analisis.wav" -y

echo "detectando silencios (${DB}dB, >${MINSIL}s)..."
$FFMPEG -i "$OUT_DIR/${BASE}_analisis.wav" -af "silencedetect=noise=${DB}dB:d=${MINSIL}" \
  -f null - 2>&1 | grep -E "silence_(start|end)" > "$OUT_DIR/${BASE}_sil.txt" || true

# --- 2. segmentos de habla -> expresion select ----------------------------
"$PY" - "$OUT_DIR/${BASE}_sil.txt" "$DUR" "$PAD" "$MINSEG" "$OUT_DIR/${BASE}_cortes.json" <<'PY' > "$OUT_DIR/${BASE}_select.txt"
import sys, json, re
sil_file, dur, pad, minseg, json_out = sys.argv[1], float(sys.argv[2]), float(sys.argv[3]), float(sys.argv[4]), sys.argv[5]
starts, ends = [], []
for line in open(sil_file):
    m = re.search(r'silence_start:\s*([\d.]+)', line)
    if m: starts.append(float(m.group(1)))
    m = re.search(r'silence_end:\s*([\d.]+)', line)
    if m: ends.append(float(m.group(1)))
sil = []
for i, s in enumerate(starts):
    e = ends[i] if i < len(ends) else dur
    sil.append((s, e))
keep, cur = [], 0.0
for s, e in sil:
    a, b = cur, min(s + pad, dur)
    if b - a >= minseg: keep.append([round(a, 3), round(b, 3)])
    cur = max(0.0, e - pad)
if dur - cur >= minseg: keep.append([round(cur, 3), round(dur, 3)])
if not keep: keep = [[0.0, round(dur, 3)]]

# los fragmentos cortos los resuelve bin/retomas.py, que si sabe lo que se dice
json.dump({"keep": keep, "src_duration": dur,
           "out_duration": round(sum(b - a for a, b in keep), 3),
           "segments": len(keep)}, open(json_out, "w"), indent=1)
print("+".join(f"between(t,{a},{b})" for a, b in keep))
PY

# --- 2b. retomas: hay que saber QUE se dice antes de decidir los cortes ------
echo "revisando fragmentos cortos (retomas)..."
"$PY" "$RAIZ_BIN/retomas.py" "$OUT_DIR/${BASE}_cortes.json" \
    "$SRC" > "$OUT_DIR/${BASE}_cortes2.json" \
  && mv -f "$OUT_DIR/${BASE}_cortes2.json" "$OUT_DIR/${BASE}_cortes.json"
# el video tiene que empezar donde empieza a hablar
"$PY" "$RAIZ_BIN/arranque.py" "$OUT_DIR/${BASE}_cortes.json" \
    "$OUT_DIR/${BASE}_analisis.wav" > "$OUT_DIR/${BASE}_cortes3.json" \
  && mv -f "$OUT_DIR/${BASE}_cortes3.json" "$OUT_DIR/${BASE}_cortes.json"

# --- 2c. cadencia: que no pare de hablar --------------------------------
# El corte por silencio de arriba usa un umbral ABSOLUTO y se le escapa casi
# todo: medido sobre el corte ya hecho quedaban 29 silencios de mas de 0.3s
# sumando 14 segundos, con picos de 0.88s. Aqui se vuelve a mirar, pero con el
# umbral RELATIVO a su propia voz, sobre el audio del corte provisional. Los
# dos recortes se aplican juntos en una sola pasada: el video se codifica una vez.
echo "midiendo la cadencia (silencios que quedan dentro)..."
SEL1=$("$PY" -c "
import json
d=json.load(open('$OUT_DIR/${BASE}_cortes.json'))
print('+'.join('between(t,%s,%s)'%(a,b) for a,b in d['keep']))")
$FFMPEG -v error -i "$SRC" -vn -af "aselect='${SEL1}',asetpts=N/SR/TB" \
  -ac 1 -ar 16000 "$OUT_DIR/${BASE}_cad.wav" -y
"$PY" "$RAIZ_BIN/cadencia.py" "$OUT_DIR/${BASE}_cad.wav" \
    "$OUT_DIR/${BASE}_cortes.json" > "$OUT_DIR/${BASE}_cortes4.json" \
  && mv -f "$OUT_DIR/${BASE}_cortes4.json" "$OUT_DIR/${BASE}_cortes.json"
rm -f "$OUT_DIR/${BASE}_cad.wav"

SELECT=$("$PY" -c "
import json
d=json.load(open('$OUT_DIR/${BASE}_cortes.json'))
print('+'.join('between(t,%s,%s)'%(a,b) for a,b in d['keep']))")
"$PY" -c "
import json;d=json.load(open('$OUT_DIR/${BASE}_cortes.json'))
print('tras limpiar retomas: %d segmentos, %.1fs'%(d['segments'],d['out_duration']))"
"$PY" -c "
import json;d=json.load(open('$OUT_DIR/${BASE}_cortes.json'))
print('segmentos: %d  %.1fs -> %.1fs  (-%.1fs)'%(d['segments'],d['src_duration'],d['out_duration'],d['src_duration']-d['out_duration']))
"

# --- 3. corte en una pasada ----------------------------------------------
# El grado de color va AQUI, en la misma pasada del corte: el video se codifica una
# sola vez y no se pierde calidad en una segunda generacion. La curva baja las sombras
# y deja los altos, que es lo que oscurece el fondo sin apagarle la cara.
CURVA=$("$PY" "$RAIZ_BIN/leer.py" imagen.curva "")
SATU=$("$PY" "$RAIZ_BIN/leer.py" imagen.saturacion "")
VF="select='${SELECT}',setpts=N/FRAME_RATE/TB"
if [ -n "$CURVA" ]; then
  VF="$VF,curves=all='${CURVA}'"
  echo "  grado: curva de sombras ${CURVA}"
fi
if [ -n "$SATU" ]; then
  VF="$VF,eq=saturation=${SATU}"
  echo "  grado: saturacion ${SATU}"
fi
echo "cortando..."
$FFMPEG -v error -stats -i "$SRC" \
  -vf "$VF" \
  -af "aselect='${SELECT}',asetpts=N/SR/TB" \
  -c:v libx264 -preset veryfast -crf 18 -pix_fmt yuv420p \
  -g 30 -keyint_min 30 -sc_threshold 0 -movflags +faststart \
  -c:a pcm_s16le -ar 48000 \
  "$OUT_DIR/${BASE}_tmp.mov" -y

# --- 3b. limpieza de voz --------------------------------------------------
# DeepFilterNet3 separa voz de ruido con red neuronal: quita sala, aire y zumbido
# sin el sonido "bajo el agua" que deja un reductor de ruido clasico. Corre a ~50x
# tiempo real en esta maquina. Despues, EQ y nivel.
EQ_TURB_HZ=$("$PY" "$RAIZ_BIN/leer.py" audio.voz_eq.turbidez_hz 250)
EQ_TURB_DB=$("$PY" "$RAIZ_BIN/leer.py" audio.voz_eq.turbidez_db -2.5)
EQ_CAJA_HZ=$("$PY" "$RAIZ_BIN/leer.py" audio.voz_eq.caja_hz 430)
EQ_CAJA_DB=$("$PY" "$RAIZ_BIN/leer.py" audio.voz_eq.caja_db -2.0)
EQ_PRES_HZ=$("$PY" "$RAIZ_BIN/leer.py" audio.voz_eq.presencia_hz 3200)
EQ_PRES_DB=$("$PY" "$RAIZ_BIN/leer.py" audio.voz_eq.presencia_db 3.5)
EQ_AIRE_HZ=$("$PY" "$RAIZ_BIN/leer.py" audio.voz_eq.aire_hz 7500)
EQ_AIRE_DB=$("$PY" "$RAIZ_BIN/leer.py" audio.voz_eq.aire_db 2.5)
VOZ_LUFS=$("$PY" "$RAIZ_BIN/leer.py" audio.voz_lufs -14)
# La compresion de la voz se afloja o se aprieta desde la configuracion. Con ratio 3
# y makeup 2 la voz salia saturada: la dinamica se aplasta y se oye "apretada".
COMP_UMBRAL=$("$PY" "$RAIZ_BIN/leer.py" audio.voz_comp.umbral_db -20)
COMP_RATIO=$("$PY" "$RAIZ_BIN/leer.py" audio.voz_comp.ratio 3)
COMP_MAKEUP=$("$PY" "$RAIZ_BIN/leer.py" audio.voz_comp.makeup 2)
echo "limpiando la voz (DeepFilterNet3)..."
$FFMPEG -v error -i "$OUT_DIR/${BASE}_tmp.mov" -vn -ac 1 -ar 48000 "$OUT_DIR/${BASE}_voz.wav" -y
# --pf es el post-filtro: aprieta un poco mas los tramos mas ruidosos. Medido sobre
# este material, baja el piso de ruido entre palabras de -62.9 a -66.8 dB (4 dB de
# regalo) sin tocar la inteligibilidad: whisper transcribe exactamente igual con y
# sin el. Una segunda pasada de DeepFilterNet solo da 1.5 dB mas y no compensa el
# riesgo de artefactos.
if uvx --python 3.11 --from deepfilternet --with "torch==2.0.1" --with "torchaudio==2.0.2" \
     deepFilter "$OUT_DIR/${BASE}_voz.wav" --pf -o "$OUT_DIR/dfn" >/dev/null 2>&1; then
  LIMPIA="$OUT_DIR/dfn/${BASE}_voz_DeepFilterNet3_pf.wav"
  [ -f "$LIMPIA" ] || LIMPIA="$OUT_DIR/dfn/${BASE}_voz_DeepFilterNet3.wav"
  echo "  voz limpiada con DeepFilterNet3"
else
  LIMPIA="$OUT_DIR/${BASE}_voz.wav"
  echo "  AVISO: DeepFilterNet no disponible, se sigue sin separacion neuronal" >&2
fi

# EQ y nivel: paso alto, deesser, compresion suave y loudnorm. La voz manda.
$FFMPEG -v error -i "$LIMPIA" \
  -af "highpass=f=95,\
equalizer=f=${EQ_TURB_HZ}:t=q:w=1.0:g=${EQ_TURB_DB},\
equalizer=f=${EQ_CAJA_HZ}:t=q:w=1.4:g=${EQ_CAJA_DB},\
equalizer=f=${EQ_PRES_HZ}:t=q:w=1.2:g=${EQ_PRES_DB},\
equalizer=f=${EQ_AIRE_HZ}:t=q:w=1.0:g=${EQ_AIRE_DB},\
deesser=i=0.45:m=0.5:f=0.5,\
acompressor=threshold=${COMP_UMBRAL}dB:ratio=${COMP_RATIO}:attack=12:release=220:makeup=${COMP_MAKEUP},\
loudnorm=I=${VOZ_LUFS}:TP=-1.5:LRA=8" \
  -ar 48000 -ac 1 "$OUT_DIR/${BASE}_voz_ok.wav" -y

$FFMPEG -v error -i "$OUT_DIR/${BASE}_tmp.mov" -i "$OUT_DIR/${BASE}_voz_ok.wav" \
  -map 0:v -map 1:a -c:v copy -c:a aac -b:a 192k -shortest \
  "$OUT_DIR/${BASE}_cut.mp4" -y
rm -rf "$OUT_DIR/${BASE}_tmp.mov" "$OUT_DIR/${BASE}_voz.wav" "$OUT_DIR/${BASE}_voz_ok.wav" "$OUT_DIR/dfn"

# --- 4. transcript por palabra sobre el YA CORTADO ------------------------
# (transcribir despues del corte evita reajustar timestamps: es la fuente de verdad del render)
echo "transcribiendo (whisper large-v3, es)..."
"$PY" "$RAIZ_BIN/transcriptor.py" "$OUT_DIR/${BASE}_cut.mp4" --output-dir "$OUT_DIR" >/dev/null
mv -f "$OUT_DIR/${BASE}_cut.srt"  "$OUT_DIR/${BASE}.srt"
mv -f "$OUT_DIR/${BASE}_cut.json" "$OUT_DIR/${BASE}.json"
echo "transcript: $OUT_DIR/${BASE}.json (palabra) + ${BASE}.srt"

rm -f "$OUT_DIR/${BASE}_analisis.wav"
echo "listo: $OUT_DIR/${BASE}_cut.mp4"
