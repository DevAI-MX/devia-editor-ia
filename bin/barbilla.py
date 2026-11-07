#!/usr/bin/env python3
"""Donde acaba la cara (la barbilla) a lo largo del video, en % del alto.

Regla del usuario (10-sep): los subtitulos van DEBAJO de la cabeza, sin tapar la boca ni
la barbilla, y dentro del area de respeto. La piel no vale para medirlo (el cuello y el
pecho tambien son piel): se detecta la CARA con la cascada Haar de OpenCV cada 2s y se
toma el borde inferior de la caja (la barbilla) que cubre el 75% de los fotogramas.

Uso: bin/barbilla.py video.mp4  -> imprime "66%"
(se ejecuta con uvx --from "opencv-python-headless<5" si el python del sistema no trae cv2)
"""
import os, subprocess, sys
import numpy as np
try:
    import cv2
except ImportError:
    r = subprocess.run(["uvx", "--from", "opencv-python-headless<5", "python", os.path.abspath(__file__)] + sys.argv[1:],
                       capture_output=True, text=True)
    sys.stdout.write(r.stdout); sys.stderr.write(r.stderr); sys.exit(r.returncode)

W, H = 360, 640
raw = subprocess.run(["ffmpeg", "-v", "quiet", "-i", sys.argv[1],
                      "-vf", f"fps=0.5,scale={W}:{H}", "-f", "rawvideo", "-pix_fmt", "gray", "-"],
                     capture_output=True).stdout
fr = np.frombuffer(raw, np.uint8).reshape(-1, H, W)
casc = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
fondos = []
for g in fr:
    caras = casc.detectMultiScale(g, scaleFactor=1.1, minNeighbors=5, minSize=(60, 60))
    if len(caras) == 0:
        continue
    x, y, w, h = max(caras, key=lambda c: c[2] * c[3])
    fondos.append((y + h) / H)
if fondos:
    print(f"{100 * np.percentile(fondos, 75):.0f}%")
    print(f"caras detectadas en {len(fondos)} de {len(fr)} fotogramas", file=sys.stderr)
else:
    print("66%")
    print("sin caras detectadas: 66% por defecto", file=sys.stderr)
