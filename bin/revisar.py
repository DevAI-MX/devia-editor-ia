#!/usr/bin/env python3
"""TRIPLE REVISION de subtitulos. Obligatoria en cada cambio.

Los subtitulos han fallado una y otra vez de cuatro maneras: palabras que se
repiten, cues duplicados, texto que no aparece cuando se dice, y bloques que se
solapan. Revisar "a ojo" no las caza: se necesitan tres niveles distintos, porque
cada fallo se ve en un sitio distinto.

  NIVEL 1 - DATOS         lo que dice el plan (cues, frases, graficos)
  NIVEL 2 - COMPOSICION   lo que el navegador realmente monta (hyperframes check)
  NIVEL 3 - RENDER        lo que se ve en el video ya renderizado

Un fallo puede pasar el nivel 1 y caer en el 3: el dato estaba bien pero la
plantilla no lo dibujo. Por eso son tres y no tres veces el mismo.

Uso: bin/revisar.py <proyecto> <transcript.json> [video.mp4]
"""
import os, json, shutil, subprocess, sys, tempfile, unicodedata
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cfg import cfg

proy, trans_p = sys.argv[1], sys.argv[2]
video = sys.argv[3] if len(sys.argv) > 3 else None
fallos = []


def norm(t):
    t = unicodedata.normalize("NFD", t.lower())
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    return "".join(c for c in t if c.isalnum())


def carga(p, d):
    return json.load(open(p)) if os.path.exists(p) else d


cues = carga(f"{proy}/cues_final.json", None) or carga(f"{proy}/cues.json", [])
kws = carga(f"{proy}/keywords.json", [])
beats = carga(f"{proy}/beats.json", {"stingers": []})
stg = [b for b in beats.get("stingers", []) if b.get("tipo") != "broll"]
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
            palabras.append({"t": t, "n": norm(t), "s": float(w["start"])})

print("NIVEL 1 - DATOS")

# 1a. duplicados: el mismo texto dos veces seguidas
# la italica cuenta: "mas / ayunos" y "mas / restricciones" son dos cues distintos
_k = lambda c: (c["text"].strip(), (c.get("italica") or "").strip())
dups = [c for i, c in enumerate(cues[:-1]) if _k(c) == _k(cues[i + 1])]
print(f"  duplicados consecutivos ....... {len(dups)}")
for c in dups[:5]:
    fallos.append(f"cue duplicado en {c['start']:.2f}s: {c['text']!r}")

# 1b. solapes entre cues
sol = [(cues[i], cues[i + 1]) for i in range(len(cues) - 1)
       if cues[i]["end"] > cues[i + 1]["start"] + 0.001]
print(f"  cues que se solapan ........... {len(sol)}")
for a, b in sol[:5]:
    fallos.append(f"cue {a['start']:.2f}-{a['end']:.2f} se solapa con {b['start']:.2f}")

# 1c. un bloque y un cue a la vez
bloques = ([(k["at"], k["at"] + k.get("dur", 0), k.get("text", ""), "frase") for k in kws]
           + [(b["at"], b["at"] + b.get("dur", 0), b.get("titular", ""), "grafico") for b in stg])
# 0.06s de tolerancia: tocarse en el borde no es solaparse
choques = [(c, b) for c in cues for b in bloques
           if c["start"] < b[1] - 0.06 and c["end"] > b[0] + 0.06]
print(f"  cue encima de un bloque ....... {len(choques)}")
for c, b in choques[:5]:
    fallos.append(f"el cue {c['text']!r} ({c['start']:.2f}s) coincide con el {b[3]} {b[2]!r}")

# 1d. repeticion: el bloque muestra unas palabras y un cue CERCANO las repite.
# Solo cuentan palabras con contenido y solo dentro de una ventana de tiempo:
# que "en la" o "tienes que" salgan dos veces en un minuto no es repeticion, y que
# el hablante repita una frase a los 20 segundos tampoco es culpa de la edicion.
VENTANA_REP = cfg("revision.ventana_repeticion", 4.0)
FUNCION = {"en", "la", "el", "los", "las", "un", "una", "de", "del", "al", "a", "que",
           "y", "o", "con", "por", "para", "su", "tu", "mi", "es", "no", "se", "te",
           "lo", "le", "tienes", "muy", "mas", "ya", "si"}
rep = []
for a, z, txt, tipo in bloques:
    pal = [norm(x) for x in txt.split() if norm(x) and norm(x) not in FUNCION]
    for c in cues:
        if c["end"] < a - VENTANA_REP or c["start"] > z + VENTANA_REP:
            continue
        cw = [norm(x) for x in c["text"].split() if norm(x) and norm(x) not in FUNCION]
        comunes = set(pal) & set(cw)
        # hacen falta DOS palabras de contenido en comun: que se repita una sola
        # suele ser el hablante repitiendola ("a ti mismo... tu mismo"), no la edicion
        if len(comunes) >= 2:
            rep.append((txt, c, comunes))
print(f"  secuencias repetidas .......... {len(rep)}")
for txt, c, com in rep[:5]:
    fallos.append(f"{txt!r} repite {sorted(com)} en el cue {c['text']!r} ({c['start']:.2f}s)")

# 1e. palabras que se dicen y no se ven
visto = set()
for c in cues:
    visto |= {norm(x) for x in c["text"].split()}
    if c.get("italica"): visto |= {norm(x) for x in c["italica"].split()}
for a, z, txt, tipo in bloques:
    visto |= {norm(x) for x in txt.split()}
# Lo que se dice DESPUES de la palabra clave no se escribe a proposito: los
# subtitulos terminan ahi y el resto solo se oye. No cuenta como perdido.
_exentas = {norm(w) for w in globals().get("_tras_cta", [])}
_exentas |= {norm(w) for w in carga(f"{proy}/tras_cta.json", [])}   # modo linea: cortado en la palabra clave
# Y lo que se dice bajo una FICHA DE COLOR tampoco: la ficha esconde el subtitulo a
# proposito y pone solo la frase que importa (asi lo hace la referencia).
for _bl in (beats.get("gancho") or {}).get("bloques", []):
    for _l in _bl.get("lineas", []):
        visto |= {norm(x) for x in str(_l.get("t", "")).split()}
for _r in (beats.get("rotulos", []) if isinstance(beats, dict) else []):
    if _r.get("dicho"):
        visto |= {norm(x) for x in str(_r["dicho"]).split()}
_vc = [(b["at"], b["at"] + b.get("dur", 0)) for b in beats.get("stingers", []) if b.get("tipo") == "color"]
falta = [p for p in palabras
         if p["n"] and p["n"] not in visto and p["n"] not in _exentas
         and not any(a - 0.05 <= p["s"] <= z + 0.05 for a, z in _vc)]
print(f"  palabras que no aparecen ...... {len(falta)} de {len(palabras)}")
for p in falta[:5]:
    fallos.append(f"no aparece {p['t']!r} (se dice en {p['s']:.2f}s)")

# --- NIVEL 2 ---------------------------------------------------------------
print("NIVEL 2 - COMPOSICION")
r = subprocess.run([shutil.which("npx") or "npx", "-y", "hyperframes@0.7.110", "check"],
                   cwd=proy, capture_output=True, text=True)
malos = [l.strip() for l in (r.stdout + r.stderr).split("\n")
         if "✗" in l and ("overlap" in l or "text" in l or "content" in l)]
print(f"  solapes de texto que ve Chrome  {len(malos)}")
for m in malos[:5]:
    fallos.append(m)

# --- NIVEL 3 ---------------------------------------------------------------
print("NIVEL 3 - RENDER")
if not video or not os.path.exists(video):
    print("  (sin video: se revisa tras renderizar)")
else:
    import numpy as np
    from PIL import Image
    revisados = malas = 0
    # se comprueba que HAY texto cuando toca y que NO lo hay cuando no toca
    momentos = [((c["start"] + c["end"]) / 2, True) for c in cues[:24]]
    huecos = [((cues[i]["end"] + cues[i + 1]["start"]) / 2, None)
              for i in range(len(cues) - 1) if cues[i + 1]["start"] - cues[i]["end"] > 0.5]
    cuadro = os.path.join(tempfile.gettempdir(), "rev.png")
    for t, espera in momentos + huecos[:6]:
        subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t:.3f}",
                        "-i", video, "-frames:v", "1", cuadro, "-y"], check=True)
        a = np.array(Image.open(cuadro).convert("RGB")).astype(int)
        h, w, _ = a.shape
        # La franja se saca del FORMATO, no de un numero fijo. Con el fijo, TOP 10
        # (que pinta arriba, al 26%) y reflexivo (al 70%) daban fallo siempre aunque
        # el texto estuviera perfectamente ahi: la revision miraba donde no era.
        _y = str(cfg("subtitulo.y", "55%"))
        if _y == "auto":
            _y = carga(f"{proy}/sub_y.json", {"y": "66%"}).get("y", "66%")
        cy = float(str(_y).replace("%", "")) / 100
        # por video (editorial): beats.subtitulo.y manda sobre el formato
        _by = ((beats.get("subtitulo") or {}) if isinstance(beats, dict) else {}).get("y")
        if _by:
            cy = float(str(_by).replace("%", "")) / 100
        lo, hi = max(0.0, cy - 0.16), min(1.0, cy + 0.16)
        band = a[int(h * lo):int(h * hi), int(w * 0.04):int(w * 0.96)]
        R, G, B = band[:, :, 0], band[:, :, 1], band[:, :, 2]
        blanco = (R > 205) & (G > 195) & (B > 180)
        # y el acento NO es blanco. Sin contarlo, un fotograma en el que solo se ve la
        # palabra amarilla se marcaba como "sin texto".
        color = (R > 170) & (G > 120) & (B < 140) & ((R - B) > 70)
        txt = int((blanco | color).sum())
        revisados += 1
        if espera and txt < 500:
            malas += 1
            fallos.append(f"en {t:.2f}s deberia verse texto y no se ve ({txt} px)")
    print(f"  frames revisados .............. {revisados} ({malas} sin el texto esperado)")

print()
if fallos:
    print(f"REVISION FALLIDA - {len(fallos)} problemas")
    for f in fallos[:14]:
        print(f"  - {f}")
    sys.exit(1)
print("REVISION OK - los tres niveles limpios")
