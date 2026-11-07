#!/bin/bash
# transcribir.sh: transcripcion por palabra, igual en cualquier equipo (ver bin/transcriptor.py).
# Acepta los argumentos de mlx_whisper. Ejemplo, para re-transcribir con el vocabulario del tema:
#   bash bin/transcribir.sh input/tramo.wav --initial-prompt "enfermeria, quirofano" --output-dir output
source "$(dirname "$0")/entorno.sh"
exec "$PY" "$KIT_RAIZ/bin/transcriptor.py" "$@"
