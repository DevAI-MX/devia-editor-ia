#!/usr/bin/env python3
"""Cierra los silencios que quedan dentro del corte: que no pare de hablar.

Por que hace falta un segundo paso. El primero (silencedetect) usa un umbral
ABSOLUTO, y por bien que se calibre se le escapa casi todo: medido sobre el corte
ya hecho de la marca quedaban 29 silencios de mas de 0.3s que sumaban 14 segundos,
con picos de 0.88s. Ni el umbral absoluto ni los tiempos de palabra de whisper los
ven — whisper alarga el final de cada palabra hasta bien entrado el silencio, asi
que medido por palabras el hueco parecia de 0.2s cuando de verdad era de 0.9s.

Aqui el umbral es RELATIVO a su voz: se mide su nivel de habla (percentil 92 de la
envolvente) y se considera silencio todo lo que baje de `nivel_rel` de eso. Con eso
da igual si grabo bajo o alto, o si cambio de habitacion entre videos.

De cada silencio se quita el CENTRO y se deja `pausa_deja`. Nunca los bordes: asi
entre el corte y la voz queda medio respiro y no se come ni la consonante final ni
el ataque de la siguiente palabra.

El resultado se devuelve en tiempo de la FUENTE, atravesando los tramos del corte
anterior, para que ffmpeg lo resuelva todo en una sola pasada.

Uso: bin/cadencia.py <audio_del_corte.wav> cortes.json > cortes2.json
"""
import json, os, sys, wave
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cfg import cfg
import numpy as np

wav = sys.argv[1]
cortes = json.load(open(sys.argv[2]))
PAUSA_MAX = float(sys.argv[3]) if len(sys.argv) > 3 else cfg("cortes.pausa_max", 0.28)
PAUSA_DEJA = float(sys.argv[4]) if len(sys.argv) > 4 else cfg("cortes.pausa_deja", 0.16)
NIVEL_REL = cfg("cortes.nivel_rel", 0.12)

w = wave.open(wav)
sr = w.getframerate()
x = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float64) / 32768
v = int(sr * 0.02)
env = np.sqrt(np.convolve(x ** 2, np.ones(v) / v, mode="same"))
voz = np.percentile(env, 92)
umbral = voz * NIVEL_REL

bajo = env < umbral
d = np.diff(bajo.astype(int))
ini = np.flatnonzero(d == 1) + 1
fin = np.flatnonzero(d == -1) + 1
if bajo[0]:
    ini = np.r_[0, ini]
if bajo[-1]:
    fin = np.r_[fin, len(bajo)]

# Islas: una palabra corta y dicha flojito ("si", "ya", "mira") puede quedar por
# debajo del umbral y desaparecer dentro de un silencio. Paso: se perdio un "si"
# de los 258 de un video. Antes de cortar se busca dentro del hueco cualquier
# repunte por encima de ISLA_REL que dure mas de ISLA_MIN, y el hueco se parte por
# ahi en dos, respetando lo que suene.
ISLA_REL, ISLA_MIN = 0.045, 0.08


def islas(a_, b_):
    """trozos con algo de sonido dentro de un tramo considerado silencio"""
    seg = env[a_:b_]
    hay = seg > voz * ISLA_REL
    if not hay.any():
        return []
    d2 = np.diff(hay.astype(int))
    i2 = np.flatnonzero(d2 == 1) + 1
    f2 = np.flatnonzero(d2 == -1) + 1
    if hay[0]:
        i2 = np.r_[0, i2]
    if hay[-1]:
        f2 = np.r_[f2, len(seg)]
    return [(a_ + p, a_ + q) for p, q in zip(i2, f2) if (q - p) / sr >= ISLA_MIN]


fuera, largos, salvadas, encogidos = [], [], 0, []
BORDE_MAX = cfg("cortes.borde_max", 0.14)
pendientes = list(zip(ini, fin))
while pendientes:
    a_, b_ = pendientes.pop(0)
    isl = islas(a_, b_)
    if isl:
        salvadas += len(isl)
        # el hueco se parte alrededor de lo que suena y cada parte se vuelve a mirar
        t0 = a_
        for p, q in isl:
            if p > t0:
                pendientes.append((t0, p))
            t0 = q
        if b_ > t0:
            pendientes.append((t0, b_))
        pendientes.sort()
        continue
    a, b = a_ / sr, b_ / sr
    if b - a <= PAUSA_MAX:
        continue
    sobra = (b - a) - PAUSA_DEJA
    c = (a + b) / 2
    ini, fin_ = c - sobra / 2, c + sobra / 2
    # GUARDA DE BORDE: el empalme no puede caer donde todavia suena la voz. El
    # umbral relativo marca "silencio" antes de que la palabra haya terminado de
    # apagarse, y el corte se comia el final: se oian palabras a medias. Se encoge
    # el recorte hasta que los dos bordes estan de verdad callados.
    def nivel(t):
        i = int(t * sr)
        j = int((t + 0.03) * sr)
        seg = env[max(0, i - int(sr * 0.03)):min(len(env), j)]
        return float(seg.max() / voz) if len(seg) else 0.0

    n = 0
    while (nivel(ini) > BORDE_MAX or nivel(fin_) > BORDE_MAX) and fin_ - ini > 0.06 and n < 20:
        ini += 0.02
        fin_ -= 0.02
        n += 1
    if fin_ - ini <= 0.06:
        continue
    if n:
        encogidos.append(round(b - a, 2))
    fuera.append((ini, fin_))
    largos.append(b - a)

dur_cut = sum(bb - aa for aa, bb in cortes["keep"])

# --- lo que se conserva, en tiempo del video ya cortado ---------------------
fuera.sort()
keep_cut, t = [], 0.0
for a, b in fuera:
    if a > t:
        keep_cut.append([t, a])
    t = max(t, b)
if t < dur_cut:
    keep_cut.append([t, dur_cut])

# --- traducido a tiempo de la FUENTE ---------------------------------------
tramos, acc = [], 0.0
for a, b in cortes["keep"]:
    tramos.append((acc, acc + (b - a), a))       # (inicio_cut, fin_cut, inicio_src)
    acc += b - a

keep_src = []
for a, b in keep_cut:
    for ca, cb, sa in tramos:
        i, j = max(a, ca), min(b, cb)
        if j - i > 0.02:
            keep_src.append([round(sa + (i - ca), 3), round(sa + (j - ca), 3)])

fund = []
for a, b in keep_src:
    if fund and abs(a - fund[-1][1]) < 0.005:
        fund[-1][1] = b
    else:
        fund.append([a, b])

quitado = sum(b - a for a, b in fuera)
salida = dict(cortes)
salida["keep"] = [(a, b) for a, b in fund]
salida["segments"] = len(fund)
salida["out_duration"] = round(sum(b - a for a, b in fund), 3)
salida["cadencia"] = {"pausa_max": PAUSA_MAX, "pausa_deja": PAUSA_DEJA,
                      "nivel_rel": NIVEL_REL, "islas_respetadas": salvadas,
                      "silencios_cerrados": len(fuera),
                      "segundos_quitados": round(quitado, 3),
                      "silencio_mas_largo_antes": round(max(largos), 3) if largos else 0.0}
json.dump(salida, sys.stdout, indent=1)

print(f"  cadencia: nivel de voz {20*np.log10(voz+1e-9):.1f} dB, umbral de silencio "
      f"{20*np.log10(umbral+1e-9):.1f} dB ({NIVEL_REL*100:.0f}% de la voz)", file=sys.stderr)
if encogidos:
    print(f"  {len(encogidos)} recortes encogidos porque el borde todavia sonaba "
          f"(la voz no se corta a media palabra)", file=sys.stderr)
if salvadas:
    print(f"  {salvadas} repuntes flojos respetados dentro de los silencios "
          f"(palabras dichas por lo bajo)", file=sys.stderr)
print(f"  {len(fuera)} silencios de mas de {PAUSA_MAX}s cerrados a {PAUSA_DEJA}s "
      f"(el mayor era de {max(largos) if largos else 0:.2f}s), -{quitado:.1f}s  "
      f"({dur_cut:.1f}s -> {salida['out_duration']:.1f}s)", file=sys.stderr)
