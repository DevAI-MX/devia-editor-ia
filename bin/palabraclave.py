#!/usr/bin/env python3
"""Detecta la palabra clave del CTA y la fija en pantalla hasta el final.

Cuando el video pide "comenta X y te mando Y", esa palabra X es lo unico que el
espectador tiene que recordar. Si solo aparece en el subtitulo que pasa en un
segundo, se pierde: hay que dejarla fija, grande y en amarillo, desde que se dice
hasta que acaba el video.

Detecta el verbo de llamada (comenta, escribe, manda, pon, teclea, di) y toma la
palabra siguiente, saltandose los articulos y el "la palabra".

Uso: bin/palabraclave.py transcript.json <duracion> > palabra.json
"""
import json, sys, unicodedata

VERBOS = {"comenta", "comentame", "comentas", "escribe", "escribeme", "manda",
          "mandame", "pon", "ponme", "teclea", "di", "dime", "responde", "contesta"}
SALTAR = {"la", "el", "me", "un", "una", "palabra", "en", "los", "comentarios",
          "abajo", "aqui", "ya", "solo", "y", "por"}


def norm(t):
    t = unicodedata.normalize("NFD", t.lower())
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    return "".join(c for c in t if c.isalnum())


trans = json.load(open(sys.argv[1]))
dur = float(sys.argv[2])

palabras = []
for seg in trans.get("segments", []):
    for w in seg.get("words", []):
        t = w.get("word", "").strip()
        if t:
            palabras.append({"t": t, "n": norm(t), "s": float(w["start"])})

def tras(i):
    """la primera palabra con contenido despues del verbo"""
    for j in range(i + 1, min(i + 5, len(palabras))):
        c = palabras[j]
        if c["n"] and c["n"] not in SALTAR:
            return c
    return None


# El verbo suelto no basta. "pon proteina en todas tus comidas" lleva "pon", que
# esta en la lista, y en el primer video se llevaba la palabra clave al minuto 48:
# el CTA quedaba fijado en "proteina" durante todo el video.
#
# Dos filtros, en este orden:
#   1. el patron completo "<verbo> la PALABRA x" — es como se escribe un CTA de
#      verdad, y no hay frase normal que lo lleve por casualidad;
#   2. si no aparece, el ultimo verbo del tramo final (el CTA va al final, nunca
#      a mitad de la explicacion).
marcadas = []
for i, p in enumerate(palabras):
    if p["n"] not in VERBOS:
        continue
    marcador = any(palabras[j]["n"] == "palabra"
                   for j in range(i + 1, min(i + 4, len(palabras))))
    cand = tras(i)
    if cand:
        marcadas.append((marcador, p, cand))

con_marcador = [m for m in marcadas if m[0]]
if con_marcador:
    _, verbo, cand = con_marcador[-1]
else:
    tarde = [m for m in marcadas if m[1]["s"] >= dur * 0.6]
    verbo, cand = (tarde or marcadas or [(None, None, None)])[-1][1:]

hallada = None
if cand:
    hallada = {"palabra": cand["t"].strip(".,;:!?¿¡"),
               "desde": round(cand["s"], 3),
               "hasta": round(dur, 3),
               "dicho_por": verbo["t"].strip(".,;:!?¿¡")}

if hallada:
    print(f"  palabra clave: \"{hallada['palabra']}\" (tras \"{hallada['dicho_por']}\") "
          f"fija desde {hallada['desde']:.2f}s hasta el final", file=sys.stderr)
else:
    print("  sin palabra clave de CTA en el guion", file=sys.stderr)

json.dump(hallada or {}, sys.stdout, ensure_ascii=False, indent=1)
