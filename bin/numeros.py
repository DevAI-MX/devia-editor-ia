#!/usr/bin/env python3
"""Saca los puntos numerados del guion para ponerlos en grande arriba.

En un video de lista ("la numero 1", "hack numero 2", "numero tres") el espectador
necesita saber en que punto va sin tener que reconstruirlo del audio. El numero
aparece arriba, en grande, cuando se dice, y se queda hasta el punto siguiente.

Se detecta la pareja <numero|hack|paso|senal|tip|error|razon|clave|regla> + digito o
numero escrito. Whisper a veces escribe "1" y a veces "uno", asi que se aceptan las
dos formas.

Uso: bin/numeros.py transcript.json <duracion> > numeros.json
"""
import json, re, sys, unicodedata

PALABRA = {"uno": 1, "una": 1, "dos": 2, "tres": 3, "cuatro": 4, "cinco": 5,
           "seis": 6, "siete": 7, "ocho": 8, "nueve": 9, "diez": 10,
           "primero": 1, "primera": 1, "segundo": 2, "segunda": 2, "tercero": 3,
           "tercera": 3, "cuarto": 4, "cuarta": 4, "quinto": 5, "quinta": 5}
# "numero" y sus variantes mal transcritas; tambien los ordinales sueltos
MARCA = {"numero", "hack", "paso", "senal", "tip", "error", "razon", "clave", "regla",
         "hap", "acto", "punto"}
SUELTOS = {"primero", "primera", "segundo", "segunda", "tercero", "tercera",
           "cuarto", "cuarta", "quinto", "quinta"}


def norm(t):
    t = unicodedata.normalize("NFD", t.lower())
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]", "", t)


trans = json.load(open(sys.argv[1]))
dur = float(sys.argv[2])

palabras = [{"t": w["word"].strip(), "n": norm(w["word"]), "s": float(w["start"])}
            for seg in trans.get("segments", []) for w in seg.get("words", [])
            if w.get("word", "").strip()]

# Se recogen por separado los dos patrones. Si el guion usa "numero N" en algun
# sitio, ESE es su sistema de numeracion y los ordinales sueltos se ignoran: en un
# video con "Numero 2" tambien aparece "primero fibra, segundo proteina" dentro de un
# punto, y esa enumeracion interna no es un punto de la lista.
con_marca, sueltos = [], []
i = 0
while i < len(palabras):
    p = palabras[i]
    if p["n"] in MARCA:
        for j in range(i + 1, min(i + 3, len(palabras))):
            c = palabras[j]["n"]
            n = int(c) if c.isdigit() else PALABRA.get(c)
            if n:
                con_marca.append({"at": round(p["s"], 3), "n": n})
                i = j
                break
    elif p["n"] in SUELTOS:
        # solo si abre frase: "Primero, pon proteina" si; "atacar primero" no
        # abre frase directamente, o detras de un "y"/"pero" que a su vez abre frase:
        # "Y cuarto, deja de llegar a la noche..." sigue siendo un punto de la lista
        def abre(k):
            return k <= 0 or palabras[k - 1]["t"].strip().endswith((".", "?", "!", "…"))
        if abre(i) or (palabras[i - 1]["n"] in ("y", "pero", "ahora") and abre(i - 1)):
            sueltos.append({"at": round(p["s"], 3), "n": PALABRA[p["n"]]})
    i += 1

crudos = con_marca or sueltos
hallados = []
for h in crudos:
    if 1 <= h["n"] <= 12 and (not hallados or h["n"] != hallados[-1]["n"]):
        hallados.append(h)

# cada numero se queda hasta que entra el siguiente; el ultimo, un rato y fuera
SOLO = 6.0
for k, h in enumerate(hallados):
    fin = hallados[k + 1]["at"] - 0.12 if k + 1 < len(hallados) else min(h["at"] + SOLO, dur)
    h["hasta"] = round(min(fin, dur), 3)

json.dump(hallados, sys.stdout, ensure_ascii=False, indent=1)
if hallados:
    print(f"  numeros en pantalla: " +
          ", ".join(f"{h['n']} en {h['at']:.1f}s" for h in hallados), file=sys.stderr)
else:
    print("  el guion no lleva puntos numerados", file=sys.stderr)
