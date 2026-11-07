#!/usr/bin/env python3
"""Reserva para el motion graphic las palabras que va a mostrar.

El problema: si el subtitulo normal ya dijo "con que seas introvertido" y acto
seguido el motion graphic muestra "introvertido o timido", la palabra llega gastada.
El enfasis esta en el bloque, asi que la palabra tiene que aparecer ALLI por
primera vez.

Vale igual para los motion graphics y para las FRASES ANIMADAS. Sin esto, la frase
que el bloque acaba de mostrar reaparecia entera en un subtitulo un segundo despues
y ademas fuera de su momento, porque al quedar tapada se rescataba hacia el cue
siguiente. Se ve como un tartamudeo de texto.

Solo se quitan las palabras de ESA aparicion concreta (se localiza el rango exacto
en el transcript, el mas cercano al bloque). Que "que" o "ella" vuelvan a salir mas
adelante no es repeticion: es la misma palabra en otra frase.

La regla: cualquier palabra que un stinger vaya a mostrar se borra de los subtitulos
normales que van ANTES de ese stinger. El cue se recorta (nunca se reordena) y, si
al recortarlo queda colgando en preposicion o articulo, se recorta un poco mas.
Si un cue se queda sin nada, desaparece y su tiempo se lo queda el anterior.

Uso: bin/reservar.py cues.json beats.json transcript.json [keywords.json] > cues.json
"""
import json, sys, unicodedata

COLGANTES = {
    "a", "ante", "bajo", "con", "contra", "de", "desde", "durante", "en", "entre",
    "hacia", "hasta", "mediante", "para", "por", "según", "sin", "sobre", "tras",
    "y", "e", "o", "u", "que", "pero", "sino", "porque", "aunque", "si", "cuando",
    "mientras", "como", "donde", "pues", "ni",
    "el", "la", "los", "las", "un", "una", "unos", "unas", "lo", "al", "del",
    "mi", "tu", "su", "mis", "tus", "sus", "este", "esta", "ese", "esa",
    "no", "más", "menos", "muy", "tan", "ya", "se", "te", "me", "le", "les", "nos",
}


def colgante(w):
    """Quita solo puntuacion y mayusculas, NO acentos: "el" es articulo y se
    puede recortar, pero "él" es pronombre y forma parte de la frase. Quitando
    el acento los dos se veian iguales y se perdian palabras."""
    return w.lower().strip(".,;:!?¿¡…\"'") in COLGANTES




def norm(t):
    t = unicodedata.normalize("NFD", t.lower())
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    return "".join(c for c in t if c.isalnum())


cues = json.load(open(sys.argv[1]))
beats = json.load(open(sys.argv[2])) if sys.argv[2] else {"stingers": []}
trans = json.load(open(sys.argv[3]))
kws = json.load(open(sys.argv[4])) if len(sys.argv) > 4 and sys.argv[4] else []

palabras = []
for seg in trans.get("segments", []):
    for w in seg.get("words", []):
        t = w.get("word", "").strip()
        if t:
            palabras.append({"t": t, "n": norm(t), "s": float(w["start"])})

# --- que rango de palabras se lleva cada stinger --------------------------
reservadas = {}          # indice de palabra -> instante del bloque que la usa
bloques = ([{"txt": b.get("titular"), "at": b["at"]} for b in beats.get("stingers", [])]
           + [{"txt": k.get("text"), "at": k["at"]} for k in kws])
for b in bloques:
    txt = b.get("txt")
    if not txt:
        continue
    objetivo = [norm(x) for x in txt.split()]
    mejor, dist = None, 1e9
    for i in range(len(palabras) - len(objetivo) + 1):
        if [p["n"] for p in palabras[i:i + len(objetivo)]] == objetivo:
            d = abs(palabras[i]["s"] - b["at"])
            if d < dist:
                mejor, dist = i, d
    if mejor is None:
        continue
    for j in range(mejor, mejor + len(objetivo)):
        reservadas[j] = min(reservadas.get(j, 1e9), b["at"])

quitadas = []
salida = []
for c in cues:
    # las palabras del transcript que caen dentro de este cue
    idx = [i for i, p in enumerate(palabras) if c["start"] <= p["s"] < c["end"]]
    texto = c["text"].split()
    # se alinean por posicion: el cue se construyo con esas mismas palabras
    reservado_aqui = False
    if len(idx) == len(texto):
        conservar = []
        for k, i in enumerate(idx):
            if i not in reservadas:
                conservar.append(texto[k])
                continue
            quitadas.append(texto[k])
            reservado_aqui = True
            if reservadas[i] >= c["start"]:
                # el grafico viene DESPUES: todo lo que sigue en el cue es su cita,
                # asi que se corta aqui y el bloque la estrena
                break
            # el grafico viene ANTES y ya enseño esta palabra. Repetirla en el
            # subtitulo justo detras se lee como un tartamudeo ('tus estrogenos'
            # en el bloque y otra vez en el cue 0.2s despues). Se quita SOLO ella:
            # cortar el resto se llevaria por delante palabras que el bloque no dice.
        texto = conservar
    # que no quede colgando tras el recorte
    while len(texto) > 1 and colgante(texto[-1]):
        texto.pop()
    if texto and norm(texto[0]) not in ("",):
        salida.append({**c, "text": " ".join(texto)})
    elif salida and not reservado_aqui:
        salida[-1]["end"] = c["end"]          # su tiempo se lo queda el anterior
    # Si el cue se quedo vacio porque un BLOQUE se lleva sus palabras, su tiempo NO
    # pasa al cue anterior: ese tramo va a estar ocupado por el bloque, y estirar el
    # anterior hasta ahi hacia que despues bin/cuadrar.py lo recortara y lo tirara
    # entero. Se perdia un subtitulo que no tenia nada que ver ('y llorando en la
    # cama' desaparecia porque el bloque de al lado se habia llevado el cue de
    # detras).

# Continuidad: sin huecos tras los borrados. PERO un cue no puede estirarse por
# encima de un bloque. Cuando el bloque se llevaba las palabras de los cues de
# detras, esta linea estiraba el cue anterior hasta el siguiente superviviente —
# es decir, por encima del bloque entero — y despues bin/cuadrar.py lo recortaba y
# lo tiraba por corto. Se perdia un subtitulo que no tenia nada que ver: 'y
# llorando en la cama' desaparecia porque el bloque de al lado se habia comido el
# cue de detras.
arranques = sorted([b["at"] for b in bloques if b.get("txt")])
# ...ni por encima del titulo del gancho o de una italica (ventanas de gancho.py):
# ahi las palabras ya estan escritas en otro sitio y el hueco es a proposito.
import os as _os
_vp = _os.environ.get("VENTANAS_JSON", "")
if _vp and _os.path.exists(_vp):
    arranques = sorted(arranques + [float(v[0]) for v in json.load(open(_vp))])
for i in range(len(salida) - 1):
    tope = salida[i + 1]["start"]
    for a_ in arranques:
        if salida[i]["end"] <= a_ < tope:
            tope = a_
            break
    salida[i]["end"] = round(tope, 3)

json.dump(salida, sys.stdout, ensure_ascii=False, indent=1)

if quitadas:
    print(f"  reservadas para el motion graphic: {', '.join(dict.fromkeys(quitadas))}",
          file=sys.stderr)
    print(f"  cues: {len(cues)} -> {len(salida)}", file=sys.stderr)
