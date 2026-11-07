#!/usr/bin/env python3
"""Genera el HTML del b-roll y copia el material al proyecto.

Por que en HTML y no por JS: HyperFrames compila los clips de video del HTML
inicial. Un <video class="clip"> creado por script despues de esa compilacion no
queda registrado en la linea de tiempo y se renderiza en negro. Comprobado.

El b-roll recibe el MISMO tratamiento que un grafico generado (push, desenfoque de
bordes, vineta y grano): eso es lo que hace que el material propio y los motion
graphics parezcan de la misma pieza.

Uso: bin/broll.py beats.json <raiz> <proyecto>   -> imprime el HTML
"""
import json, os, shutil, subprocess, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cfg import cfg

# El desenfoque de bordes se apaga por formato. En las referencias de impacto el
# material entra limpio y a sangre: el halo de los bordes lo delataba como pieza
# pegada encima del plano. Las capas van escritas en el HTML, asi que la decision se
# toma aqui y no en la plantilla.
CAPAS = ('<div class="grano"></div>' if cfg("broll.desenfoque", True) is False
         else '<div class="dof"></div><div class="vineta"></div><div class="grano"></div>')

beats = json.load(open(sys.argv[1])) if sys.argv[1] else {"stingers": []}
raiz, proy = sys.argv[2], sys.argv[3]

IMAGEN = (".png", ".jpg", ".jpeg", ".webp", ".avif")
html, faltan, n = [], [], 0

for b in beats.get("stingers", []):
    if b.get("tipo") != "broll":
        continue
    m = b.get("media")
    if not m:
        faltan.append("(stinger de b-roll sin campo 'media')"); continue
    orig = m if os.path.isabs(m) else os.path.join(raiz, "input", "broll", m)
    if not os.path.exists(orig):
        faltan.append(orig); continue
    os.makedirs(os.path.join(proy, "broll"), exist_ok=True)
    base = os.path.basename(m)
    shutil.copy2(orig, os.path.join(proy, "broll", base))

    # Un clip al que se le pide mas de lo que dura se queda CONGELADO en su ultimo
    # fotograma, y ademas HyperFrames avisa de cobertura insuficiente al renderizar.
    # Pasaba en seis de los veintiseis b-rolls: los ajustes de encaje y de solape
    # alargan la ventana sin mirar cuanto material hay.
    try:
        real = float(subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries",
             "format=duration", "-of", "csv=p=0", orig],
            capture_output=True, text=True).stdout.strip())
        if b["dur"] > real - 0.03:
            print(f"  {base} recortado a {real - 0.03:.2f}s: no da mas de si "
                  f"(se pedian {b['dur']:.2f}s)", file=sys.stderr)
            b["dur"] = round(real - 0.03, 3)
    except (ValueError, OSError):
        pass

    b["__bi"] = n
    if base.lower().endswith(IMAGEN):
        # la imagen tambien lleva id: el renderer descubre los medios por id
        # La imagen NO se declara como clip: comprobado que HyperFrames solo
        # gobierna <video> por la linea de tiempo; un <img class="clip"> no se
        # muestra. La revela GSAP junto con el contenedor.
        media = f'<img id="brolli-{n}" src="broll/{base}" alt="">'
    else:
        # el id es obligatorio: sin el, el renderer no descubre el elemento y el
        # video sale CONGELADO. 'hyperframes check' lo caza, pero mejor no llegar ahi.
        # el video lleva su propia temporizacion (el check la exige) ademas de la
        # del contenedor: uno gobierna la reproduccion, el otro la visibilidad
        media = (f'<video id="brollv-{n}" class="clip" src="broll/{base}" muted playsinline '
                 f'data-start="{b["at"]}" data-media-start="{b.get("media_start", 0)}" '
                 f'data-duration="{b["dur"]}" data-volume="{b.get("volumen", 0)}" '
                 f'data-track-index="1"></video>')
    html.append(
        # sin data-track-index en el contenedor: los stingers dinamicos tampoco
        # lo llevan, y con el HyperFrames trata el div como un clip sin
        # data-start y no lo muestra. El <video> de dentro si lo lleva.
        # El contenedor NO lleva temporizacion: un <video> temporizado dentro de
        # otro elemento temporizado se congela en el render (lo caza el check).
        # El medio es el clip; el contenedor solo agrupa las capas de tratamiento.
        # La clase 'broll' lo manda a la capa de abajo: el b-roll es fondo y los
        # subtitulos siguen corriendo por encima. Sin ella los tapaba en los diez
        # tramos del video (el orden del DOM no bastaba).
        f'      <div class="stinger broll" id="broll-{n}">\n'
        f'        <div class="grafico" data-layout-allow-overflow>\n'
        f'          <div class="broll">{media}</div>\n'
        f'        </div>\n'
        f'        {CAPAS}\n'
        f'      </div>')
    print(f"  b-roll: {base}", file=sys.stderr)
    n += 1

# Los emojis de las FICHAS tambien viajan al proyecto: se referencian desde el
# stinger, no desde props, asi que nadie mas los copia.
emojis = sorted({b["emoji"] for b in beats.get("stingers", [])
                 if b.get("tipo") == "ficha" and b.get("emoji")})
if emojis:
    dst = os.path.join(proy, "props", "emoji")
    os.makedirs(dst, exist_ok=True)
    for e in emojis:
        o = os.path.join(raiz, "input", "props", "emoji", e)
        if os.path.exists(o):
            shutil.copy2(o, os.path.join(dst, e))
        else:
            faltan.append(o)
    print(f"  fichas: {len(emojis)} emojis ({', '.join(emojis)})", file=sys.stderr)

# Y las FOTOS de las fichas (la cara de un cliente cuando el guion lo nombra).
fotos = sorted({b["foto"] for b in beats.get("stingers", [])
                if b.get("tipo") == "ficha" and b.get("foto")})
if fotos:
    dst = os.path.join(proy, "props", "fotos")
    os.makedirs(dst, exist_ok=True)
    for f in fotos:
        o = os.path.join(raiz, "input", "props", "fotos", f)
        if os.path.exists(o):
            shutil.copy2(o, os.path.join(dst, f))
        else:
            faltan.append(o)
    print(f"  fichas: {len(fotos)} fotos ({', '.join(fotos)})", file=sys.stderr)

if faltan:
    print("ERROR: falta material de b-roll:", file=sys.stderr)
    for f in faltan:
        print(f"  {f}", file=sys.stderr)
    sys.exit(1)

# se reescribe beats.json con el indice __bi para que el JS encuentre cada bloque
if n:
    json.dump(beats, open(sys.argv[1], "w"), ensure_ascii=False, indent=1)
print("\n".join(html))
