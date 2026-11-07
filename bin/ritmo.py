#!/usr/bin/env python3
"""Ajusta los zooms al pulso de la cancion, pero solo cuando no se nota.

Los zooms los coloca bin/estimulos.py sobre el habla: caen al principio de una
palabra para que el golpe no parta una silaba. Aqui se les da un empujon de unas
centesimas para que ademas coincidan con un golpe de la musica. Como el SFX de cada
zoom sale de este mismo archivo, el efecto queda pegado al beat sin tocar nada mas.

La regla es NO FORZAR. Un zoom solo se mueve si el golpe le queda a menos de
`ritmo.ajuste`; si el golpe esta lejos, el zoom se queda donde estaba, encima de la
palabra. Vale mas un efecto fuera del compas que uno fuera de la frase.

Uso: bin/ritmo.py zooms.json compas.json [ajuste] > zooms_al_ritmo.json
"""
import os, sys, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cfg import cfg

zooms = json.load(open(sys.argv[1]))
compas = json.load(open(sys.argv[2])) if sys.argv[2] and os.path.exists(sys.argv[2]) else {}
AJUSTE = float(sys.argv[3]) if len(sys.argv) > 3 else cfg("ritmo.ajuste", 0.13)

golpes = compas.get("golpes") or []
if not golpes:
    json.dump(zooms, sys.stdout, ensure_ascii=False, indent=1)
    print("  ritmo: sin analisis de la cancion, los zooms se quedan como estaban",
          file=sys.stderr)
    sys.exit(0)

# Dos rejillas, por orden de preferencia: primero el golpe del compas (el "uno",
# que es el que se siente), y si ese queda lejos, el tiempo suelto. Ajustarse solo
# al uno dejaba fuera casi todos los zooms: con compases de 1.5s, la probabilidad
# de que uno caiga a menos de 0.13s del golpe es de una entre seis.
tiempos = compas.get("tiempos") or []
movidos, desvios, en_uno = 0, [], 0
for z in zooms:
    for rejilla, nombre in ((golpes, "compas"), (tiempos, "tiempo")):
        if not rejilla:
            continue
        g = min(rejilla, key=lambda t: abs(t - z["at"]))
        d = g - z["at"]
        if abs(d) <= AJUSTE:
            z["at"] = round(g, 3)
            z["al_ritmo"] = round(d, 3)
            z["cae_en"] = nombre
            movidos += 1
            en_uno += nombre == "compas"
            desvios.append(abs(d))
            break

zooms.sort(key=lambda z: z["at"])
json.dump(zooms, sys.stdout, ensure_ascii=False, indent=1)
media = sum(desvios) / len(desvios) if desvios else 0
print(f"  ritmo: {movidos} de {len(zooms)} zooms caen con la musica "
      f"({en_uno} en el uno del compas, {movidos - en_uno} en un tiempo; "
      f"movidos {media*1000:.0f}ms de media, tope {AJUSTE*1000:.0f}ms); "
      f"el resto se queda sobre la palabra", file=sys.stderr)
