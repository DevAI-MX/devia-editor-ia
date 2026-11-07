#!/usr/bin/env python3
"""Quita tramos del video YA CORTADO (retomas, equivocaciones) sin volver a transcribir.

Cuando la persona se equivoca y repite ("te voy a repetir esa parte, me equivoque"), el
corte por silencio no lo caza. Aqui se dan los tramos a quitar en segundos de la linea
de tiempo del _cut.mp4, y se actualizan los tres archivos que dependen de esa linea de
tiempo: el video, el transcript por palabra (se borran las palabras del tramo y se
desplazan las siguientes) y los cortes del A-roll (`keep`, para que el punch zoom y el
encaje sigan cayendo en los saltos reales).

Uso: bin/quitar.py <nombre> "a-b,c-d"        (rutas: input/<nombre>_cut.mp4, .json, _cortes.json)
"""
import json, os, subprocess, sys

nombre, tramos_txt = sys.argv[1], sys.argv[2]
cut = f"input/{nombre}_cut.mp4"; trans_p = f"input/{nombre}.json"; cortes_p = f"input/{nombre}_cortes.json"
tramos = sorted([tuple(float(x) for x in t.split("-")) for t in tramos_txt.split(",") if t.strip()])
dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                            "-of", "csv=p=0", cut], capture_output=True, text=True).stdout)

# 1) video: se conserva lo que NO esta en los tramos, con re-codificacion (el corte
#    tiene que caer en el frame exacto, no en el keyframe anterior)
quedan, t0 = [], 0.0
for a, b in tramos:
    if a > t0 + 0.02:
        quedan.append((t0, a))
    t0 = max(t0, b)
if dur > t0 + 0.02:
    quedan.append((t0, dur))
sel = "+".join(f"between(t,{a:.3f},{b:.3f})" for a, b in quedan)
tmp = cut.replace("_cut.mp4", "_cut_q.mp4")
subprocess.run(["ffmpeg", "-v", "error", "-i", cut,
                "-vf", f"select='{sel}',setpts=N/FRAME_RATE/TB", "-af", f"aselect='{sel}',asetpts=N/SR/TB",
                "-c:v", "libx264", "-crf", "16", "-preset", "medium", "-pix_fmt", "yuv420p",
                "-c:a", "aac", "-b:a", "192k", tmp, "-y"], check=True)
os.replace(tmp, cut)

# 2) transcript: fuera las palabras del tramo, y las de despues se desplazan
def nuevo_t(t):
    if any(a <= t < b for a, b in tramos):
        return None
    return round(t - sum(min(b, t) - a for a, b in tramos if a < t), 3)
d = json.load(open(trans_p))
for seg in d.get("segments", []):
    ws = []
    for w in seg.get("words", []):
        s, e = nuevo_t(float(w["start"])), nuevo_t(float(w["end"]))
        if s is None or e is None:
            continue
        w["start"], w["end"] = s, max(s + 0.02, e); ws.append(w)
    seg["words"] = ws
    seg["text"] = " ".join(w["word"].strip() for w in ws)
    if ws:
        seg["start"], seg["end"] = ws[0]["start"], ws[-1]["end"]
d["segments"] = [s for s in d.get("segments", []) if s.get("words")]
json.dump(d, open(trans_p, "w"), ensure_ascii=False, indent=1)

# 3) cortes: los `keep` van en tiempos de la FUENTE; el tramo quitado se traduce a
#    tiempos de fuente y se recorta de los keep (un keep partido en dos es un corte nuevo)
c = json.load(open(cortes_p))
keep = [tuple(k) for k in c["keep"]]
def a_fuente(t):
    acc = 0.0
    for a, b in keep:
        if t <= acc + (b - a) + 1e-6:
            return a + (t - acc)
        acc += b - a
    return keep[-1][1]
for a, b in tramos:
    fa, fb = a_fuente(a), a_fuente(b)
    nuevo = []
    for ka, kb in keep:
        if kb <= fa or ka >= fb:
            nuevo.append((ka, kb)); continue
        if ka < fa:
            nuevo.append((ka, fa))
        if kb > fb:
            nuevo.append((fb, kb))
    keep = nuevo
c["keep"] = [[round(a, 3), round(b, 3)] for a, b in keep]
c["out_duration"] = round(sum(b - a for a, b in keep), 3)
c["segments"] = len(keep)
c["quitados"] = c.get("quitados", []) + [[a, b] for a, b in tramos]
json.dump(c, open(cortes_p, "w"), ensure_ascii=False, indent=1)
print(f"  quitados {len(tramos)} tramos ({sum(b - a for a, b in tramos):.2f}s): video, transcript y cortes al dia; ahora {c['out_duration']:.1f}s", file=sys.stderr)
