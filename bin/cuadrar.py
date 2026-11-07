#!/usr/bin/env python3
"""Resuelve los subtitulos contra los bloques ANTES de renderizar.

Antes esto se hacia dentro de la plantilla, en tiempo de render, y por eso se
perdian palabras sin que nadie se enterara. Ahora se decide aqui, se puede auditar,
y la plantilla solo dibuja lo que recibe.

Reglas:
  - un cue tapado en parte se recorta;
  - si lo que queda es demasiado corto para leerse (<0.30s), NO se tira: sus
    palabras se pegan al cue vecino que si se ve, para que no desaparezcan;
  - un cue tapado del todo cede sus palabras al vecino, salvo que el bloque que lo
    tapa ya diga esas mismas palabras (entonces ya se ven, en grande).

Uso: bin/cuadrar.py cues.json keywords.json beats.json > cues_finales.json
"""
import os, json, sys, unicodedata
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cfg import cfg

MIN_LEGIBLE = cfg("subtitulo.cue_legible", 0.30)
SALIDA_KW = cfg("bloque.salida", 0.16)
MARGEN = cfg("bloque.margen_tras_salida", 0.04)
MAX_PALABRAS = 6        # un cue rescatado no puede convertirse en un parrafo

# Las palabras rescatadas se pegan al cue vecino, pero el resultado tiene que
# seguir leyendose como una frase: ni terminar colgando en preposicion o
# articulo, ni juntar dos ideas que no tienen que ver.
COLGANTES = {
    "a", "ante", "bajo", "con", "contra", "de", "desde", "durante", "en", "entre",
    "hacia", "hasta", "mediante", "para", "por", "según", "sin", "sobre", "tras",
    "y", "e", "o", "u", "que", "pero", "sino", "porque", "aunque", "si", "cuando",
    "mientras", "como", "donde", "pues", "ni", "el", "la", "los", "las", "un",
    "una", "unos", "unas", "lo", "al", "del", "mi", "tu", "su", "mis", "tus",
    "sus", "este", "esta", "ese", "esa", "no", "más", "menos", "muy", "tan",
    "ya", "se", "te", "me", "le", "les", "nos",
}


def colgante(w):
    """Quita solo puntuacion y mayusculas, NO acentos: "el" es articulo y se
    puede recortar, pero "él" es pronombre y forma parte de la frase. Quitando
    el acento los dos se veian iguales y se perdian palabras."""
    return w.lower().strip(".,;:!?¿¡…\"'") in COLGANTES




def sin_puntos(t):
    """Fuera los puntos. En pantalla un punto final no aporta nada (el cue ya
    termina ahi) y ensucia el remate de la frase, sobre todo con los puntos
    suspensivos. Las comas se quedan: esas si marcan el fraseo al leer."""
    return t.replace("...", "").replace("…", "").replace(".", "").strip()


def coherente(palabras):
    """No deja la frase colgando ni la convierte en un parrafo."""
    ws = list(palabras)
    # si la frase anterior ya cerro con punto, no se arrastra al cue siguiente
    for i in range(len(ws) - 1):
        if ws[i].endswith((".", "?", "!", "…")) and i + 1 < len(ws):
            pass
    # NO se recortan palabras por longitud: perder texto es peor que un cue largo,
    # y el cuerpo de letra ya se ajusta solo. Solo se evita el final colgando, y
    # aun asi lo que se quita se devuelve al final para que no desaparezca.
    sobra = []
    while len(ws) > 1 and colgante(ws[-1]):
        sobra.insert(0, ws.pop())
    return ws + sobra if len(ws) < 2 else ws + (sobra if sobra and len(ws) > 4 else sobra)


def norm(t):
    t = unicodedata.normalize("NFD", t.lower())
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    return "".join(c for c in t if c.isalnum())


cues = json.load(open(sys.argv[1]))
kws = json.load(open(sys.argv[2])) if len(sys.argv) > 2 and sys.argv[2] else []
beats = json.load(open(sys.argv[3])) if len(sys.argv) > 3 and sys.argv[3] else {"stingers": []}
salida_kws = sys.argv[4] if len(sys.argv) > 4 else None
stg = beats.get("stingers", [])

# --- primero: que ninguna frase animada deje un subtitulo sin tiempo ------
# Mover palabras a un cue posterior las saca de sincronia con el audio (se leen
# despues de oirse, y eso canta). Es mejor ACORTAR la frase animada lo justo para
# que el subtitulo siguiente sobreviva en su propio sitio.
# margen minimo tras la ultima palabra de la frase animada. Con 0.30 no habia
# sitio para acortarla y quedaba solapada con el subtitulo siguiente; 0.12 sigue
# dejando leerla y evita que se pisen.
HOLD_MIN = 0.12
for k in kws:
    ult = max((p["at"] for p in k.get("palabras", [])), default=k["at"])
    minimo_fin = ult + HOLD_MIN
    fin = k["at"] + k["dur"] + SALIDA_KW + MARGEN
    propias = {norm(x) for x in k["text"].split()}
    for c in cues:
        if c["start"] < k["at"] or c["end"] <= k["at"]:
            continue                                  # empieza antes: no le afecta el final
        if {norm(x) for x in c["text"].split()} <= propias:
            continue                                  # es el propio texto de la frase
        if c["start"] >= fin:
            break                                     # ya no lo alcanza
        if fin >= c["end"]:
            objetivo = c["start"]                     # lo tapa ENTERO
        elif c["end"] - fin < MIN_LEGIBLE:
            objetivo = c["end"] - MIN_LEGIBLE         # le deja un resto ilegible
        else:
            break                                     # le queda tiempo de sobra
        if objetivo >= minimo_fin:
            k["dur"] = round(objetivo - k["at"] - SALIDA_KW - MARGEN, 3)
            print(f"  frase '{k['text']}' acortada a {k['dur']:.2f}s para que "
                  f"'{c['text']}' se lea en su sitio y a tiempo", file=sys.stderr)
        else:
            print(f"  AVISO: '{c['text']}' queda tapado por '{k['text']}' y no se "
                  f"puede acortar mas sin comerse la propia frase", file=sys.stderr)
        break

# una frase animada que choca con un grafico no se muestra: manda el grafico
kws_vis = [k for k in kws
           if not any(k["at"] < b["at"] + b["dur"] and k["at"] + k["dur"] > b["at"]
                      for b in stg if b.get("tipo") != "broll")]

# El bloque sigue en pantalla hasta que la ULTIMA palabra ha terminado de aparecer:
# la plantilla no deja que la salida se cruce con la entrada (si se cruzan, la palabra
# se queda encendida para siempre). Aqui hay que usar el mismo final o el subtitulo
# siguiente se coloca encima del bloque todavia visible.
ENTRA_KW = 0.30


def fin_real(k):
    ult = max([k["at"]] + [p["at"] for p in k.get("palabras", [])])
    return max(k["at"] + k["dur"], ult + ENTRA_KW + 0.04) + SALIDA_KW + MARGEN


bloques = ([(k["at"], fin_real(k),
             {norm(x) for x in k["text"].split()}) for k in kws_vis]
           # El B-ROLL no bloquea los subtitulos: es material que va DEBAJO de la
           # narracion, como en cualquier edicion. Solo los motion graphics, que
           # traen su propio texto, se quedan con el hueco.
           + [(b["at"], b["at"] + b["dur"],
               {norm(x) for x in (b.get("titular") or "").split()})
              for b in stg if b.get("tipo") != "broll"])
bloques.sort()

salida, notas = [], []

# NO se rescatan palabras hacia otro cue. Antes, si un bloque tapaba un subtitulo,
# sus palabras se pegaban al cue siguiente: el resultado eran frases concatenadas
# fuera de orden y fuera de su momento ("es Si ni siquiera mismo te traes que hagan
# las mujeres?"). El texto tiene que salir CUANDO se dice o no salir.
# Si algo se pierde, lo canta bin/auditar.py y se arregla ajustando el bloque.
for c in cues:
    a, b_ = c["start"], c["end"]
    tapado = False
    for oa, ob, dice in bloques:
        if ob <= a or oa >= b_:
            continue
        if oa <= a and ob >= b_:
            tapado = True; break
        if oa <= a: a = ob
        elif ob >= b_: b_ = oa
        else:
            if b_ - oa >= ob - a: b_ = oa
            else: a = ob

    if tapado:
        faltan = [w for w in c["text"].split() if norm(w) not in dice]
        if faltan:
            notas.append(f"'{c['text']}' tapado del todo por un bloque que no lo dice")
        continue
    if b_ - a < MIN_LEGIBLE:
        notas.append(f"'{c['text']}' se queda en {b_ - a:.2f}s y no da tiempo a leerlo")
        continue
    salida.append({**c, "text": sin_puntos(" ".join(coherente(c["text"].split()))),
                   "start": round(a, 3), "end": round(b_, 3)})

# se guardan las frases con su duracion ya acortada: sin esto el render usaba la
# duracion original y la frase seguia solapando el subtitulo siguiente
if salida_kws:
    json.dump(kws, open(salida_kws, "w"), ensure_ascii=False, indent=1)

json.dump(salida, sys.stdout, ensure_ascii=False, indent=1)
for n in notas:
    print(f"  {n}", file=sys.stderr)
print(f"  cues: {len(cues)} -> {len(salida)}", file=sys.stderr)
