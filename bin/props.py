#!/usr/bin/env python3
"""Recortes y tarjetas PNG: las imagenes que ponen EN ESCENA lo que se esta diciendo.

Es la pieza que separa las referencias de un talking head normal. Ahi no hay solo
b-roll a pantalla completa: hay recortes con fondo transparente pegados junto al que
habla (un grupo de amigos, una cara, un objeto) y tarjetas de esquina redondeada con
una foto o una captura. Entran en el primer segundo, se quedan varios y crecen
despacio. Nunca llevan desenfoque de bordes ni velo: son piezas limpias.

Van en `props` dentro de beats.json:

  {"at": 0.0, "dur": 3.4, "archivo": "amigos.png", "tipo": "recorte",
   "sitio": "abajo-izq", "alto": 0.46}

  tipo   recorte  PNG con transparencia, apoyado en el borde. Entra deslizando.
         tarjeta  foto o captura en un rectangulo de esquina redondeada.
  sitio  abajo | abajo-izq | abajo-der | izq | der | arriba-izq | arriba-der
  alto   fraccion de la altura del cuadro que ocupa (0.46 = 46%)

El material sale de input/props/. Se declara en HTML y no por JS, igual que el
b-roll: HyperFrames compila los medios del HTML inicial.

Uso: bin/props.py beats.json <raiz> <proyecto>   -> imprime el HTML
"""
import json, os, shutil, subprocess, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cfg import cfg

beats = json.load(open(sys.argv[1])) if sys.argv[1] else {}
raiz, proy = sys.argv[2], sys.argv[3]

SITIOS = {"abajo", "abajo-izq", "abajo-der", "izq", "der",
          "arriba", "arriba-izq", "arriba-der"}
VIDEO = (".mp4", ".mov", ".m4v", ".webm")
html, faltan, n = [], [], 0
detras_html, detras = [], []
AROLL = os.path.join(proy, "aroll.mp4")


def poner_detras(p, i):
    """Genera el recorte del que habla para la ventana de este prop y devuelve su HTML.

    Con esto el elemento deja de necesitar un hueco libre: se le pone DETRAS, y el
    cuerpo y las manos del que habla pasan por delante. Es como estan puestos los
    recortes en las referencias."""
    if not os.path.exists(AROLL):
        faltan.append("no encuentro aroll.mp4 en el proyecto para recortar al sujeto")
        return None
    salida = os.path.join(proy, "props", f"detras-{i}.webm")
    os.makedirs(os.path.dirname(salida), exist_ok=True)
    # Recortar al sujeto cuesta ~1s por fotograma. Si ya esta hecho para esta misma
    # ventana y el plano no ha cambiado, se reaprovecha: si no, cada retoque de una
    # coma del guion costaba dos minutos de espera.
    marca = os.path.join(proy, "props", f"detras-{i}.txt")
    # La firma NO puede usar la fecha del aroll: el montaje lo vuelve a copiar cada
    # vez, asi que la fecha cambia siempre y la cache no servia de nada. El tamano en
    # bytes si identifica al plano.
    firma = f"{p['at']}|{p['dur']}|{os.path.getsize(AROLL)}"
    if os.path.exists(salida) and os.path.exists(marca) and open(marca).read() == firma:
        print(f"  recorte del sujeto reaprovechado ({p['dur']}s desde {p['at']}s)", file=sys.stderr)
        detras.append({"i": i, "at": p["at"], "dur": p["dur"]})
        return (f'      <div class="camara" id="detras-{i}">\n'
                f'        <video id="detrasv-{i}" class="clip" src="props/detras-{i}.webm" muted '
                f'playsinline data-start="{p["at"]}" data-media-start="0" '
                f'data-duration="{p["dur"]}" data-volume="0" data-track-index="4"></video>\n'
                f'      </div>')
    # stdout capturado a proposito: lo que imprime este script va al HTML del
    # proyecto, y cualquier linea suelta acaba escrita dentro del video.
    r = subprocess.run([sys.executable, os.path.join(raiz, "bin", "matte.py"),
                        AROLL, str(p["at"]), str(p["dur"]), salida],
                       stdout=subprocess.DEVNULL)
    if r.returncode != 0 or not os.path.exists(salida):
        faltan.append(f"no se pudo recortar al sujeto para el prop de {p['at']}s")
        return None
    open(marca, "w").write(firma)
    detras.append({"i": i, "at": p["at"], "dur": p["dur"]})
    return (f'      <div class="camara" id="detras-{i}">\n'
            f'        <video id="detrasv-{i}" class="clip" src="props/detras-{i}.webm" muted '
            f'playsinline data-start="{p["at"]}" data-media-start="0" '
            f'data-duration="{p["dur"]}" data-volume="0" data-track-index="4"></video>\n'
            f'      </div>')


def esc(t):
    return (str(t).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;"))


def inicial(nombre):
    """El avatar es la inicial sobre un circulo de color, no una foto. Una cara real
    en una notificacion falsa seria suplantar a alguien; una inicial se lee como lo
    que es, una recreacion."""
    return esc(nombre.strip()[:1].upper() or "?")


def captura(p):
    """Dibuja la captura en HTML, sin archivo. Son las notificaciones de mensaje y los
    chats que salen en las referencias. Todo el texto va en espanol neutro, y los
    nombres son de pila y genericos: no se recrea la cuenta de nadie."""
    estilo = p.get("estilo", "dm")
    if estilo == "dm":
        filas = []
        for it in p.get("items", []):
            filas.append(
                '<div class="cap-dm">'
                f'<div class="cap-av">{inicial(it.get("de", "?"))}</div>'
                '<div class="cap-tx">'
                f'<div class="cap-de">{esc(it.get("de", ""))}</div>'
                f'<div class="cap-msg">{esc(it.get("texto", ""))}</div>'
                f'<div class="cap-hora">{esc(it.get("cuando", ""))}</div>'
                "</div>"
                '<div class="cap-punto"></div>'
                "</div>")
        return f'<div class="cap-pila">{"".join(filas)}</div>'

    if estilo == "chat":
        burbujas = []
        for m in p.get("mensajes", []):
            lado = "yo" if m.get("lado") == "yo" else "otro"
            burbujas.append(
                f'<div class="cap-bur {lado}">{esc(m.get("texto", ""))}'
                f'<span class="cap-h">{esc(m.get("hora", ""))}</span></div>')
        return ('<div class="cap-tel">'
                '<div class="cap-cab">'
                f'<div class="cap-av chico">{inicial(p.get("contacto", "?"))}</div>'
                f'<div><div class="cap-de">{esc(p.get("contacto", ""))}</div>'
                '<div class="cap-est">en l\u00ednea</div></div></div>'
                f'<div class="cap-cuerpo">{"".join(burbujas)}</div>'
                "</div>")

    raise ValueError(f"estilo de captura desconocido: {estilo}")

for p in beats.get("props", []):
    sitio = p.get("sitio", "abajo-izq")
    if sitio not in SITIOS:
        faltan.append(f"sitio '{sitio}' desconocido (usa {sorted(SITIOS)})")
        continue

    # Las capturas se DIBUJAN: no hay archivo que copiar.
    if p.get("tipo") == "captura":
        p["__pi"] = n
        alto = float(p.get("alto", 0.26))
        try:
            cuerpo = captura(p)
        except ValueError as e:
            faltan.append(str(e))
            continue
        html.append(
            f'      <div class="prop captura {p.get("estilo", "dm")} {sitio}" id="prop-{n}" '
            f'style="--alto:{alto * 100:.1f}%" data-layout-allow-overflow>\n'
            f'        {cuerpo}\n'
            f'      </div>')
        print(f"  prop: captura {p.get('estilo', 'dm')} ({sitio}, {alto * 100:.0f}% de alto)",
              file=sys.stderr)
        n += 1
        continue

    a = p.get("archivo")
    if not a:
        faltan.append("(prop sin campo 'archivo')")
        continue
    # el material puede venir de input/props/ o del b-roll que ya tiene el video
    orig = a if os.path.isabs(a) else os.path.join(raiz, "input", "props", a)
    if not os.path.exists(orig):
        orig = os.path.join(raiz, "input", "broll", a)
    # y de la carpeta de RECURSOS del formato (la clase, la guia): ahi es donde el
    # usuario deja las portadas, y `masterclass.jpg` solo funcionaba porque ademas
    # habia una copia suelta en input/props/.
    if not os.path.exists(orig):
        orig = os.path.join(raiz, str(cfg("recursos.carpeta", "input/props/recursos")), a)
    if not os.path.exists(orig):
        faltan.append(orig)
        continue
    os.makedirs(os.path.join(proy, "props"), exist_ok=True)
    base = os.path.basename(orig)
    shutil.copy2(orig, os.path.join(proy, "props", base))
    p["__pi"] = n
    tipo = p.get("tipo", "recorte")
    alto = float(p.get("alto", 0.46))

    # La OFERTA lleva etiqueta y resplandor: es la pieza del cierre, no un adorno.
    if tipo == "oferta":
        etq = p.get("etiqueta") or {}   # sin etiqueta = sin texto sobre la imagen
        cuerpo = ""
        if etq:
            cuerpo += ('<div class="of-etq">'
                       f'<div class="of-arriba">{esc(etq.get("arriba", ""))}</div>'
                       f'<div class="of-abajo">{esc(etq.get("abajo", ""))}</div></div>')
        medio_of = (f'<img src="props/{base}" alt="">' if not base.lower().endswith(VIDEO)
                    else f'<video id="propv-{n}" class="clip" src="props/{base}" muted playsinline '
                         f'data-start="{p["at"]}" data-media-start="0" data-duration="{p["dur"]}" '
                         f'data-volume="0" data-track-index="2"></video>')
        cuerpo += f'<div class="of-caja">{medio_of}</div>'
        luz = p.get("luz", "rgba(255,92,48,.85)")
        html.append(
            f'      <div class="prop oferta {sitio}" id="prop-{n}" '
            f'style="--alto:{alto * 100:.1f}%;--of-luz:{luz};'
            f'--of-y:{p.get("abajo_de", "72%")};'
            f'font-size:{p.get("cuerpo", 110)}px" data-layout-allow-overflow>\n'
            f'        {cuerpo}\n'
            f'      </div>')
        print(f"  prop: OFERTA {base} ({etq.get('arriba','')} {etq.get('abajo','')}, "
              f"{alto * 100:.0f}% de alto)", file=sys.stderr)
        n += 1
        continue

    if base.lower().endswith(VIDEO):
        # Una tarjeta tambien puede llevar VIDEO, no solo una foto: es la pieza de la
        # referencia donde una escena corre dentro de un rectangulo de esquina
        # redondeada al lado del que habla. El id es obligatorio — sin el, el renderer
        # no descubre el medio y el clip sale congelado — y la temporizacion va en el
        # <video>, nunca en el contenedor.
        try:
            real = float(subprocess.run(
                ["ffprobe", "-v", "error", "-show_entries",
                 "format=duration", "-of", "csv=p=0", orig],
                capture_output=True, text=True).stdout.strip())
            if p["dur"] > real - 0.03:
                print(f"  {base} recortado a {real - 0.03:.2f}s: no da mas de si",
                      file=sys.stderr)
                p["dur"] = round(real - 0.03, 3)
        except (ValueError, OSError):
            pass
        medio = (f'<video id="propv-{n}" class="clip" src="props/{base}" muted playsinline '
                 f'data-start="{p["at"]}" data-media-start="{p.get("media_start", 0)}" '
                 f'data-duration="{p["dur"]}" data-volume="0" data-track-index="2"></video>')
    else:
        medio = f'<img src="props/{base}" alt="">'

    html.append(
        f'      <div class="prop {tipo} {sitio}" id="prop-{n}" '
        f'style="--alto:{alto * 100:.1f}%" data-layout-allow-overflow>\n'
        f'        {medio}\n'
        f'      </div>')
    if p.get("detras"):
        h = poner_detras(p, n)
        if h:
            detras_html.append(h)
            print(f"  prop: {base} DETRAS del sujeto ({sitio}, {alto * 100:.0f}% de alto)",
                  file=sys.stderr)
            n += 1
            continue
    print(f"  prop: {base} ({tipo}, {sitio}, {alto * 100:.0f}% de alto)", file=sys.stderr)
    n += 1

# Las imagenes de los ROTULOS del TOP 10 viajan al proyecto desde aqui: ya no son props
# sueltos, van dentro del bloque del rotulo, pero el archivo hay que copiarlo igual.
for r in (beats.get("rotulos", []) if isinstance(beats, dict) else []):
    if r.get("img"):
        o = os.path.join(raiz, "input", "props", "top10", r["img"])
        if os.path.exists(o):
            d = os.path.join(proy, "props", "top10"); os.makedirs(d, exist_ok=True)
            shutil.copy2(o, os.path.join(d, r["img"]))
        else:
            faltan.append(o)

if faltan:
    print("ERROR: faltan imagenes de props:", file=sys.stderr)
    for f in faltan:
        print(f"  {f}", file=sys.stderr)
    sys.exit(1)

# El JS necesita saber cuando entra y sale cada una; el HTML solo las declara.
if n:
    datos = [{"i": p["__pi"], "at": p["at"], "dur": p["dur"],
              "tipo": p.get("tipo", "recorte"), "sitio": p.get("sitio", "abajo-izq"),
              "sube_texto": p.get("sube_texto", 14)}
             for p in beats.get("props", []) if "__pi" in p]
    with open(os.path.join(proy, "props.json"), "w") as f:
        json.dump(datos, f, ensure_ascii=False, indent=1)
else:
    with open(os.path.join(proy, "props.json"), "w") as f:
        f.write("[]")

# FLASH DE SILUETA (editorial, ejemplos): en el doble flash del gancho la
# persona se vuelve blanco puro y el fondo sigue visible. Se recorta al sujeto en la
# ventana 0.15-0.50s y la plantilla lo pinta en blanco (filter) solo en los frames del
# flash. Cache por tamano del aroll, igual que los recortes de `detras`.
_pf = beats.get("primer_frame") or {} if isinstance(beats, dict) else {}
if _pf.get("destello_doble") and os.path.exists(AROLL):
    _sal = os.path.join(proy, "props", "silueta.webm"); os.makedirs(os.path.dirname(_sal), exist_ok=True)
    _marca = os.path.join(proy, "props", "silueta.txt"); _firma = f"0.15|0.35|{os.path.getsize(AROLL)}"
    if not (os.path.exists(_sal) and os.path.exists(_marca) and open(_marca).read() == _firma):
        _r = subprocess.run([sys.executable, os.path.join(raiz, "bin", "matte.py"), AROLL, "0.15", "0.35", _sal],
                            stdout=subprocess.DEVNULL)
        if _r.returncode == 0 and os.path.exists(_sal):
            open(_marca, "w").write(_firma)
    if os.path.exists(_sal):
        detras_html.append('      <div class="camara" id="silueta">\n'
                           '        <video id="siluetav" class="clip" src="props/silueta.webm" muted playsinline '
                           'data-start="0.15" data-media-start="0" data-duration="0.35" data-volume="0" '
                           'data-track-index="4"></video>\n      </div>')
        print("  silueta del sujeto para el doble flash del gancho (0.15-0.50s)", file=sys.stderr)
    else:
        print("  AVISO: no se pudo recortar la silueta del gancho; el flash sera a pantalla completa", file=sys.stderr)

with open(os.path.join(proy, "detras.json"), "w") as f:
    json.dump(detras, f, ensure_ascii=False, indent=1)
with open(os.path.join(proy, "detras.html"), "w") as f:
    f.write("\n".join(detras_html))

print("\n".join(html))
