#!/bin/bash
source "$(dirname "$0")/entorno.sh"
# entregar.sh — render + masterizacion + triple revision + copia a la carpeta de salida.
# Uso: FORMATO=<formato> bin/entregar.sh <nombre> <transcript.json> <destino.mp4>
set -euo pipefail
RAIZ="$KIT_RAIZ"
N="$1"; TRANS="$2"; DEST="$3"; PROY="$RAIZ/output/$N"
ESTILO="${ESTILO:-$RAIZ/formatos/${FORMATO:-dinamico}.json}"
(cd "$PROY" && npx -y hyperframes@0.7.110 render -o final_raw.mp4 --workers 4 --sdr -q high --video-frame-format png > "$KIT_TMP/hf_render_$N.log" 2>&1) || { echo "ERROR: render de $N"; tail -3 "$KIT_TMP/hf_render_$N.log"; exit 1; }
# Master: la suma de voz+musica+sfx se normaliza a loudness de plataforma con techo de
# pico real. Es lo que evita la voz "saturada": sin esto el pico pasaba de 1.0 y recortaba.
LUFS=$("$PY" -c "import json;print((json.load(open('$ESTILO'))['audio'].get('master') or {}).get('lufs',-16))")
TP=$("$PY" -c "import json;print((json.load(open('$ESTILO'))['audio'].get('master') or {}).get('tp',-1.5))")
LRA=$("$PY" -c "import json;print((json.load(open('$ESTILO'))['audio'].get('master') or {}).get('lra',11))")
ffmpeg -v error -i "$PROY/final_raw.mp4" -c:v copy -af "loudnorm=I=${LUFS}:TP=${TP}:LRA=${LRA}" -c:a aac -b:a 192k "$PROY/final.mp4" -y
PICO=$(ffmpeg -v info -i "$PROY/final.mp4" -vn -af "loudnorm=I=${LUFS}:TP=${TP}:print_format=summary" -f null - 2>&1 | grep -E "Input Integrated|Input True Peak" | tr '\n' ' ')
echo "  master: $PICO"
FORMATO="${FORMATO:-dinamico}" "$PY" "$RAIZ/bin/revisar.py" "$PROY" "$TRANS" "$PROY/final.mp4" > "$KIT_TMP/rev_$N.log" 2>&1 || { echo "ERROR: revision de $N"; tail -5 "$KIT_TMP/rev_$N.log"; exit 1; }
tail -1 "$KIT_TMP/rev_$N.log"
mkdir -p "$(dirname "$DEST")" && cp "$PROY/final.mp4" "$DEST" && echo "  entregado: $DEST"
