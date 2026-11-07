#!/usr/bin/env python3
"""Donde va el plano dentro de la banda del marco (formato reflexivo), en % para object-position.

Regla del usuario (25-sep): con marco, la cabeza se ve COMPLETA, con aire arriba, y un
poco de torso. Recortar el video por el centro dentro de la banda le cortaba la cabeza:
la banda es mas baja que el video y el centro geometrico no es la cara.

Se detecta la CARA con la cascada Haar de OpenCV cada 2 s (igual que bin/barbilla.py). El
borde de arriba de la cabeza se estima sobre la caja de la cara (el pelo sube ~25% del
alto de la caja; medido el 25-sep en tres fotogramas: 16-25%. Con 40% sobraba aire) y se toma el mas alto de casi todo el video (percentil 10), para que
ningun momento corte la cabeza. La ventana visible empieza `marco.aire` (fraccion de la
banda) por encima de esa linea.

Uso: bin/encuadre.py video.mp4 <banda_arriba 0-1> <banda_abajo 0-1> [aire 0-1]  -> "19%"
"""
import os, subprocess, sys
import numpy as np
try:
    import cv2
except ImportError:
    r = subprocess.run(["uvx", "--from", "opencv-python-headless<5", "python", os.path.abspath(__file__)] + sys.argv[1:],
                       capture_output=True, text=True)
    sys.stdout.write(r.stdout); sys.stderr.write(r.stderr); sys.exit(r.returncode)

video, arriba, abajo = sys.argv[1], float(sys.argv[2]), float(sys.argv[3])
aire = float(sys.argv[4]) if len(sys.argv) > 4 else 0.07
W, H = 360, 640
PELO = 0.25   # cuanto sube el pelo sobre la caja de la cara, en fraccion de su alto
raw = subprocess.run(["ffmpeg", "-v", "quiet", "-i", video, "-vf", f"fps=0.5,scale={W}:{H}",
                      "-f", "rawvideo", "-pix_fmt", "gray", "-"], capture_output=True).stdout
fr = np.frombuffer(raw, np.uint8).reshape(-1, H, W)
casc = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
cabezas = []
for g in fr:
    caras = casc.detectMultiScale(g, scaleFactor=1.1, minNeighbors=5, minSize=(60, 60))
    if len(caras):
        x, y, w, h = max(caras, key=lambda c: c[2] * c[3])
        cabezas.append((y - PELO * h) / H)
banda = 1.0 - arriba - abajo              # alto visible, en fraccion del alto del video
sobra = 1.0 - banda                       # lo que queda fuera de la banda
if not cabezas or sobra <= 0:
    print("30%"); print("sin caras detectadas: 30% por defecto", file=sys.stderr); sys.exit(0)
tope = float(np.percentile(cabezas, 10))
y0 = min(max(tope - aire * banda, 0.0), sobra)
print(f"{100 * y0 / sobra:.0f}%")
print(f"cabeza desde {100 * tope:.0f}% en {len(cabezas)} de {len(fr)} fotogramas", file=sys.stderr)
