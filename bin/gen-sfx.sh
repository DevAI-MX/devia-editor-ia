#!/bin/bash
source "$(dirname "$0")/entorno.sh"
# Genera el kit de SFX de edicion con ffmpeg. Sin librerias, sin login, sin creditos.
# Uso: bash scripts/gen-sfx.sh [directorio-salida]
# Salida: WAV 48kHz estereo, normalizados a -3 dBFS de pico.

set -euo pipefail

FFMPEG_BIN="ffmpeg"
[ -x "$FFMPEG_BIN" ] || FFMPEG_BIN=$(which ffmpeg)

OUT="${1:-assets/sfx}"
mkdir -p "$OUT"
TMP=$(mktemp -d "$KIT_TMP/sfx.XXXXXX")
trap 'rm -rf "$TMP"' EXIT

# Normaliza el pico a -3 dBFS y deja el archivo final en $OUT/$1.wav
norm() {
  local name="$1"
  local src="$TMP/$name.raw.wav"
  local peak
  # volumedetect reporta en nivel info: NO usar -v error aqui o no imprime nada.
  peak=$("$FFMPEG_BIN" -hide_banner -v info -i "$src" -af volumedetect -f null - 2>&1 |
    grep max_volume | sed -E 's/.*max_volume: (-?[0-9.]+) dB.*/\1/')
  local gain
  gain=$("$PY" -c "print(round(-3.0 - float('${peak:-0}'), 2))")
  "$FFMPEG_BIN" -y -v error -i "$src" -af "volume=${gain}dB" -ac 2 -ar 48000 "$OUT/$name.wav"
  printf '%-22s %ss  (pico %s dB -> -3 dB)\n' "$name.wav" \
    "$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$OUT/$name.wav" | cut -c1-4)" "${peak:-?}"
}

gen() { "$FFMPEG_BIN" -y -v error "$@"; }

# --- WHOOSH: ruido rosa + flanger (da el movimiento de barrido) + envolvente ---
# corto (0.45s) para punches rapidos
gen -f lavfi -i "anoisesrc=d=0.45:c=pink:a=0.9:r=48000" \
  -af "highpass=f=350,lowpass=f=7000,flanger=delay=6:depth=4:speed=2.2,volume='0.02+1.3*pow(t/0.45,2.2)':eval=frame,afade=t=out:st=0.36:d=0.09" \
  "$TMP/whoosh-corto.raw.wav"
norm whoosh-corto

# largo (0.9s) para transiciones a b-roll
gen -f lavfi -i "anoisesrc=d=0.9:c=pink:a=0.9:r=48000" \
  -af "highpass=f=250,lowpass=f=8000,flanger=delay=8:depth=5:speed=1.1,volume='0.02+1.3*pow(t/0.9,2.4)':eval=frame,afade=t=out:st=0.72:d=0.18" \
  "$TMP/whoosh-largo.raw.wav"
norm whoosh-largo

# inverso (succion antes de un corte) = whoosh corto al reves
gen -i "$OUT/whoosh-corto.wav" -af "areverse" "$TMP/whoosh-inverso.raw.wav"
norm whoosh-inverso

# --- IMPACT: transitorio de ruido + cuerpo de sub con decaimiento exponencial ---
gen -f lavfi -i "sine=frequency=58:duration=0.6:r=48000" \
  -f lavfi -i "anoisesrc=d=0.6:c=white:a=0.8:r=48000" \
  -filter_complex "[0:a]volume='exp(-t*7)':eval=frame[sub];\
[1:a]highpass=f=1200,volume='exp(-t*45)':eval=frame[tr];\
[sub][tr]amix=inputs=2:weights=1 0.5:normalize=0" \
  "$TMP/impact.raw.wav"
norm impact

# --- SUB DROP: chirp descendente 180 -> 35 Hz en 0.9s ---
gen -f lavfi -i "aevalsrc='sin(2*PI*(180*t-80.5*t*t))':d=0.9:s=48000" \
  -af "volume='0.35+0.65*exp(-t*2)':eval=frame,afade=t=out:st=0.7:d=0.2,lowpass=f=200" \
  "$TMP/sub-drop.raw.wav"
norm sub-drop

# --- RISER: chirp ascendente 200 -> 4000 Hz + ruido, 1.5s, para reveals ---
gen -f lavfi -i "aevalsrc='sin(2*PI*(200*t+1266.7*t*t))':d=1.5:s=48000" \
  -f lavfi -i "anoisesrc=d=1.5:c=pink:a=0.6:r=48000" \
  -filter_complex "[0:a]volume='pow(t/1.5,1.8)':eval=frame[ch];\
[1:a]highpass=f=800,volume='0.5*pow(t/1.5,3)':eval=frame[ns];\
[ch][ns]amix=inputs=2:weights=1 0.7:normalize=0,afade=t=out:st=1.44:d=0.06" \
  "$TMP/riser.raw.wav"
norm riser

# --- CLICK: transitorio corto para marcar keywords en pantalla ---
gen -f lavfi -i "anoisesrc=d=0.06:c=white:a=0.9:r=48000" \
  -af "highpass=f=2500,volume='exp(-t*90)':eval=frame" \
  "$TMP/click.raw.wav"
norm click

# --- POP: aparicion de elemento (tono corto con decaimiento) ---
gen -f lavfi -i "aevalsrc='sin(2*PI*(900*t-1200*t*t))':d=0.12:s=48000" \
  -af "volume='exp(-t*28)':eval=frame" \
  "$TMP/pop.raw.wav"
norm pop

# --- TAPE STOP: tono que se frena, para cortar una idea en seco ---
# OJO: los params de lowpass/highpass NO aceptan expresiones con t (solo volume lo hace).
# El frenado lo da el chirp descendente, no un barrido de filtro.
gen -f lavfi -i "aevalsrc='sin(2*PI*(420*t-260*t*t))':d=0.7:s=48000" \
  -af "volume='exp(-t*1.6)':eval=frame,lowpass=f=2500,afade=t=out:st=0.6:d=0.1" \
  "$TMP/tape-stop.raw.wav"
norm tape-stop

# --- GLITCH: ruido troceado por una puerta cuadrada rapida ---
gen -f lavfi -i "anoisesrc=d=0.35:c=white:a=0.9:r=48000" \
  -af "highpass=f=600,lowpass=f=9000,volume='gt(sin(2*PI*28*t),0)*(0.3+0.7*exp(-t*4))':eval=frame" \
  "$TMP/glitch.raw.wav"
norm glitch

echo
echo "Kit generado en: $OUT"
