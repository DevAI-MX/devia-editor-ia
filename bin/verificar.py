#!/usr/bin/env python3
"""Ningun texto en pantalla puede ser inventado.

Todo lo que aparece escrito tiene que ser algo que se dice de verdad en el video.
Este script coge cada cadena de keywords.json y beats.json y comprueba que su
secuencia de palabras aparece tal cual en el transcript. Si no, aborta el montaje
y dice cual es la frase inventada.

Unica excepcion: el gancho fijo de cabecera (`hook` en beats.json), que es un
titular de portada y no tiene por que estar dicho.

Uso: bin/verificar.py transcript.json keywords.json beats.json
"""
import json, sys, unicodedata


def tokens(t):
    t = unicodedata.normalize("NFD", t.lower())
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    return ["".join(c for c in p if c.isalnum()) for p in t.split() if any(c.isalnum() for c in p)]


trans = json.load(open(sys.argv[1]))
dichas = []
for seg in trans.get("segments", []):
    for w in seg.get("words", []):
        dichas += tokens(w.get("word", ""))

keys = json.load(open(sys.argv[2])) if len(sys.argv) > 2 and sys.argv[2] else []
beats = json.load(open(sys.argv[3])) if len(sys.argv) > 3 and sys.argv[3] else {}


def esta_dicho(texto):
    t = tokens(texto)
    if not t:
        return True
    for i in range(len(dichas) - len(t) + 1):
        if dichas[i:i + len(t)] == t:
            return True
    return False


inventados = []


def revisar(texto, donde):
    if texto and not esta_dicho(texto):
        inventados.append((donde, texto))


for k in keys:
    revisar(k.get("text"), f"keyword @{k.get('at')}s")

for b in beats.get("stingers", []):
    for campo in ("kicker", "titular", "desc"):
        revisar(b.get(campo), f"stinger {b.get('tipo')} @{b.get('at')}s [{campo}]")

# Editorial: las lineas de la ficha de color, los bloques del titulo del gancho
# y los rotulos de lista tambien son texto en pantalla -> tambien tienen que decirse.
# Las lineas del titulo se comprueban JUNTAS ademas de una a una: el titulo entero es
# una frase del habla partida en renglones, no renglones sueltos.
for b in beats.get("stingers", []):
    if b.get("tipo") == "color":
        for i, l in enumerate(b.get("lineas", [])):
            t = l if isinstance(l, str) else l.get("t")
            revisar(t, f"ficha de color @{b.get('at')}s [linea {i+1}]")
for bi, bl in enumerate((beats.get("gancho") or {}).get("bloques", [])):
    lns = [l.get("t", "") for l in bl.get("lineas", [])]
    for i, t in enumerate(lns):
        revisar(t, f"titulo del gancho bloque {bi+1} [linea {i+1}]")
    revisar(" ".join(lns), f"titulo del gancho bloque {bi+1} [las lineas juntas]")
for r in beats.get("rotulos", []) if isinstance(beats, dict) else []:
    revisar(r.get("txt"), f"rotulo @{r.get('at')}s")

for l in beats.get("listas", []):
    for i, it in enumerate(l.get("items", [])):
        revisar(it.get("tit"), f"lista item {i+1} [tit]")
        revisar(it.get("sub"), f"lista item {i+1} [sub]")

if inventados:
    print("ERROR: hay texto en pantalla que no se dice en el video.", file=sys.stderr)
    print("Todo el texto tiene que salir del transcript (excepto el gancho fijo).",
          file=sys.stderr)
    for donde, texto in inventados:
        print(f"  {donde}: \"{texto}\"", file=sys.stderr)
    sys.exit(1)

n = (len(keys) + sum(1 for b in beats.get("stingers", []) for c in ("kicker", "titular", "desc") if b.get(c))
     + sum(len(b.get("lineas", [])) for b in beats.get("stingers", []) if b.get("tipo") == "color")
     + sum(len(bl.get("lineas", [])) for bl in (beats.get("gancho") or {}).get("bloques", []))
     + len(beats.get("rotulos", []) if isinstance(beats, dict) else []))
print(f"  texto verificado: {n} cadenas, todas dichas en el video", file=sys.stderr)
