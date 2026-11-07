#!/usr/bin/env python3
"""Auditoria del video montado: que se dice vs que se ve.

Busca las dos familias de fallo que se cuelan sin que se noten hasta ver el video:
  1. PALABRAS PERDIDAS: algo que se dice y no aparece en pantalla en ningun sitio
     (ni subtitulo normal, ni frase animada, ni texto de motion graphic).
  2. DESFASE: un texto que aparece lejos del momento en que se dice esa frase.

Uso: bin/auditar.py <proyecto> <transcript.json>
"""
import json, sys, unicodedata, os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cfg import cfg

proy, trans_p = sys.argv[1], sys.argv[2]


def norm(t):
    t = unicodedata.normalize("NFD", t.lower())
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    return "".join(c for c in t if c.isalnum())


def carga(p, defecto):
    return json.load(open(p)) if os.path.exists(p) else defecto


# cues_final.json es el que se dibuja de verdad (ya resuelto contra los bloques)
cues = carga(f"{proy}/cues_final.json", None) or carga(f"{proy}/cues.json", [])
kws = carga(f"{proy}/keywords.json", [])
beats = carga(f"{proy}/beats.json", {"stingers": []})
stg = beats.get("stingers", [])
# Formato impacto: lo que se ve en pantalla no son los cues ni los bloques de tres
# registros, son las parejas de dos lineas. Se auditan ESAS, que es lo que se dibuja.
# ni en dos_lineas ni en linea se dibuja el bloque: las keywords son acento dentro
# del subtitulo, no un grafico aparte que pueda tapar nada
if cfg("subtitulo.modo", "") in ("dos_lineas", "linea"):
    # Las parejas posteriores al CTA no se dibujan a proposito: los subtitulos
    # terminan en la palabra clave y lo de despues solo se oye. No son texto perdido.
    if cfg("subtitulo.modo", "") == "dos_lineas":
        cues = [{"text": (p["lead"] + " " + p["clave"]).strip(),
                 "start": p["at"], "end": p["fin"]}
                for p in carga(f"{proy}/pares.json", []) if not p.get("tras_cta")]
    _tras_cta = [w for p in carga(f"{proy}/pares.json", []) if p.get("tras_cta")
                 for w in (p["lead"] + " " + p["clave"]).split()]
    kws = []
    stg = []   # en este formato los graficos no llevan texto

palabras = []
for seg in json.load(open(trans_p)).get("segments", []):
    for w in seg.get("words", []):
        t = w.get("word", "").strip()
        if t:
            palabras.append({"t": t, "n": norm(t), "s": float(w["start"]), "e": float(w["end"])})

# --- que bloques ocupan la pantalla (misma logica que la plantilla) --------
SALIDA_KW, MARGEN = 0.16, 0.04
# el b-roll no ocupa el hueco del subtitulo: va debajo de la narracion
ocupa = ([(k["at"], k["at"] + k["dur"] + SALIDA_KW + MARGEN) for k in kws]
         + [(b["at"], b["at"] + b["dur"]) for b in stg if b.get("tipo") != "broll"])
ocupa.sort()

# una frase animada que choca con un grafico no se muestra (manda el grafico)
kws_vis = [k for k in kws
           if not any(k["at"] < b["at"] + b["dur"] and k["at"] + k["dur"] > b["at"]
                      for b in stg if b.get("tipo") != "broll")]

# --- que texto llega de verdad a pantalla ---------------------------------
mostrado = set()
for k in kws_vis:
    mostrado |= {norm(x) for x in k["text"].split()}
for b in stg:
    if b.get("titular"):
        mostrado |= {norm(x) for x in b["titular"].split()}

for c in cues:
    mostrado |= {norm(x) for x in c["text"].split()}
    if c.get("italica"): mostrado |= {norm(x) for x in c["italica"].split()}

fallos = 0
# proporcion real de ocre sobre todo el texto que se ve
tot = len(mostrado)
en_ocre = set()
for k in kws_vis:
    ac = k.get("acento")
    if not ac:
        continue
    ws = k["text"].split()
    if ac in ("nucleo", "grande"):
        en_ocre |= {norm(x) for x in ws[1:3]}
    elif ac in ("remate", "serif"):
        en_ocre |= {norm(x) for x in ws[-2:]}
    else:
        en_ocre |= {norm(ws[0])}
pct = 100 * len(en_ocre) / max(tot, 1)
print(f"== TEXTO EN OCRE: {len(en_ocre)} palabras de {tot} distintas en pantalla "
      f"({pct:.0f}%) ==")
if pct > 25:
    print("   AVISO: demasiado ocre, deja de destacar")

_exentas = {norm(w) for w in globals().get("_tras_cta", [])}
_exentas |= {norm(w) for w in carga(f"{proy}/tras_cta.json", [])}   # modo linea: cortado en la palabra clave
# Mientras hay una FICHA DE COLOR (editorial) el subtitulo se esconde a proposito:
# la ficha pone en pantalla la frase que importa y el resto de lo que se dice en ese
# tramo no se rotula (asi lo hace la referencia). Esas palabras no cuentan como perdidas.
# Las palabras del TITULO DEL GANCHO (editorial) se ven arriba, no en el subtitulo.
for _bl in (beats.get("gancho") or {}).get("bloques", []):
    for _l in _bl.get("lineas", []):
        mostrado |= {norm(x) for x in str(_l.get("t", "")).split()}
# El numero DICHO de un punto de lista ("Numero 5", "Tercero") no va al subtitulo a
# proposito (regla del usuario): solo cambia el rotulo. No cuenta como perdido.
for _r in (beats.get("rotulos", []) if isinstance(beats, dict) else []):
    if _r.get("dicho"):
        mostrado |= {norm(x) for x in str(_r["dicho"]).split()}
_ventanas_color = [(b["at"], b["at"] + b.get("dur", 0)) for b in beats.get("stingers", [])
                   if b.get("tipo") == "color"]
def _en_ficha_color(p):
    return any(a - 0.05 <= p["s"] <= z + 0.05 for a, z in _ventanas_color)
perdidas = [p for p in palabras if p["n"] and p["n"] not in mostrado and p["n"] not in _exentas
            and not _en_ficha_color(p)]
fallos += len(perdidas)
print(f"== PALABRAS QUE SE DICEN Y NO SE VEN: {len(perdidas)} de {len(palabras)} ==")
if perdidas:
    for p in perdidas:
        print(f"   {p['s']:6.2f}s  '{p['t']}'")

# --- desfase de los motion graphics ---------------------------------------
print(f"\n== DESFASE DE LOS MOTION GRAPHICS ==")
for b in stg:
    txt = b.get("titular")
    if not txt:
        continue
    obj = [norm(x) for x in txt.split()]
    # la frase puede decirse varias veces: se compara con la aparicion MAS CERCANA
    # al grafico, no con la primera del video
    dicho, mejor = None, 1e9
    for i in range(len(palabras) - len(obj) + 1):
        if [p["n"] for p in palabras[i:i + len(obj)]] == obj:
            d = abs(palabras[i]["s"] - b["at"])
            if d < mejor:
                mejor = d
                dicho = (palabras[i]["s"], palabras[i + len(obj) - 1]["e"])
    if dicho is None:
        print(f"   {b['at']:6.2f}s  '{txt}'  -> NO se dice asi en el video")
        continue
    d = b["at"] - dicho[0]
    fin_g, fin_d = b["at"] + b["dur"], dicho[1]
    estado = "ok" if abs(d) <= 0.35 else ("ADELANTADO" if d < 0 else "ATRASADO")
    print(f"   grafico {b['at']:6.2f}-{fin_g:5.2f}  se dice {dicho[0]:6.2f}-{fin_d:5.2f}  "
          f"desfase {d:+5.2f}s  {estado}")
    if estado != "ok":
        fallos += 1
    if fin_d > fin_g:
        print(f"      + la frase sigue sonando {fin_d - fin_g:.2f}s despues de que el grafico se fue")
        fallos += 1

sys.exit(1 if fallos else 0)
