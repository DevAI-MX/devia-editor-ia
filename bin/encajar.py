#!/usr/bin/env python3
"""Encaja el final de cada motion graphic con el corte del A-roll que tiene detras.

El problema: si el stinger termina un poco ANTES de un corte del A-roll, al salir
se ve un pedacito del clip viejo y acto seguido el salto de plano. Se cuentan dos
cortes donde deberia verse uno.

La regla: el motion graphic nunca termina justo antes de un corte. Si el corte cae
dentro de la ventana, el stinger se ALARGA hasta ese corte exacto y sale de golpe,
de modo que el cambio de plano queda tapado por el grafico. Nunca se acorta.

Los cortes de salida salen de <base>_cortes.json (los segmentos que dejo cortar.sh):
la posicion de cada corte en la linea de tiempo final es la suma acumulada de las
duraciones de los segmentos anteriores.

Uso: bin/encajar.py beats.json cortes.json [ventana] > beats_encajados.json
"""
import json, os, subprocess, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cfg import cfg

beats = json.load(open(sys.argv[1]))
cortes = json.load(open(sys.argv[2]))
VENTANA = float(sys.argv[3]) if len(sys.argv) > 3 and sys.argv[3] else cfg("stingers.encaje", 1.2)
RAIZ = sys.argv[4] if len(sys.argv) > 4 else ""


def dura(b):
    """cuanto material hay de verdad: un b-roll no se puede alargar mas alla de su
    propio metraje (si se le pide de mas, se queda congelado en el ultimo frame)"""
    m = b.get("media")
    if not m or not RAIZ:
        return 1e9
    f = m if os.path.isabs(m) else os.path.join(RAIZ, "input", "broll", m)
    if not os.path.exists(f):
        return 1e9
    try:
        return float(subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries",
             "format=duration", "-of", "csv=p=0", f],
            capture_output=True, text=True).stdout.strip()) - 0.03
    except ValueError:
        return 1e9

acc, bordes = 0.0, []
for a, b in cortes["keep"][:-1]:
    acc += b - a
    bordes.append(round(acc, 3))

movidos = 0
stg = sorted(beats.get("stingers", []), key=lambda x: x["at"])
# Cuanto puede crecer un stinger en TOTAL entre los dos lados. Sin tope, un b-roll
# que tuviera un corte 2s antes y otro 2s despues se iba a 6s y tapaba dos frases.
CRECE_MAX = float(cfg("stingers.encaje_crece_max", VENTANA))
for k, s in enumerate(stg):
    ini, fin = s["at"], s["at"] + s["dur"]
    dur0 = s["dur"]
    # Techo: nunca puede pisar al stinger siguiente. Sin esto se alargaba a ciegas
    # y dos b-rolls quedaban solapados 0.05s en la misma pista, que es justo lo que
    # 'hyperframes check' rechaza. El fallo no se ve en el JSON de entrada porque
    # ahi no habia solape: lo creaba este propio ajuste.
    techo = stg[k + 1]["at"] if k + 1 < len(stg) else 1e9
    suelo = stg[k - 1]["at"] + stg[k - 1]["dur"] if k else 0.0
    tope_media = s["at"] + dura(s)

    # 1) Un corte poco DESPUES del final: se alarga hasta el corte (regla original).
    cand_fin = [c for c in bordes if 0 < c - fin <= VENTANA and c <= techo and c <= tope_media]
    # 2) Un corte poco ANTES del inicio: se ADELANTA el inicio hasta el corte, y el
    #    grafico entra justo en el salto de plano. Regla del usuario: "si el b-roll
    #    esta proximo a un corte por un segundo o dos, que el corte quede tapado".
    #    Una ficha no se adelanta: su emoji va con una frase concreta y adelantarla
    #    la separa de lo que se dice. El b-roll si, es imagen sin texto propio.
    cand_ini = ([c for c in bordes if 0 < ini - c <= VENTANA and c >= suelo]
                if s.get("tipo") == "broll" else [])
    # Gana el corte mas cercano; el otro lado solo si queda margen de crecimiento.
    opciones = ([(fin_c - fin, "fin", fin_c) for fin_c in cand_fin]
                + [(ini - ini_c, "ini", ini_c) for ini_c in cand_ini])
    if not opciones:
        continue
    opciones.sort()
    crecido = 0.0
    for delta, lado, c in opciones:
        if crecido + delta > CRECE_MAX + 1e-6:
            continue
        if lado == "fin" and c > s["at"] + s["dur"]:
            s["dur"] = round(c - s["at"], 3)
            s["encajado"] = round(s.get("encajado", 0) + delta, 3)
            crecido += delta
        elif lado == "ini" and c < s["at"]:
            s["dur"] = round(s["at"] + s["dur"] - c, 3)
            s["at"] = round(c, 3)
            s["adelantado"] = round(delta, 3)
            crecido += delta
    if crecido:
        movidos += 1

json.dump(beats, sys.stdout, ensure_ascii=False, indent=1)

if bordes:
    print(f"  cortes del A-roll en la salida: {bordes}", file=sys.stderr)
for s in beats.get("stingers", []):
    if "adelantado" in s:
        print(f"  stinger {s.get('tipo')} adelantado {s['adelantado']}s hasta el corte "
              f"({s['at']}s): entra en el salto de plano", file=sys.stderr)
    if "encajado" in s:
        print(f"  stinger {s.get('tipo')} alargado {s['encajado']}s hasta el corte "
              f"({round(s['at'] + s['dur'], 3)}s): tapa el salto de plano", file=sys.stderr)
if bordes and not movidos:
    print("  ningun stinger cae cerca de un corte: nada que encajar", file=sys.stderr)

# Y los cortes que se quedan AL DESCUBIERTO: ningun grafico los tapa. Se cantan para
# que el montaje ponga un b-roll justo ahi ("si hay un corte, mete algo que no parezca
# que el video esta cortado"). Se considera tapado si un stinger esta en pantalla en
# el instante del corte.
al_aire = []
for c in bordes:
    if not any(s["at"] - 0.05 <= c <= s["at"] + s["dur"] + 0.05 for s in beats.get("stingers", [])):
        al_aire.append(c)
if al_aire:
    print(f"  CORTES AL DESCUBIERTO ({len(al_aire)} de {len(bordes)}): "
          + ", ".join(f"{c:.1f}s" for c in al_aire) + "  <- un b-roll que empiece ahi los tapa",
          file=sys.stderr)
elif bordes:
    print(f"  todos los cortes ({len(bordes)}) quedan tapados por un grafico", file=sys.stderr)
