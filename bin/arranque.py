#!/usr/bin/env python3
"""El video empieza justo donde empieza a hablar, no antes.

El detector de silencios marca el fin del silencio en cuanto sube algo de energia
(una respiracion, un roce del microfono), asi que el corte arrancaba medio segundo
antes de la primera palabra. En un reel ese medio segundo es el que decide si te
quedas o pasas de largo.

Aqui se busca el primer arranque de VOZ de verdad dentro del primer segmento y se
mueve su inicio ahi, dejando solo un pelo de aire para no comerse la consonante.

Uso: bin/arranque.py cortes.json analisis.wav > cortes_ajustados.json
"""
import os, json, sys, wave
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cfg import cfg
import numpy as np

PRE = cfg("cortes.arranque_aire", 0.05)          # aire que se deja antes de la primera palabra

cortes = json.load(open(sys.argv[1]))
w = wave.open(sys.argv[2])
sr = w.getframerate()
x = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float64) / 32768

a, b = cortes["keep"][0]
i0, i1 = int(a * sr), min(int(b * sr), len(x))
seg = x[i0:i1]
if len(seg) < sr // 10:
    json.dump(cortes, sys.stdout, indent=1)
    sys.exit(0)

win = int(sr * 0.01)
e = np.array([np.sqrt((seg[i:i + win] ** 2).mean() + 1e-12)
              for i in range(0, len(seg) - win, win)])
# umbral relativo al nivel de voz del propio segmento: asi vale igual para
# material grabado alto o bajo
umbral = np.percentile(e, 92) * 0.18
idx = np.nonzero(e > umbral)[0]
if len(idx):
    onset = max(0.0, idx[0] * 0.01 - PRE)
    if onset > 0.02:
        cortes["keep"][0] = (round(a + onset, 3), b)
        cortes["out_duration"] = round(sum(y - z for z, y in cortes["keep"]), 3)
        print(f"  arranque: se quitan {onset:.2f}s de silencio antes de la primera palabra",
              file=sys.stderr)

json.dump(cortes, sys.stdout, indent=1)
