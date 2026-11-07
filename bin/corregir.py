#!/usr/bin/env python3
"""Corrige palabras mal transcritas en el transcript, sin tocar los tiempos.

Whisper acierta casi siempre, pero se le escapan terminos que en este material son
justo los importantes: "lejumbres" por "legumbres", "salseantes" por "saciantes",
"de las manos" por "te las mando". Como el transcript ES la fuente de verdad de los
subtitulos, un fallo suyo sale escrito en pantalla.

Se corrige AQUI y no en los subtitulos porque el mismo transcript alimenta la
verificacion, las palabras reservadas y el texto de los graficos: si se parchea
solo al final, cada paso sigue trabajando con la palabra mala.

Cuando la correccion cambia el numero de palabras ("en permanente pausa" ->
"en editorial"), el tramo de tiempo de las palabras viejas se reparte entre
las nuevas en proporcion a su longitud. El tramo total no se mueve: lo que entra
y lo que sale ocupan exactamente los mismos segundos.

Uso: bin/corregir.py transcript.json correcciones.json > transcript_ok.json
     correcciones.json = {"lejumbres": "legumbres", "de las manos": "te las mando"}
"""
import json, re, sys, unicodedata


def norm(t):
    t = unicodedata.normalize("NFD", t.lower())
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9ñ]", "", t)


d = json.load(open(sys.argv[1]))
corr = json.load(open(sys.argv[2]))
# se ordenan de mas palabras a menos: "de las manos" tiene que intentarse antes que "de"
reglas = sorted(corr.items(), key=lambda kv: -len(kv[0].split()))
hechas = []

for seg in d.get("segments", []):
    ws = seg.get("words", [])
    i = 0
    while i < len(ws):
        for viejo, nuevo in reglas:
            vs, ns = viejo.split(), nuevo.split()
            if [norm(w["word"]) for w in ws[i:i + len(vs)]] != [norm(v) for v in vs]:
                continue
            tramo = ws[i:i + len(vs)]
            t0, t1 = float(tramo[0]["start"]), float(tramo[-1]["end"])
            espacio = " " if tramo[0]["word"].startswith(" ") else ""
            cola = "".join(c for c in tramo[-1]["word"].strip() if c in ".,;:!?")
            if len(vs) == len(ns):
                # mismo numero: cada palabra conserva SU tiempo exacto
                for k, n_ in enumerate(ns):
                    fin = "".join(c for c in tramo[k]["word"].strip() if c in ".,;:!?")
                    sep = " " if tramo[k]["word"].startswith(" ") else ""
                    tramo[k]["word"] = sep + n_ + fin
                nuevas = tramo
            else:
                # distinto numero: el tramo se reparte segun lo larga que sea cada palabra
                largos = [len(n_) for n_ in ns]
                total = sum(largos) or 1
                nuevas, t = [], t0
                for k, n_ in enumerate(ns):
                    d_ = (t1 - t0) * largos[k] / total
                    nuevas.append({"word": (espacio if k == 0 else " ") + n_
                                           + (cola if k == len(ns) - 1 else ""),
                                   "start": round(t, 3),
                                   "end": round(t1 if k == len(ns) - 1 else t + d_, 3)})
                    t += d_
                ws[i:i + len(vs)] = nuevas
            hechas.append(f"{viejo} -> {nuevo}  ({t0:.2f}s)")
            i += len(nuevas) - 1
            break
        i += 1
    seg["text"] = "".join(w["word"] for w in ws) or seg["text"]

json.dump(d, sys.stdout, ensure_ascii=False, indent=1)
if hechas:
    print(f"  transcript corregido ({len(hechas)}):", file=sys.stderr)
    for h in hechas:
        print(f"    {h}", file=sys.stderr)
faltan = [v for v, _ in reglas if not any(h.startswith(v + " ->") for h in hechas)]
if faltan:
    print(f"  AVISO: no se encontro en el transcript: {', '.join(faltan)}", file=sys.stderr)
