#!/usr/bin/env python3
"""Traslada los tiempos de un beats.json de un corte a otro.

Cuando se vuelve a cortar un video (por ejemplo para cerrar los huecos entre
palabras), todo lo que venia despues se adelanta. Las frases animadas se
recolocan solas, porque alinear.py y kw.py las buscan por su TEXTO; pero el
b-roll no tiene texto, asi que su `at` se quedaria en el sitio viejo.

Aqui se resuelve por palabras: se mira que palabra sonaba en ese instante en el
transcript VIEJO y se busca esa misma palabra en el NUEVO, comparando el contexto
de alrededor para no confundirla con otra igual mas adelante.

Uso: bin/remapear.py beats.json transcript_viejo.json transcript_nuevo.json > beats2.json
"""
import json, sys, unicodedata


def norm(t):
    t = unicodedata.normalize("NFD", t.lower())
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    return "".join(c for c in t if c.isalnum())


def palabras(p):
    return [{"n": norm(w["word"]), "s": float(w["start"]), "e": float(w["end"])}
            for seg in json.load(open(p)).get("segments", [])
            for w in seg.get("words", []) if norm(w["word"])]


datos = json.load(open(sys.argv[1]))
# vale tanto para beats.json (dict con "stingers") como para keywords.json (lista)
es_beats = isinstance(datos, dict)
piezas = datos.get("stingers", []) if es_beats else datos
viejo, nuevo = palabras(sys.argv[2]), palabras(sys.argv[3])
# El corte solo QUITA tiempo, nunca reordena: la palabra numero 40 del corte viejo
# sigue siendo la numero 40 del nuevo (salvo alguna que whisper lea distinto). Asi
# que se emparejan las dos listas de palabras con difflib y se traduce por indice.
#
# El primer intento buscaba un contexto de 13 palabras por todo el transcript nuevo
# y elegia el mejor parecido. Fallaba: con tantos parecidos parciales ganaba una
# posicion equivocada y los graficos se iban hasta 7 segundos de su sitio.
import difflib

mapa = {}
sm = difflib.SequenceMatcher(None, [w["n"] for w in viejo], [w["n"] for w in nuevo])
for a1, b1, n in sm.get_matching_blocks():
    for k in range(n):
        mapa[a1 + k] = b1 + k


def traducir(t):
    i = next((k for k, w in enumerate(viejo) if w["e"] >= t), len(viejo) - 1)
    # si esa palabra concreta no casa, se busca la mas cercana que si
    for d in range(0, 12):
        for j in (i - d, i + d):
            if j in mapa:
                w_v, w_n = viejo[j], nuevo[mapa[j]]
                return round(w_n["s"] + (t - w_v["s"]), 3), 1.0
    return None, 0.0


faltan = 0
for b in piezas:
    nt, punt = traducir(b["at"])
    if nt is None:
        print(f"  AVISO: no encuentro donde va {b.get('media') or b.get('tipo')} "
              f"({b['at']}s): el contexto no casa", file=sys.stderr)
        faltan += 1
        continue
    print(f"  {(b.get('media') or b.get('text') or b.get('icono') or b.get('tipo'))[:38]:38s}"
          f" {b['at']:7.2f} -> {nt:7.2f}", file=sys.stderr)
    b["at"] = nt

piezas.sort(key=lambda x: x["at"])

# Las frases animadas no se solapan entre si (bin/cuadrar.py ya las resuelve) y su
# duracion la recalcula bin/kw.py, asi que aqui solo hay que moverlas de sitio.
if not es_beats:
    json.dump(piezas, sys.stdout, ensure_ascii=False, indent=1)
    if faltan:
        print(f"  {faltan} sin trasladar: revisalos a mano", file=sys.stderr)
    sys.exit(0)

beats = datos
beats["stingers"] = piezas

# Al comprimirse la linea de tiempo, dos piezas que estaban separadas pueden quedar
# pegadas o superpuestas. Dos clips solapados en la misma pista los rechaza
# 'hyperframes check', asi que se resuelve aqui: manda el que empieza DESPUES (esta
# pegado a su frase) y se acorta el de delante. Si al acortarlo se queda en nada, se
# cae: mejor una pieza menos que un parpadeo.
SEP, MIN = 0.20, 1.20
limpio, fuera = [], []
for i, b in enumerate(beats["stingers"]):
    sig = beats["stingers"][i + 1]["at"] if i + 1 < len(beats["stingers"]) else 1e9
    tope = sig - SEP - b["at"]
    if tope < MIN:
        fuera.append(b)
        print(f"  se cae {b.get('media') or b.get('icono') or b['tipo']} en {b['at']}s: "
              f"solo le quedan {max(0, tope):.2f}s hasta la pieza siguiente", file=sys.stderr)
        continue
    if b["dur"] > tope:
        print(f"  {b.get('media') or b.get('icono') or b['tipo']} acortado "
              f"{b['dur']:.2f} -> {tope:.2f}s para no pisar la pieza siguiente", file=sys.stderr)
        b["dur"] = round(tope, 3)
    limpio.append(b)
beats["stingers"] = limpio

json.dump(beats, sys.stdout, ensure_ascii=False, indent=1)
if faltan:
    print(f"  {faltan} sin trasladar: revisalos a mano", file=sys.stderr)
