#!/usr/bin/env python3
"""Auditor de dopamina: garantiza que el video no pase mas de N segundos sin estimulo.

Estimulo = keyword animada, stinger, lista, o zoom de camara.
Si entre dos estimulos hay un hueco mayor que MAX_HUECO, mete un zoom en medio,
alineado al inicio del cue mas cercano (para que el punch caiga sobre una palabra
y no a mitad de silaba).

Zooms que alterna:
  punch  corte seco de escala (12%), sin transicion. El mas agresivo.
  push   acercamiento lento durante 1.6s. Sostiene la atencion sin marear.
  pull   alejamiento lento. Da aire despues de un bloque denso.

Uso: bin/estimulos.py cues.json beats.json keywords.json <duracion> [max_hueco]
Escribe zooms.json y un informe por stderr.
"""
import os, json, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cfg import cfg

cues = json.load(open(sys.argv[1]))
beats = json.load(open(sys.argv[2])) if sys.argv[2] else {"stingers": [], "listas": []}
keys = json.load(open(sys.argv[3])) if sys.argv[3] else []
dur = float(sys.argv[4])
MAX_HUECO = float(sys.argv[5]) if len(sys.argv) > 5 else cfg("estimulos.hueco_max", 3.0)
# LA APERTURA VA MAS DENSA. Medido: con un solo hueco para todo el video, el zoom out
# de apertura contaba como estimulo y el relleno esperaba el hueco entero, asi que en
# `comentasocialing` no habia NADA hasta el segundo 5.3 y ningun zoom dentro del gancho.
# El editor: "si en los primeros 3 segundos no los estimulas bien, la gente se va".
# Durante `apertura_dur` el limite baja a `apertura_hueco`.
APERTURA_DUR = float(cfg("estimulos.apertura_dur", 0.0))
APERTURA_HUECO = float(cfg("estimulos.apertura_hueco", MAX_HUECO))

# Un estimulo DURA: una frase animada de 2.6s sigue estimulando mientras esta en
# pantalla. El hueco se mide desde que termina uno hasta que empieza el siguiente,
# no entre inicios; medirlo entre inicios inventaba huecos que no existen.
fijos = ([{"at": k["at"], "fin": k["at"] + k.get("dur", 0), "tipo": "keyword"} for k in keys]
         + [{"at": b["at"], "fin": b["at"] + b.get("dur", 0), "tipo": "stinger"}
            for b in beats.get("stingers", [])]
         + [{"at": b["at"], "fin": b["at"] + b.get("dur", 0), "tipo": "lista"}
            for b in beats.get("listas", [])])
fijos.sort(key=lambda x: x["at"])

inicios = [c["start"] for c in cues]


def cue_cercano(t):
    return min(inicios, key=lambda s: abs(s - t)) if inicios else t


zooms, tipos = [], ["punch", "push", "punch", "pull"]


# EL REPARTO. Regla del usuario: ~50% su plano, ~30% b-roll, ~20% motion graphic.
# Y "los zooms pueden reducirse si hay muchisimo b-roll o motion graphic": cuando los
# graficos ya cubren mas de `cobertura_alta` del video, el hueco permitido crece
# `cobertura_factor` veces — la pantalla ya cambia sola, la camara no hace falta.
_br = sum(b.get("dur", 0) for b in beats.get("stingers", []) if b.get("tipo") == "broll")
_mg = sum(b.get("dur", 0) for b in beats.get("stingers", []) if b.get("tipo") != "broll")
_mg += sum(b.get("dur", 0) for b in beats.get("listas", []))
COBERTURA = (_br + _mg) / dur if dur else 0.0
print(f"  reparto: cara {1 - COBERTURA:.0%} / b-roll {_br / dur:.0%} / motion graphic {_mg / dur:.0%}"
      f"   (objetivo {cfg('reparto.cara', 50)}/{cfg('reparto.broll', 30)}/{cfg('reparto.mg', 20)})",
      file=sys.stderr)
FACTOR = float(cfg("estimulos.cobertura_factor", 1.5)) if COBERTURA >= float(cfg("estimulos.cobertura_alta", 0.45)) else 1.0
if FACTOR != 1.0:
    print(f"  graficos cubren {COBERTURA:.0%}: los zooms se espacian x{FACTOR}", file=sys.stderr)


def limite(t):
    """el hueco permitido en el instante t: mas corto mientras dura la apertura"""
    return (APERTURA_HUECO if t < APERTURA_DUR else MAX_HUECO) * FACTOR


def rellenar(desde, hasta):
    """mete zooms entre dos instantes hasta que ningun hueco pase del limite"""
    t = desde
    while hasta - t > limite(t):
        MAX_HUECO = limite(t)
        objetivo = cue_cercano(t + MAX_HUECO * 0.8)
        # el ajuste al cue mas cercano puede empujar el zoom MAS ALLA del limite:
        # asi quedaba un hueco real de 3.26s con el limite en 3.0, y el informe lo
        # cantaba sin que hubiera forma de que el relleno lo arreglara. El zoom se
        # ajusta al habla, pero nunca a costa de saltarse el limite.
        if objetivo <= t + 0.4 or objetivo >= hasta - 0.2 or objetivo > t + MAX_HUECO:
            objetivo = t + MAX_HUECO * 0.8
        zooms.append({"at": round(objetivo, 3), "tipo": tipos[len(zooms) % len(tipos)]})
        t = objetivo


# El gancho de apertura ya es un estimulo, y de los fuertes: el zoom out ocupa el
# primer medio segundo. Sin contarlo, se metia un zoom encima del arranque que
# peleaba con el mismo tween sobre #camara.
prev = float(cfg("arranque.duracion", 0.0)) if cfg("arranque.activo", False) else 0.0
if prev:
    print(f"arranque: zoom out de apertura ocupa 0 -> {prev}s (cuenta como estimulo)",
          file=sys.stderr)
for f in fijos:
    rellenar(prev, f["at"])
    prev = max(prev, f["fin"])          # el estimulo cuenta hasta que termina
rellenar(prev, dur)

zooms.sort(key=lambda z: z["at"])
json.dump(zooms, open("zooms.json", "w") if False else sys.stdout, ensure_ascii=False, indent=1)

# --- informe -------------------------------------------------------------
# para el informe, cada estimulo ocupa desde su inicio hasta su fin
tramos = sorted([(f["at"], f["fin"]) for f in fijos] + [(z["at"], z["at"]) for z in zooms])
todos = [t[0] for t in tramos]
# Los tramos se FUNDEN antes de medir. Sin esto, un zoom que cae dentro de una
# frase animada rompia el tramo en dos y el informe inventaba huecos: cantaba
# 3.42s donde el hueco real eran 2.80s, y no habia forma de arreglarlo porque
# no existia.
fund = []
for a, b in tramos:
    if fund and a <= fund[-1][1]:
        fund[-1][1] = max(fund[-1][1], b)
    else:
        fund.append([a, b])
if cfg("arranque.activo", False):
    fund.insert(0, [0.0, float(cfg("arranque.duracion", 0.0))])
tramos = fund
huecos = [(round(tramos[i][1], 2), round(tramos[i + 1][0], 2),
           round(tramos[i + 1][0] - tramos[i][1], 2))
          for i in range(len(tramos) - 1)]
peor = max([h[2] for h in huecos], default=round(dur, 2))
inicio = round(todos[0], 2) if todos else round(dur, 2)
final = round(dur - todos[-1], 2) if todos else round(dur, 2)
print(f"\nestimulos: {len(fijos)} fijos + {len(zooms)} zooms = {len(todos)}", file=sys.stderr)
print(f"hueco maximo entre estimulos: {peor}s  (limite {MAX_HUECO}s)", file=sys.stderr)
print(f"hasta el primero: {inicio}s   desde el ultimo al final: {final}s", file=sys.stderr)
if peor > MAX_HUECO + 0.05 or inicio > MAX_HUECO or final > MAX_HUECO:
    print("AVISO: hay tramo sin estimulo por encima del limite", file=sys.stderr)
