#!/usr/bin/env python3
"""Donde esta la cara en el primer medio segundo del A-roll, en % del ancho y del alto.

Sirve de `transform-origin` para el PRIMER FRAME del formato editorial: el video
abre en un primer plano y tiene que cerrarse SOBRE la cara, no sobre el centro del
encuadre (a 2x, un centro geometrico deja la cabeza fuera).

Uso: bin/foco.py video_cut.mp4  -> imprime "x% y%"
"""
import subprocess, sys
import numpy as np

W, H = 180, 320
raw = subprocess.run(["ffmpeg", "-v", "quiet", "-t", "0.6", "-i", sys.argv[1],
                      "-vf", f"fps=5,scale={W}:{H}", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                     capture_output=True).stdout
fr = np.frombuffer(raw, np.uint8).reshape(-1, H, W, 3).astype(int)
xs, ys = [], []
for a in fr:
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    piel = (r > 90) & (r > g + 15) & (g > b) & (r - b > 30)
    # la cara es la mancha de piel MAS ALTA con cuerpo: filas con piel, de arriba abajo
    filas = np.where(piel.sum(axis=1) > W * 0.06)[0]
    if not len(filas):
        continue
    top = filas[0]
    banda = piel[top:min(H, top + int(H * 0.22))]
    yy, xx = np.where(banda)
    if len(xx) < 50:
        continue
    xs.append(xx.mean() / W); ys.append((top + yy.mean()) / H)
# Cuanto cerrar: si la fuente ya viene cerrada (la cara ocupa mas de un tercio del
# ancho), un 2x deja media cabeza fuera. Se mide el ancho de la mancha de piel de la cara.
anchos = []
for a in fr:
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    piel = (r > 90) & (r > g + 15) & (g > b) & (r - b > 30)
    filas = np.where(piel.sum(axis=1) > W * 0.06)[0]
    if not len(filas):
        continue
    top = filas[0]; banda = piel[top:min(H, top + int(H * 0.18))]
    cols = np.where(banda.sum(axis=0) > 3)[0]
    if len(cols) > 5:
        anchos.append((cols[-1] - cols[0]) / W)
ancho = float(np.median(anchos)) if anchos else 0.25
escala = 1.6 if ancho > 0.36 else (1.8 if ancho > 0.30 else 2.0)
if xs:
    print(f"{100 * np.median(xs):.0f}% {100 * np.median(ys):.0f}%")
else:
    print("50% 32%")
print(f"{escala}")
print(f"cara: {ancho:.0%} del ancho -> escala {escala}", file=sys.stderr)
