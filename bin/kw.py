#!/usr/bin/env python3
"""Da timing por PALABRA a cada keyword, alineado al transcript.

Las keywords salen palabra por palabra. Si la palabra aparece justo cuando se dice,
el efecto engancha; si va a destiempo, se nota falso. Por eso se busca cada palabra
de la keyword en el transcript dentro de su ventana y se usa el tiempo real de habla.
Si la keyword es una parafrasis y no casa con lo dicho, se reparte uniformemente.

Uso: bin/kw.py transcript.json keywords.json > keywords_timed.json
"""
import json, os, sys, unicodedata
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cfg import cfg


def norm(t):
    t = unicodedata.normalize("NFD", t.lower())
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    return "".join(c for c in t if c.isalnum())


data = json.load(open(sys.argv[1]))
keys = json.load(open(sys.argv[2]))

palabras = []
for seg in data.get("segments", []):
    for w in seg.get("words", []):
        t = w.get("word", "").strip()
        if t:
            palabras.append({"n": norm(t), "s": float(w["start"]), "e": float(w["end"])})

def casa(a, b):
    return a == b or (len(b) > 4 and a.startswith(b[:5]))


for k in keys:
    trozos = k["text"].split()
    objetivo = [norm(t) for t in trozos]

    # Se busca la frase en TODO el transcript, no en una ventana alrededor de `at`.
    # Con ventana, al volver a cortar el video (que mueve todo lo que viene detras)
    # la frase dejaba de encontrarse y se repartia uniformemente en el sitio viejo:
    # el bloque salia a destiempo y tapaba subtitulos que no decia.
    # `at` pasa a ser una PISTA: entre dos apariciones de la misma frase, gana la
    # que caiga mas cerca de donde se pidio.
    mejor, mejor_punt = None, 0
    for j in range(len(palabras) - len(objetivo) + 1):
        punt = sum(1 for x, o in enumerate(objetivo)
                   if casa(palabras[j + x]["n"], o))
        if punt < len(objetivo):
            continue
        cerca = -abs(palabras[j]["s"] - k["at"])
        if mejor is None or cerca > mejor_punt:
            mejor, mejor_punt = j, cerca

    if mejor is not None:
        tiempos = [round(palabras[mejor + x]["s"], 3) for x in range(len(objetivo))]
        k["origen"] = "transcript"
    else:
        # reparto uniforme en el 65% inicial de la ventana: deja aire al final
        paso = (k["dur"] * 0.65) / max(1, len(trozos))
        tiempos = [round(k["at"] + x * paso, 3) for x in range(len(trozos))]
        k["origen"] = "uniforme"

    # nunca demasiado juntas ni demasiado separadas: 0.10s minimo, 0.55s maximo
    for x in range(1, len(tiempos)):
        tiempos[x] = max(tiempos[x], tiempos[x - 1] + 0.10)
        tiempos[x] = min(tiempos[x], tiempos[x - 1] + 0.55)
    k["at"] = tiempos[0]
    k["palabras"] = [{"t": trozos[x], "at": tiempos[x]} for x in range(len(trozos))]

    # La ventana tiene que cubrir hasta la ULTIMA palabra y dejarla leerse.
    # Si no, las ultimas se revelaban justo cuando la frase ya se estaba yendo.
    # Pero pasarse tampoco vale: con 0.6s el bloque seguia en pantalla cuando ya
    # habia empezado la frase siguiente y se llevaba por delante su subtitulo.
    hold = k.get("hold", cfg("bloque.hold_kw", 0.6))
    minimo = tiempos[-1] - k["at"] + hold
    if k["dur"] < minimo:
        k["dur"] = round(minimo, 3)
        k["ajustado"] = True

json.dump(keys, sys.stdout, ensure_ascii=False, indent=1)
print("", file=sys.stderr)
for k in keys:
    extra = "  (ventana ampliada a %.2fs para que quepa la frase)" % k["dur"] if k.get("ajustado") else ""
    print(f"  keyword '{k['text']}' -> {len(k['palabras'])} palabras, timing {k['origen']}{extra}",
          file=sys.stderr)
