#!/usr/bin/env python3
"""transcript de mlx-whisper (json por palabra) -> cues de subtitulo estilo de referencia.

Reglas medidas en referencia1/2/3 + indicaciones del usuario:
  - 2-4 palabras por cue, UNA sola linea, nunca dos.
  - el cue termina EXACTAMENTE donde empieza el siguiente: ni hueco ni solape.
  - NUNCA una frase a medias: un cue no puede terminar en preposicion,
    conjuncion, articulo ni cualquier palabra que exija continuacion.
    Si le toca, esa palabra se empuja al cue siguiente.
  - se corta en puntuacion y en pausa > 0.35s.

Uso: bin/cues.py input/video.json [max_palabras] [max_chars] > output/cues.json
"""
import os, json, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cfg import cfg

MAX_W = int(sys.argv[2]) if len(sys.argv) > 2 else cfg("subtitulo.palabras_max", 4)
MAX_C = int(sys.argv[3]) if len(sys.argv) > 3 else cfg("subtitulo.caracteres_max", 22)
GAP = cfg("subtitulo.pausa_corte", 0.35)

# palabras que no pueden cerrar un cue: dejan la idea colgando
COLGANTES = {
    # preposiciones
    "a", "ante", "bajo", "con", "contra", "de", "desde", "durante", "en", "entre",
    "hacia", "hasta", "mediante", "para", "por", "según", "sin", "sobre", "tras",
    # conjunciones y nexos
    "y", "e", "o", "u", "que", "pero", "sino", "porque", "aunque", "si", "cuando",
    "mientras", "como", "donde", "pues", "ni", "aunque",
    # articulos y determinantes
    "el", "la", "los", "las", "un", "una", "unos", "unas", "lo", "al", "del",
    "mi", "tu", "su", "mis", "tus", "sus", "nuestro", "nuestra", "este", "esta",
    "ese", "esa", "aquel", "aquella", "esos", "esas", "estos", "estas",
    # adverbios/auxiliares que piden complemento
    "no", "más", "menos", "muy", "tan", "ya", "se", "te", "me", "le", "les", "nos",
    "es", "son", "está", "están", "he", "ha", "han", "va", "vas", "van", "puede",
    "puedes", "pueden", "tiene", "tienes", "tienen", "hay",
}


def limpio(t):
    """Sin quitar acentos: "el" (articulo) se puede recortar, "él" (pronombre) no.
    Al normalizarlos igual se perdian palabras del guion."""
    return t.strip(" .,;:!?¿¡…\"'").lower()


data = json.load(open(sys.argv[1]))
words = []
for seg in data.get("segments", []):
    for w in seg.get("words", []):
        t = w.get("word", "").strip()
        if t:
            words.append({"t": t, "s": float(w["start"]), "e": float(w["end"])})


# UN SIGNO SUELTO NO ES UNA PALABRA. Whisper separa "99 %" en dos tokens y el
# troceador los repartia en cues distintos: en pantalla salia "que el 99" y el "%"
# aparecia despues, como si fueran dos ideas. Se pegan al token anterior, igual que
# haria un lector. Vale para %, º, ª y las monedas.
PEGADOS = {"%", "º", "ª", "€", "$", "¢"}


def _juntar_signos(ws):
    salida = []
    for w in ws:
        if w["t"] in PEGADOS and salida:
            salida[-1] = {**salida[-1], "t": salida[-1]["t"] + w["t"], "e": w["e"]}
        else:
            salida.append(w)
    return salida

words = _juntar_signos(words)

if not words:
    sys.exit("El transcript no trae timestamps por palabra "
             "(relanza whisper con --word-timestamps True)")

# --- 1. troceado greedy -------------------------------------------------
grupos, cur = [], []
for i, w in enumerate(words):
    prev_gap = w["s"] - words[i - 1]["e"] if i else 0
    cand = " ".join([x["t"] for x in cur] + [w["t"]])
    if cur and (len(cur) >= MAX_W or len(cand) > MAX_C or prev_gap > GAP):
        grupos.append(cur); cur = []
    cur.append(w)
    if w["t"][-1] in ".,;:!?…":       # la frase manda sobre el conteo
        grupos.append(cur); cur = []
if cur:
    grupos.append(cur)

# --- 2. arreglar frases a medias ---------------------------------------
# mientras el ultimo token de un grupo sea colgante, se empuja al siguiente
cambio = True
while cambio:
    cambio = False
    for i in range(len(grupos) - 1):
        g = grupos[i]
        if len(g) > 1 and limpio(g[-1]["t"]) in COLGANTES:
            grupos[i + 1].insert(0, g.pop())
            cambio = True
# el ultimo grupo no tiene a donde empujar: se fusiona hacia atras
while len(grupos) > 1 and limpio(grupos[-1][-1]["t"]) in COLGANTES and len(grupos[-1]) == 1:
    grupos[-2].extend(grupos.pop())
# un grupo sobrecargado por los empujes se parte por la mitad respetando el limite
final = []
for g in grupos:
    while len(g) > MAX_W + 2:
        final.append(g[:MAX_W]); g = g[MAX_W:]
    if g:
        final.append(g)
grupos = [g for g in final if g]

# --- 2b. fuera los cues demasiado cortos ---------------------------------
# Un cue de 0.2s no da tiempo a leerse: parpadea. Se fusiona con el siguiente.
# Ademas son los que luego chocan con los bloques y acaban perdiendose.
MIN_CUE = cfg("subtitulo.cue_min", 0.38)
i = 0
while i < len(grupos) - 1:
    dura = grupos[i][-1]["e"] - grupos[i][0]["s"]
    if dura < MIN_CUE:
        grupos[i] = grupos[i] + grupos[i + 1]
        del grupos[i + 1]
    else:
        i += 1
if len(grupos) > 1 and grupos[-1][-1]["e"] - grupos[-1][0]["s"] < MIN_CUE:
    # ojo: `grupos[-2] += grupos.pop()` escribe en el elemento equivocado, porque
    # el indice se resuelve DESPUES del pop. Duplicaba el ultimo cue y perdia
    # palabras del anterior.
    ultimo = grupos.pop()
    grupos[-1] = grupos[-1] + ultimo

cues = [{"text": " ".join(w["t"] for w in g),
         "start": round(g[0]["s"], 3),
         "end": round(g[-1]["e"], 3),
         "key": False} for g in grupos]

# --- 3. continuidad total: cada cue dura hasta que empieza el siguiente --
# Sin huecos y sin solapes. Donde termina uno empieza el otro, aunque en medio
# haya una pausa al hablar: la pantalla nunca se queda sin subtitulo.
# (Los unicos huecos los abren los motion graphics, que se tratan aparte.)
for i, c in enumerate(cues[:-1]):
    c["end"] = cues[i + 1]["start"]

json.dump(cues, sys.stdout, ensure_ascii=False, indent=1)
