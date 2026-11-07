#!/usr/bin/env python3
"""El texto de un motion graphic ES lo que se dice mientras dura.

Antes yo elegia un `titular` y el resto de lo que sonaba durante el grafico no
aparecia en ninguna parte: se oia hablar sin texto en pantalla, o el texto salia
antes o despues. Con 3s de grafico eso pasaba muchas veces.

Ahora el titular se COMPONE con las palabras del transcript que caen dentro de la
ventana del grafico, con su tiempo real. Asi cada palabra aparece justo cuando se
dice y no se pierde ninguna. El `titular` escrito a mano pasa a ser opcional: si
esta, se respeta (y entonces la ventana se ajusta a esa frase).

Uso: bin/textograf.py beats.json transcript.json > beats_con_texto.json
"""
import os, json, sys, unicodedata
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cfg import cfg

# el texto del grafico tampoco puede terminar colgando
COLGANTES = {
    "a", "ante", "bajo", "con", "contra", "de", "desde", "durante", "en", "entre",
    "hacia", "hasta", "mediante", "para", "por", "según", "sin", "sobre", "tras",
    "y", "e", "o", "u", "ni", "que", "pero", "sino", "porque", "aunque", "si",
    "cuando", "mientras", "como", "donde", "pues", "el", "la", "los", "las", "un",
    "una", "unos", "unas", "lo", "al", "del", "mi", "tu", "su", "mis", "tus", "sus",
    "este", "esta", "ese", "esa", "no", "ya", "se", "te", "me", "le", "les", "nos",
    "más", "menos", "muy", "tan", "es", "son",
}


def limpio(t):
    t = unicodedata.normalize("NFD", t.lower())
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    return "".join(c for c in t if c.isalnum())

beats = json.load(open(sys.argv[1]))
trans = json.load(open(sys.argv[2]))

palabras = []
for seg in trans.get("segments", []):
    for w in seg.get("words", []):
        t = w.get("word", "").strip()
        if t:
            palabras.append({"t": t, "s": float(w["start"]), "e": float(w["end"])})

for b in beats.get("stingers", []):
    if b.get("tipo") == "broll":
        continue                      # el b-roll no lleva texto: van los subtitulos
    if b.get("tipo") == "color":
        continue                      # la ficha de color trae sus lineas escritas a mano
    if b.get("titular"):
        continue                      # titular escrito a mano: manda
    a, z = b["at"], b["at"] + b["dur"]
    # palabras cuyo centro cae dentro de la ventana del grafico
    dentro = [p for p in palabras if a <= (p["s"] + p["e"]) / 2 < z]
    if not dentro:
        print(f"  AVISO: el grafico de {a:.2f}s no cubre ninguna palabra", file=sys.stderr)
        continue
    # La ventana no puede acabar en conector: "tus intenciones e" no es una frase.
    # Se recorta el grafico hasta la ultima palabra con contenido; lo que sobra
    # vuelve a los subtitulos normales, que es donde tiene que verse.
    while len(dentro) > 1 and limpio(dentro[-1]["t"]) in COLGANTES:
        dentro.pop()
    b["titular"] = " ".join(p["t"] for p in dentro)
    b["palabras"] = [{"t": p["t"], "at": round(p["s"], 3)} for p in dentro]
    # el grafico se va en cuanto termina su ultima palabra: si se queda de mas,
    # tapa lo que ya se esta diciendo y el texto siguiente llega tarde
    b["dur"] = round(dentro[-1]["e"] + cfg("graficos_texto.cierre", 0.08) - b["at"], 3)
    b["hold"] = 0.08
    b["_auto"] = True
    print(f"  grafico {a:5.2f}-{z:5.2f} dice: \"{b['titular']}\"", file=sys.stderr)

json.dump(beats, sys.stdout, ensure_ascii=False, indent=1)
