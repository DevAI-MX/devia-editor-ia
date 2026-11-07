#!/usr/bin/env python3
"""Zoom en los cortes (formato editorial), decidido en UN sitio para que la
plantilla (el movimiento) y sfx.py (el tick) hagan lo mismo.

Regla del usuario: "los zooms son solo de acercar y alejar, no tantos ni tan de
pronto; el zoom va en cada corte, no porque si; si el clip es muy largo, un zoom in o
zoom out muy lento".

  - El encuadre cambia EN un corte: de base (1.00) a cerrado (1.00+entra) o al reves.
    Es un acercar/alejar que coincide con el salto de plano, asi que se lee como un
    cambio de plano y no como un efecto.
  - No en todos los cortes: solo si han pasado `cada_min` segundos desde el ultimo
    cambio. Los cortes de en medio quedan como jump cuts limpios.
  - Un clip largo (>= `largo`) lleva una deriva MUY lenta (`deriva`/s) en la
    direccion contraria a donde esta: si esta cerrado se abre despacio, si esta en
    base se cierra despacio. Un clip corto no se mueve.

Uso: bin/zoomcortes.py cortes.json <duracion> <t0> > zooms_cortes.json
Escribe [{"at", "escala", "deriva_hasta", "fin"}] con la escala que toma la camara
en cada tramo. Por stderr, un resumen.
"""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cfg import cfg

cortes_p, dur, t0 = sys.argv[1], float(sys.argv[2]), float(sys.argv[3])
PC = cfg("estimulos.punch_en_cortes", {}) or {}
ENTRA = float(PC.get("entra", 0.08))
CADA = float(PC.get("cada_min", 2.5))
LARGO = float(PC.get("largo", 4.0))
DERIVA = float(PC.get("deriva", 0.015))
HERO = float(PC.get("hero", 0.14))

bordes, acc = [], 0.0
if os.path.exists(cortes_p):
    for a, b in json.load(open(cortes_p))["keep"][:-1]:
        acc += b - a; bordes.append(round(acc, 3))
cortes = [c for c in bordes if c > t0 + 0.2]

tramos = []
escala, ultimo = 1.0, t0
puntos = [t0] + cortes + [dur]
cambios = 0
for i in range(len(puntos) - 1):
    a, b = puntos[i], puntos[i + 1]
    if i > 0 and a - ultimo >= CADA:
        escala = 1.0 + ENTRA if escala <= 1.0 + 1e-6 else 1.0
        ultimo = a; cambios += 1
    largo = (b - a) >= LARGO
    hasta = escala
    if largo:
        signo = -1 if escala > 1.0 + 1e-6 else 1
        hasta = round(escala + signo * DERIVA * (b - a), 4)
        hasta = max(1.0, min(1.0 + ENTRA + 0.06, hasta))
    tramos.append({"at": round(a, 3), "fin": round(b, 3), "escala": round(escala, 4),
                   "deriva_hasta": hasta, "cambio": bool(i > 0 and a == ultimo)})
json.dump(tramos, sys.stdout, ensure_ascii=False, indent=1)
n_largos = sum(1 for t in tramos if t["deriva_hasta"] != t["escala"])
print(f"  zoom en cortes: {cambios} cambios de encuadre en {len(cortes)} cortes "
      f"(minimo {CADA}s entre cambios, {ENTRA:.0%}); {n_largos} clips largos con deriva lenta", file=sys.stderr)
