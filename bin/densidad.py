#!/usr/bin/env python3
"""Aviso de densidad de stingers.

Los motion graphics NO son automaticos: se colocan a mano en beats.json. Lo unico
automatico es la regla de los 3 segundos, y esa se rellena con ZOOMS de camara.
Este chequeo existe para que los stingers no se conviertan en un tic: si salen
demasiado seguidos dejan de ser un golpe y pasan a ser el fondo del video.

Uso: bin/densidad.py beats.json <duracion> estilo.json
"""
import json, sys

if len(sys.argv) < 4 or not sys.argv[1]:
    sys.exit(0)

beats = json.load(open(sys.argv[1]))
dur = float(sys.argv[2])
lim = json.load(open(sys.argv[3]))["stingers"]["densidad_aviso"]

n = len(beats.get("stingers", []))
por_min = n / (dur / 60) if dur else 0
linea = f"  stingers: {n} en {dur:.0f}s = {por_min:.1f}/min"
if por_min > lim:
    linea += f"   AVISO: por encima de {lim}/min. No deberian salir siempre."
print(linea, file=sys.stderr)
