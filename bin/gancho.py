#!/usr/bin/env python3
"""El TITULO APILADO del gancho (formato editorial) y los subtitulos.

En la referencia el titulo de arriba es la primera frase del habla partida en
renglones, y el subtitulo de abajo arranca DESPUES de la ultima palabra del titulo:
las palabras que ya estan escritas arriba no se repiten abajo. Este script:
  1. localiza en el transcript las palabras de cada bloque del titulo y fija su
     `at` (si no viene) en el instante en que se dice la primera;
  2. quita de los cues los que caen dentro de la ventana de cada bloque.

Uso: bin/gancho.py beats.json transcript.json cues.json > cues_sin_gancho.json
Escribe ademas beats con `at`/`fin` resueltos en la ruta que se pase por -o.
"""
import json, os, sys, unicodedata

def norm(t):
    t = unicodedata.normalize("NFD", t.lower())
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    return "".join(c for c in t if c.isalnum())

args = [a for a in sys.argv[1:] if not a.startswith("-o")]
salida_beats = next((a[2:] for a in sys.argv[1:] if a.startswith("-o")), "")
beats = json.load(open(args[0]))
trans = json.load(open(args[1]))
cues = json.load(open(args[2]))

palabras = []
for seg in trans.get("segments", []):
    for w in seg.get("words", []):
        n = norm(w.get("word", ""))
        if n:
            palabras.append({"n": n, "s": float(w["start"]), "e": float(w["end"])})

ventanas = []
gan = beats.get("gancho") or {}
for bi, bl in enumerate(gan.get("bloques", [])):
    toks = [norm(x) for l in bl.get("lineas", []) for x in str(l.get("t", "")).split()]
    toks = [t for t in toks if t]
    if not toks:
        continue
    pos = None
    for i in range(len(palabras) - len(toks) + 1):
        if [p["n"] for p in palabras[i:i + len(toks)]] == toks:
            pos = i
            break
    if pos is None:
        print(f"  AVISO: el bloque {bi+1} del titulo no se encuentra seguido en el habla", file=sys.stderr)
        continue
    ini, fin = palabras[pos]["s"], palabras[pos + len(toks) - 1]["e"]
    if bl.get("at") is None:
        bl["at"] = 0.0 if bi == 0 else round(ini, 3)
    # cada linea entra cuando se dice su primera palabra, si no trae `at`
    k = pos
    for l in bl.get("lineas", []):
        n_l = len([x for x in str(l.get("t", "")).split() if norm(x)])
        if l.get("at") is None and n_l:
            l["at"] = 0.0 if (bi == 0 and k == pos) else round(palabras[k]["s"], 3)
        k += n_l
    ventanas.append((ini, fin))
    # El gancho y los subtitulos no conviven (regla del usuario): el ultimo bloque se va
    # en cuanto acaba su ultima palabra, y ahi empiezan los subtitulos.
    if bl.get("fin") is None and bi == len(gan.get("bloques", [])) - 1:
        bl["fin"] = round(fin + 0.12, 3)
    print(f"  titulo del gancho, bloque {bi+1}: {ini:.2f}-{fin:.2f}s  ({' / '.join(str(l.get('t','')) for l in bl.get('lineas', []))})", file=sys.stderr)

def buscar(texto):
    """posicion (ini, fin en segundos) de una secuencia literal de palabras en el habla"""
    toks = [norm(x) for x in str(texto).split()]
    toks = [t for t in toks if t]
    if not toks:
        return None
    for i in range(len(palabras) - len(toks) + 1):
        if [p["n"] for p in palabras[i:i + len(toks)]] == toks:
            return palabras[i]["s"], palabras[i + len(toks) - 1]["e"]
    return None

# FICHAS DE COLOR y ROTULOS sin `at`: se colocan donde se dice su texto. La ficha
# entra con la primera palabra y dura hasta 0.4s despues de la ultima (referencia
# ejemplos: entra 0.1-0.2s antes de la frase y sale tras la ultima palabra).
for b in beats.get("stingers", []):
    if b.get("tipo") == "color" and b.get("at") is None:
        frase = " ".join((l if isinstance(l, str) else l.get("t", "")) for l in b.get("lineas", []))
        pos = buscar(frase)
        if pos is None:
            print(f"  AVISO: la ficha de color '{frase[:40]}' no se encuentra seguida en el habla", file=sys.stderr)
            b["at"] = 0.0; b["dur"] = 0.0
            continue
        b["at"] = round(max(0.0, pos[0] - 0.12), 3)
        b["dur"] = round(pos[1] - b["at"] + (b.get("cola", 0.4)), 3)
        # cada linea entra cuando se dice su primera palabra
        k = 0
        for l in b.get("lineas", []):
            t = l if isinstance(l, str) else l.get("t", "")
            pl = buscar(t)
            if isinstance(l, dict) and l.get("at") is None and pl:
                l["at"] = round(pl[0], 3)
        print(f"  ficha de color '{frase[:36]}': {b['at']:.2f}-{b['at'] + b['dur']:.2f}s", file=sys.stderr)
# El ARRANQUE es sagrado: el frame 0 es la cara con el zoom out, el titulo y el whoosh.
# Un b-roll o una ficha por frase nunca empieza antes de que el zoom out haya aterrizado.
try:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from cfg import cfg as _cfg
    _arr = _cfg("arranque", {}) or {}
    MIN_AT = (float(_arr.get("duracion") or _arr.get("dur") or 0.6) + 0.35) if (_arr.get("activo") or _arr.get("modo")) else 0.0
except Exception:
    MIN_AT = 0.0
# B-ROLL por frase: entra 0.1s antes de la primera palabra y dura lo que la frase (minimo 2.2s)
for b in beats.get("stingers", []):
    if b.get("tipo") == "broll" and b.get("at") is None and b.get("frase"):
        pos = buscar(b["frase"])
        if pos is None:
            print(f"  AVISO: el b-roll '{b['frase'][:40]}' no se encuentra seguido en el habla", file=sys.stderr)
            b["at"] = 0.0; b["dur"] = 0.0; continue
        b["at"] = round(max(MIN_AT, pos[0] - 0.1), 3)
        b["dur"] = round(max(float(b.get("dur_min", 2.2)), pos[1] - b["at"] + 0.3), 3)
        print(f"  b-roll '{b['frase'][:36]}': {b['at']:.2f}-{b['at'] + b['dur']:.2f}s", file=sys.stderr)
# FICHAS (emoji/foto) y PROPS (oferta) por frase: entran con la primera palabra
for b in beats.get("stingers", []):
    if b.get("tipo") == "ficha" and b.get("at") is None and b.get("frase"):
        pos = buscar(b["frase"])
        if pos is None:
            print(f"  AVISO: la ficha '{b['frase'][:40]}' no se encuentra seguida en el habla", file=sys.stderr)
            b["at"] = 0.0; b["dur"] = 0.0; continue
        b["at"] = round(max(MIN_AT, pos[0] - 0.1), 3)
        b["dur"] = round(max(float(b.get("dur_min", 2.4)), pos[1] - b["at"] + 0.3), 3)
        print(f"  ficha '{b['frase'][:36]}': {b['at']:.2f}-{b['at'] + b['dur']:.2f}s", file=sys.stderr)
for pr in beats.get("props", []) if isinstance(beats, dict) else []:
    if pr.get("at") is None and pr.get("frase"):
        pos = buscar(pr["frase"])
        if pos:
            pr["at"] = round(max(0.0, pos[0] - 0.1), 3)
            fin_v = palabras[-1]["e"] + 0.3 if palabras else pr["at"] + 6
            pr["dur"] = round(float(pr.get("dur") or (fin_v - pr["at"])), 3)
            print(f"  prop '{pr['frase'][:36]}': {pr['at']:.2f}-{pr['at'] + pr['dur']:.2f}s", file=sys.stderr)
        else:
            print(f"  AVISO: el prop '{pr['frase'][:40]}' no se encuentra seguido en el habla", file=sys.stderr)
            pr["at"] = 0.0; pr["dur"] = 0.0

# dos b-rolls seguidos que se pisan van CONTIGUOS (como la secuencia de ejemplos): el
# segundo arranca donde acaba el primero, sin volver al plano de ella en medio
_brs = sorted([b for b in beats.get("stingers", []) if b.get("tipo") == "broll" and b.get("dur")], key=lambda b: b["at"])
for i in range(1, len(_brs)):
    prev, cur = _brs[i - 1], _brs[i]
    if cur["at"] < prev["at"] + prev["dur"]:
        fin = cur["at"] + cur["dur"]
        cur["at"] = round(prev["at"] + prev["dur"], 3)
        cur["dur"] = round(max(1.2, fin - cur["at"]), 3)
        print(f"  b-roll '{cur.get('frase', '')[:30]}' pegado al anterior: {cur['at']:.2f}-{cur['at'] + cur['dur']:.2f}s", file=sys.stderr)
# El NUMERO DICHO ("Numero 5", "Tercero", "2.") no sale en el subtitulo: solo cambia el
# rotulo de arriba (regla del usuario). rotulos[].dicho = lo que dice al enunciar el punto.
for r in beats.get("rotulos", []) if isinstance(beats, dict) else []:
    if r.get("dicho"):
        pos = buscar(r["dicho"])
        if pos:
            ventanas.append((pos[0], pos[1]))
            if r.get("at") is None:
                r["at"] = round(max(0.0, pos[0] - 0.05), 3)
            print(f"  rotulo {r.get('num','')}: '{r['dicho']}' fuera del subtitulo ({pos[0]:.2f}-{pos[1]:.2f}s)", file=sys.stderr)
        else:
            print(f"  AVISO: '{r['dicho']}' no se encuentra seguido en el habla", file=sys.stderr)
for r in beats.get("rotulos", []) if isinstance(beats, dict) else []:
    if r.get("at") is None and r.get("txt"):
        pos = buscar(r["txt"])
        if pos:
            r["at"] = round(max(0.0, pos[0] - 0.1), 3)
            print(f"  rotulo '{r['txt']}': entra en {r['at']:.2f}s", file=sys.stderr)
# un rotulo de lista sin `dur` se queda hasta que entra el siguiente (referencia fresco:
# "1- Proteina" dura el punto entero); el ultimo, hasta `hasta` o hasta el final
_rots = sorted([r for r in (beats.get("rotulos", []) if isinstance(beats, dict) else []) if r.get("at") is not None], key=lambda r: r["at"])
_fin_video = palabras[-1]["e"] + 0.5 if palabras else 0
for i, r in enumerate(_rots):
    if r.get("dur") is None:
        fin = _rots[i + 1]["at"] if i + 1 < len(_rots) else r.get("hasta", _fin_video)
        if isinstance(fin, str):
            pf = buscar(fin); fin = pf[0] - 0.1 if pf else _fin_video
        r["dur"] = round(max(0.5, float(fin) - r["at"]), 3)

# ITALICAS (ejemplos): subtitulo de dos lineas, prefijo en la grotesca y la palabra clave
# en serif italica debajo. Se colocan donde se dice "prefijo palabra"; los cues
# normales de esa ventana se quitan y entra un cue especial.
especiales = []
for it in beats.get("italicas", []) if isinstance(beats, dict) else []:
    pos = buscar((it.get("prefijo", "") + " " + it.get("palabra", "")).strip())
    if pos is None:
        print(f"  AVISO: la italica '{it.get('prefijo')} {it.get('palabra')}' no se encuentra seguida en el habla", file=sys.stderr)
        continue
    ventanas.append((pos[0], pos[1]))
    especiales.append({"start": round(pos[0], 3), "end": round(pos[1] + float(it.get("cola", 0.2)), 3),
                       "text": it.get("prefijo", ""), "italica": it.get("palabra", "")})
    print(f"  italica '{it.get('prefijo')} / {it.get('palabra')}': {pos[0]:.2f}-{pos[1]:.2f}s", file=sys.stderr)

antes = len(cues)
# Un cue que PISA una ventana (titulo o italica) no se tira entero: se parte con
# los tiempos de palabra del transcript y se conserva lo que queda fuera. Tirarlo
# entero perdia palabras ("meta estetica" desaparecio por una italica que empezaba
# 0.5s despues).
palabras_txt = []
for seg in trans.get("segments", []):
    for w in seg.get("words", []):
        if w.get("word", "").strip():
            palabras_txt.append({"t": w["word"].strip(), "s": float(w["start"]), "e": float(w["end"])})
def trozo(c, s0, s1):
    ws = [w for w in palabras_txt if s0 - 0.02 <= w["s"] < s1 - 0.02]
    if not ws:
        return None
    return {"start": round(max(c["start"], ws[0]["s"]), 3), "end": round(min(c["end"], s1), 3),
            "text": " ".join(w["t"] for w in ws)}
def recortar(c):
    for a, z in ventanas:
        if c["end"] <= a + 0.05 or c["start"] >= z - 0.05:
            continue
        partes = []
        if c["start"] < a - 0.15:
            t = trozo(c, c["start"], a)
            if t and t["end"] - t["start"] >= 0.2: partes.append(t)
        if c["end"] > z + 0.15:
            t = trozo(c, z, c["end"])
            if t and t["end"] - t["start"] >= 0.2: partes.append(t)
        return partes
    return [c]
# Se repite hasta que ningun trozo pise ninguna ventana: un trozo que sobra de una
# ventana puede caer dentro de la siguiente (paso: "y sigues" sobraba del bloque 1 y
# era justo el principio del bloque 2).
nuevos = list(cues)
for _ in range(6):
    otra = []
    for c in nuevos:
        otra += recortar(c)
    if otra == nuevos:
        break
    nuevos = otra
cues = nuevos
cues = sorted(cues + especiales, key=lambda c: c["start"])
# un cue normal no puede pisar a la italica: se recorta al empezar ella
for i in range(len(cues) - 1):
    if cues[i + 1].get("italica") and cues[i]["end"] > cues[i + 1]["start"]:
        cues[i]["end"] = round(cues[i + 1]["start"], 3)
if ventanas:
    print(f"  subtitulos quitados bajo el titulo: {antes - len(cues)} (las palabras ya estan escritas arriba)", file=sys.stderr)

if salida_beats:
    json.dump(beats, open(salida_beats, "w"), ensure_ascii=False, indent=1)
# las ventanas se guardan para reservar.py: un cue no puede estirarse por encima
# de un titulo o de una italica para rellenar el hueco que dejan
if os.environ.get("VENTANAS_OUT"):
    json.dump([[round(a, 3), round(z, 3)] for a, z in ventanas], open(os.environ["VENTANAS_OUT"], "w"))
json.dump(cues, sys.stdout, ensure_ascii=False, indent=1)
