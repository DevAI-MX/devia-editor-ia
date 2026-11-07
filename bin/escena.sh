#!/bin/bash
source "$(dirname "$0")/entorno.sh"
# escena.sh — saca un trozo de una pelicula horizontal y lo deja vertical 1080x1920,
# listo para usarse como b-roll.
#
# Siempre a sangre (recorte 9:16), nunca en "carta" sobre fondo desenfocado: probado
# y descartado. Un 16:9 metido a lo ancho en un 9:16 ocupa el 32% de la altura y se
# ve diminuto, con mas relleno borroso que pelicula. A sangre llena la pantalla y se
# mete dentro del video.
#
# El precio de recortar es que se pierden los lados, y el sujeto casi nunca esta en
# el centro exacto. Por eso el DESVIO: mueve la ventana de recorte a izquierda o
# derecha. 0 = centro, -1 = pegado al borde izquierdo, 1 = al derecho.
#
# El ultimo argumento opcional LEVANTA la imagen. Una grabacion muy oscura esta
# rodado muy oscuro y calido; sobre el, la vineta y el velo del b-roll lo dejaban
# casi negro en un movil. Un 0.06 de brillo devuelve la cara sin lavar la peli.
#
# TODO clip sale etiquetado bt709 (SDR). El iPhone graba en HLG y esas etiquetas
# viajaban dentro del clip: bastaba UN b-roll en HLG para que HyperFrames detectara
# HDR en todo el proyecto, se fuera por la rama HDR (salida HEVC) y en esa rama los
# subtitulos quedaran POR DEBAJO del b-roll en el mp4 final. En la composicion se
# veian bien; solo fallaba el render, y solo en el video que llevaba clips del iPhone.
# Los pixeles no se tocan: HLG bien expuesto se lee correcto como bt709.
#
# Uso: bin/escena.sh <pelicula> <inicio> <duracion> <desvio -1..1> <salida.mp4> [luz]
set -euo pipefail
FFMPEG=ffmpeg
SRC="$1"; INI="$2"; DUR="$3"; DESV="${4:-0}"; OUT="$5"; LUZ="${6:-0}"

# El recorte se calcula sobre las medidas REALES de la fuente, no sobre 1920x1080.
# Asi el mismo script sirve para las peliculas (horizontales) y para el material de
# la marca, que viene en vertical, en 4K y en formatos raros como 4096x1728.
LEE=$(ffprobe -v error -select_streams v:0 \
        -show_entries stream=width,height -of csv=p=0:s=x "$SRC" | head -1)
X=$("$PY" -c "
w,h = [int(v) for v in '$LEE'.split('x')[:2]]
esc = max(1080/w, 1920/h)          # se escala hasta CUBRIR el 9:16
W = w*esc
libre = max(0.0, (W-1080)/2)       # cuanto se puede mover la ventana a cada lado
d = max(-1.0, min(1.0, float('$DESV')))
print(round(libre + libre*d, 1))")

$FFMPEG -nostdin -v error -ss "$INI" -t "$DUR" -i "$SRC" \
  -vf "scale=1080:1920:force_original_aspect_ratio=increase:flags=lanczos,crop=1080:1920:$X:0,eq=brightness=$LUZ:contrast=$("$PY" -c "print(round(1+float('$LUZ'),3))"):saturation=$("$PY" -c "print(round(1+float('$LUZ')*0.8,3))"),setsar=1,setparams=color_primaries=bt709:color_trc=bt709:colorspace=bt709:range=tv" -an \
  -r 30 -c:v libx264 -preset veryfast -crf 19 -pix_fmt yuv420p \
  -color_primaries bt709 -color_trc bt709 -colorspace bt709 \
  -g 15 -keyint_min 15 -sc_threshold 0 -movflags +faststart "$OUT" -y
echo "  $(basename "$OUT")  ${INI}s +${DUR}s  desvio $DESV  luz $LUZ"
