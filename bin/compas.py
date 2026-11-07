#!/usr/bin/env python3
"""Saca el pulso de la cancion: tempo, tiempos y primeros tiempos de compas.

Para que los efectos caigan con la musica hacen falta dos cosas, y esta es la
primera: saber DONDE estan los golpes. La segunda es no forzarlos (eso lo hace
bin/ritmo.py, que solo mueve un zoom si el golpe le queda a un pelo).

Como se calcula, sin librerias de analisis musical:
  1. flujo espectral -> curva de "cuanto cambia el sonido" en cada instante;
     los golpes de bateria son picos de esa curva.
  2. autocorrelacion de la curva entre 70 y 165 BPM -> el periodo que mas se
     repite es el tempo.
  3. fase: se prueba un tren de pulsos en cada desplazamiento posible dentro de
     un periodo y gana el que mas energia de golpes recoge.
  4. primer tiempo de compas: de cada 4 tiempos, el que mas peso acumula.

Ademas elige DONDE arrancar la cancion: el primer downbeat pasados unos segundos
de intro y ya con la bateria dentro, para que el video empiece en el uno del
compas y no a media frase musical.

Uso: bin/compas.py <pista> <duracion_video> [salto_min] > compas.json
"""
import json, os, subprocess, sys, tempfile, wave
import numpy as np

SR = 22050
pista = sys.argv[1]
dur_video = float(sys.argv[2])
SALTO_MIN = float(sys.argv[3]) if len(sys.argv) > 3 else 6.0

tmp = os.path.join(tempfile.gettempdir(), "_compas.wav")
subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-i", pista,
                "-ac", "1", "-ar", str(SR), "-f", "wav", tmp, "-y"], check=True)
w = wave.open(tmp)
x = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float64) / 32768
if len(x) < SR * 4:
    print(json.dumps({}))
    sys.exit(0)

# --- 1. flujo espectral ----------------------------------------------------
N, H = 1024, 256                       # ventana y salto -> ~86 cuadros/segundo
FPS = SR / H
ven = np.hanning(N)
n_cuadros = (len(x) - N) // H
esp = np.abs(np.fft.rfft(np.lib.stride_tricks.as_strided(
    x, (n_cuadros, N), (x.strides[0] * H, x.strides[0])) * ven, axis=1))
flujo = np.maximum(0, np.diff(esp, axis=0)).sum(axis=1)
flujo -= np.convolve(flujo, np.ones(43) / 43, mode="same")   # se le quita la media local
flujo = np.maximum(0, flujo)
flujo /= flujo.max() + 1e-9

# --- 2. tempo por autocorrelacion -----------------------------------------
f = flujo - flujo.mean()
ac = np.correlate(f, f, mode="full")[len(f) - 1:]
lo, hi = int(FPS * 60 / 165), int(FPS * 60 / 70)
lag = lo + int(np.argmax(ac[lo:hi]))
bpm = 60 * FPS / lag
# los tempos lentos suelen ser el doble de largo de lo que se siente al oido
while bpm < 88:
    bpm *= 2; lag /= 2
while bpm > 175:
    bpm /= 2; lag *= 2
periodo = 60.0 / bpm

# --- 3. fase ---------------------------------------------------------------
mejor, fase = -1, 0.0
for d in np.arange(0, periodo, 0.01):
    t = np.arange(d, len(flujo) / FPS, periodo)
    idx = (t * FPS).astype(int)
    idx = idx[idx < len(flujo)]
    v = flujo[idx].sum()
    if v > mejor:
        mejor, fase = v, d

tiempos = np.arange(fase, len(flujo) / FPS, periodo)

# --- 4. primer tiempo de compas (de cada 4) --------------------------------
peso = [flujo[((tiempos[k::4] * FPS).astype(int) < len(flujo)) &
              ((tiempos[k::4] * FPS).astype(int) >= 0)] .sum()
        if False else flujo[np.clip((tiempos[k::4] * FPS).astype(int), 0, len(flujo) - 1)].sum()
        for k in range(4)]
uno = int(np.argmax(peso))
downbeats = tiempos[uno::4]

# --- 6. golpes REALES, uno por compas ---------------------------------------
# Dos correcciones sobre la rejilla de tempo:
#   a) la rejilla se DESVIA. 114.8 BPM medidos frente a los ~117 reales son dos
#      segundos de deriva al final de un video de dos minutos, y un efecto clavado
#      a la rejilla acabaria sonando fuera de sitio.
#   b) los picos sueltos del flujo espectral son DEMASIADOS (440 en 109s, cuatro
#      por segundo): ajustarse a "el pico mas cercano" no significa nada, porque
#      siempre hay uno al lado.
# La solucion junta las dos: se recorre la rejilla compas a compas y en cada uno se
# busca el pico mas fuerte a un pelo del sitio esperado. Ese pico es el golpe bueno,
# y ademas re-ancla la rejilla, asi que la deriva no se acumula.
pico = flujo.copy()
VENTANA = 0.18
golpes, t, compas = [], float(downbeats[0]), periodo * 4
while t < len(flujo) / FPS:
    i0, i1 = int((t - VENTANA) * FPS), int((t + VENTANA) * FPS)
    i0, i1 = max(0, i0), min(len(pico), i1)
    if i1 > i0:
        j = i0 + int(np.argmax(pico[i0:i1]))
        if pico[j] > np.percentile(pico, 70):
            t = j / FPS                      # el golpe manda: la rejilla se re-ancla
    golpes.append(t)
    t += compas

# --- 7. donde arranca la cancion en el video --------------------------------
# El arranque se elige SOBRE los golpes, no sobre la rejilla: asi el frame 0 del
# video cae en un golpe de verdad y el whoosh de apertura suena con la musica.
# Se salta la intro (que suele venir sin bateria) y se pide energia suficiente.
energia = np.convolve(flujo, np.ones(int(FPS * 2)) / int(FPS * 2), mode="same")
umbral = np.percentile(energia, 45)
largo = len(x) / SR
inicio = float(golpes[0])
# preferencia: que ademas quepa el video entero sin dar la vuelta a la cancion
for exigir_cabida in (True, False):
    hallado = None
    for g in golpes:
        if g < SALTO_MIN:
            continue
        if exigir_cabida and g + dur_video > largo:
            continue
        i = int(g * FPS)
        if i < len(energia) and energia[i] >= umbral:
            hallado = float(g)
            break
    if hallado is not None:
        inicio = hallado
        break

# los golpes, ya en tiempo del VIDEO (0 = primer frame)
rel_t = [round(float(t - inicio), 3) for t in tiempos if inicio - 0.2 <= t <= inicio + dur_video]
rel_d = [round(float(t - inicio), 3) for t in downbeats if inicio - 0.2 <= t <= inicio + dur_video]

rel_g = [round(float(t - inicio), 3) for t in golpes if inicio - 0.2 <= t <= inicio + dur_video]

json.dump({"bpm": round(float(bpm), 1), "periodo": round(periodo, 4),
           "golpes": rel_g,
           "compas": round(periodo * 4, 4), "inicio_pista": round(inicio, 3),
           "tiempos": rel_t, "downbeats": rel_d}, sys.stdout, indent=1)
print(f"  compas: {bpm:.1f} BPM, compas de {periodo*4:.2f}s, la pista arranca en "
      f"{inicio:.2f}s (primer tiempo de compas con bateria), {len(rel_g)} golpes",
      file=sys.stderr)
