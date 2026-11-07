#!/usr/bin/env python3
"""Incrusta en el proyecto SOLO los iconos que se usan.

La biblioteca (Lucide, licencia ISC, ~2000 iconos de trazo) vive en
plantilla/iconos/. Aqui se leen los nombres declarados en beats.json y se emite
un iconos.js con esos SVG en linea. Asi el render no depende de la red ni arrastra
7,9 MB por video.

Se eligen iconos de TRAZO a proposito: al ser lineas con `currentColor`, heredan
el color de acento del stinger y el glow se agarra al trazo. Un icono relleno se
apelmaza sobre fondo oscuro.

Uso: bin/iconos.py beats.json plantilla/iconos > proyecto/iconos.js
"""
import json, os, re, sys

beats = json.load(open(sys.argv[1])) if sys.argv[1] else {}
libreria = sys.argv[2]

nombres = []
for b in beats.get("stingers", []):
    for campo in ("icono", "iconos"):
        v = b.get(campo)
        if isinstance(v, str):
            nombres.append(v)
        elif isinstance(v, list):
            nombres += v

salida, faltan = {}, []
for n in dict.fromkeys(nombres):
    ruta = os.path.join(libreria, n + ".svg")
    if not os.path.exists(ruta):
        faltan.append(n)
        continue
    svg = open(ruta).read()
    svg = re.sub(r"<!--.*?-->", "", svg, flags=re.S)          # fuera la cabecera de licencia
    svg = re.sub(r'\s*width="\d+"|\s*height="\d+"', "", svg)  # el tamano lo pone el CSS
    salida[n] = " ".join(svg.split())

if faltan:
    print(f"ERROR: estos iconos no existen en la biblioteca: {', '.join(faltan)}",
          file=sys.stderr)
    print(f"       busca el nombre exacto en {libreria}/", file=sys.stderr)
    sys.exit(1)

print(f"window.__ICONOS__ = {json.dumps(salida, ensure_ascii=False)};")
if salida:
    print(f"  iconos incrustados: {', '.join(salida)}", file=sys.stderr)
