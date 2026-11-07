#!/usr/bin/env python3
"""Alinea cada motion graphic con el momento en que se dice su frase.

Colocar los stingers a mano por timestamp es la fuente principal de desfase: el
grafico entra antes o despues de que la frase suene. Aqui el `at` declarado pasa a
ser solo una PISTA de en que zona del video se quiere el grafico; el instante exacto
sale del transcript.

Ademas se da timing por palabra al texto del grafico (igual que a las frases
animadas) y se garantiza que el grafico dure lo suficiente para cubrir la frase
entera mas un margen de lectura.

Uso: bin/alinear.py beats.json transcript.json > beats_alineados.json
"""
import os, json, sys, unicodedata
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cfg import cfg

beats = json.load(open(sys.argv[1]))
trans = json.load(open(sys.argv[2]))
HOLD = cfg("bloque.hold", 0.45)          # cuanto se queda el grafico tras la ultima palabra
ADELANTO = cfg("bloque.adelanto", 0.10)      # entra un pelo antes de la primera palabra


def norm(t):
    t = unicodedata.normalize("NFD", t.lower())
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    return "".join(c for c in t if c.isalnum())


palabras = []
for seg in trans.get("segments", []):
    for w in seg.get("words", []):
        t = w.get("word", "").strip()
        if t:
            palabras.append({"t": t, "n": norm(t), "s": float(w["start"]), "e": float(w["end"])})

for b in beats.get("stingers", []):
    txt = b.get("titular")
    if not txt:
        continue
    obj = [norm(x) for x in txt.split()]
    mejor, dist = None, 1e9
    for i in range(len(palabras) - len(obj) + 1):
        if [p["n"] for p in palabras[i:i + len(obj)]] == obj:
            d = abs(palabras[i]["s"] - b["at"])
            if d < dist:
                mejor, dist = i, d
    if mejor is None:
        print(f"  AVISO: '{txt}' no se dice literalmente; el grafico se queda donde estaba",
              file=sys.stderr)
        continue

    trozo = palabras[mejor:mejor + len(obj)]
    nuevo_at = round(max(0.0, trozo[0]["s"] - ADELANTO), 3)
    # `hold` por grafico: cuando justo detras viene habla que tiene que verse,
    # el grafico no puede quedarse 0.45s de mas o se la come
    hold = b.get("hold", HOLD)
    minimo = round(trozo[-1]["e"] + hold - nuevo_at, 3)
    movido = round(nuevo_at - b["at"], 3)
    b["at"] = nuevo_at
    if b["dur"] < minimo:
        b["dur"] = minimo
    # el texto del grafico entra palabra por palabra, al ritmo real del habla
    b["palabras"] = [{"t": p["t"], "at": round(p["s"], 3)} for p in trozo]
    if abs(movido) > 0.05:
        print(f"  grafico '{txt}' movido {movido:+.2f}s -> entra en {nuevo_at:.2f}s "
              f"(cuando se dice)", file=sys.stderr)

json.dump(beats, sys.stdout, ensure_ascii=False, indent=1)
