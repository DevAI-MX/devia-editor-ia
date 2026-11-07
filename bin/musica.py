#!/usr/bin/env python3
"""Cama musical sintetizada en local, con ducking bajo la voz.

Sintetizada y no descargada por dos razones: no hay problema de licencia para
publicar, y se puede generar exactamente de la duracion del video sin cortes raros.

Estilo sample de hip-hop / trap: acordes menores filtrados con caracter de vinilo,
bateria (kick, palmas, hats a semicorchea) y un 808 sosteniendo. El ritmo es lo que
aporta el pulso dopaminico; por eso no vale una cama ambiental.

Sigue sin haber MELODIA: si la musica se puede tararear, compite con lo que estas
diciendo. Lo que engancha aqui es el groove, no una linea melodica.

El ducking es real: se mide la envolvente de la voz del video ya cortado y la musica
baja donde hay habla. Sin eso, o la musica no se oye o se come la voz.

Uso: bin/musica.py <video_cortado> <duracion> salida.wav [nivel_dB] [tono]
"""
import os, subprocess, sys, tempfile, wave, struct
import numpy as np

SR = 48000
rng = np.random.default_rng(11)

src = sys.argv[1]
dur = float(sys.argv[2])
out = sys.argv[3]
NIVEL_DB = float(sys.argv[4]) if len(sys.argv) > 4 else -26.0
RAIZ = float(sys.argv[5]) if len(sys.argv) > 5 else 55.0     # sol#1 aprox

PISTA = os.environ.get("MUSICA_PISTA", "")   # mp3/wav real; si esta, manda sobre el sintetizado
# Caracter del sintetizado. "calma" (estilo reflexivo): acordes sostenidos y lentos, sin
# bateria ni 808. Cualquier otro valor: el sample de hip-hop de siempre.
CALMA = os.environ.get("MUSICA_CARACTER", "") == "calma"

n = int(SR * dur)
t = np.arange(n) / SR

if PISTA:
    # Musica real de la libreria. Se usa cuando la hay: un beat de verdad tiene
    # groove y variacion que un sintetizador no da. El sintetizado queda como
    # respaldo para cuando no hay pista a mano.
    wavp = os.path.join(tempfile.gettempdir(), "_pista.wav")
    subprocess.run(["ffmpeg", "-v", "error", "-i", PISTA,
                    "-ac", "1", "-ar", str(SR), "-f", "wav", wavp, "-y"], check=True)
    w = wave.open(wavp)
    p_ = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float64) / 32768
    # Se arranca donde dice bin/compas.py: en un golpe de verdad, ya con la
    # bateria dentro. Asi el frame 0 del video cae en el uno del compas y el
    # whoosh de apertura suena CON la musica. Antes eran 8s fijos, que caian
    # donde cayeran.
    salto = float(os.environ.get("MUSICA_INICIO", "8"))
    ini = min(int(SR * salto), max(0, len(p_) - n))
    p_ = p_[ini:]
    if len(p_) < n:
        p_ = np.tile(p_, int(np.ceil(n / len(p_))))
    cama = p_[:n]
    cama /= np.max(np.abs(cama)) + 1e-9
    # entrada y salida suaves para que no arranque ni corte de golpe
    fade = int(SR * 0.8)
    cama[:fade] *= np.linspace(0, 1, fade)
    fade_out = float(os.environ.get("MUSICA_FADE_OUT", "0.8"))
    if fade_out > 0:
        fo = int(SR * fade_out)
        cama[-fo:] *= np.linspace(1, 0, fo)
    # Editorial: la musica NO suena en el gancho. Entra EN el corte que lo cierra
    # (MUSICA_DESDE, en segundos del video), en seco, y sigue hasta el ultimo frame.
    desde = float(os.environ.get("MUSICA_DESDE", "0") or 0)
    if desde > 0:
        i = min(n, int(SR * desde))
        cama = np.concatenate([np.zeros(i), p_[:n - i]]) if n - i > 0 else np.zeros(n)
        cama /= np.max(np.abs(cama)) + 1e-9
        f2 = int(SR * 0.03)
        if n - i > f2:
            cama[i:i + f2] *= np.linspace(0, 1, f2)
        if fade_out > 0:
            fo = int(SR * fade_out)
            cama[-fo:] *= np.linspace(1, 0, fo)


# --- SINTETIZADO (respaldo si no hay pista real) ---------------------------
# --- SAMPLE: acordes menores filtrados, con caracter de vinilo -------------
# La referencia estetica es el sample de hip-hop / trap: un trozo de acorde que
# suena a disco viejo, no un pad sintetico. Se consigue con armonicos impares,
# un filtro que corta agudos y un poco de ruido de superficie.
GRADOS = [0, 8, 3, 10]                    # i - VI - III - VII
BPM = 84
if CALMA:
    GRADOS = [0, 7, 9, 5]                 # I - V - vi - IV, en mayor: sereno, sin drama
    BPM = 66
COMPAS = 60.0 / BPM * 4                   # un acorde por compas de 4 tiempos


def acorde(f, ini, largo, nivel):
    i0, i1 = int(ini * SR), min(int((ini + largo) * SR), n)
    if i1 <= i0:
        return
    m = i1 - i0
    tt = np.arange(m) / SR
    # ataque corto y caida: un sample tocado, no un pad que se sostiene
    if CALMA:   # ataque suave y cola larga: un piano con pedal, no un golpe
        env = np.exp(-tt * 0.55) * np.minimum(1.0, tt / 0.18)
        notas = [(0, 1.0), (4, 0.62), (7, 0.55), (11, 0.28), (12, 0.30)]
    else:
        env = np.exp(-tt * 1.9) * np.minimum(1.0, tt / 0.012)
        notas = [(0, 1.0), (3, 0.72), (7, 0.58), (10, 0.40), (12, 0.30)]
    onda = np.zeros(m)
    for semi, amp in notas:
        fr = f * 2 ** (semi / 12)
        for k, ka in [(1, 1.0), (2, 0.30), (3, 0.22), (5, 0.10)]:
            onda += amp * ka * np.sin(2 * np.pi * fr * k * tt + rng.uniform(0, 6))
    cama[i0:i1] += onda / 9.0 * env * nivel


if not PISTA:
  cama = np.zeros(n)
  c = 0
  while c * COMPAS < dur:
    g = GRADOS[c % len(GRADOS)]
    f0 = RAIZ * 2 ** (g / 12)
    ini = c * COMPAS
    acorde(f0, ini, COMPAS * 0.98, 0.62)
    if not CALMA:
        acorde(f0, ini + COMPAS / 2, COMPAS * 0.48, 0.34)   # repique a mitad de compas
    c += 1

  # --- BATERIA: el ritmo es lo que da el pulso dopaminico --------------------
  paso = 60.0 / BPM / 4                     # semicorchea


  def golpe(sig, t, gain=1.0):
    i = int(t * SR)
    m = min(len(sig), n - i)
    if i >= 0 and m > 0:
        cama[i:i + m] += sig[:m] * gain


  def kick():
    m = int(SR * 0.42)
    t = np.arange(m) / SR
    f = 105 * np.exp(-t * 26) + 44
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 7.5)


  def clap():
    m = int(SR * 0.26)
    x = rng.normal(0, 1, m)
    F = np.fft.rfft(x); f = np.fft.rfftfreq(m, 1 / SR)
    F[(f < 900) | (f > 5200)] = 0
    x = np.fft.irfft(F, m)
    e = np.exp(-np.arange(m) / SR * 16)
    for d in (0.008, 0.016):              # tres golpes = suena a palmas, no a ruido
        k = int(d * SR)
        e[k:] += np.exp(-np.arange(m - k) / SR * 18) * 0.6
    return x * e


  def hat(abierto=False):
    m = int(SR * (0.16 if abierto else 0.045))
    x = rng.normal(0, 1, m)
    F = np.fft.rfft(x); f = np.fft.rfftfreq(m, 1 / SR)
    F[f < 6500] = 0
    x = np.fft.irfft(F, m)
    return x * np.exp(-np.arange(m) / SR * (14 if abierto else 55))


  K, C, H, HO = kick(), clap(), hat(), hat(True)
  compases = int(dur / (paso * 16)) + 1
  for cc in (range(0) if CALMA else range(compases)):
    t0 = cc * paso * 16
    # patron de trap: kick en 1 y en el "y" del 3, clap en 2 y 4
    for p in (0, 6, 10):
        golpe(K, t0 + p * paso, 0.85)
    for p in (4, 12):
        golpe(C, t0 + p * paso, 0.42)
    for p in range(16):                   # hats a semicorchea, con dobles
        golpe(H, t0 + p * paso, 0.13 if p % 2 else 0.20)
        if p in (7, 15):
            golpe(H, t0 + (p + 0.5) * paso, 0.11)
    golpe(HO, t0 + 14 * paso, 0.14)

  # --- 808: la nota grave que sostiene el acorde ----------------------------
  for cc in (range(0) if CALMA else range(compases)):
    g = GRADOS[cc % len(GRADOS)]
    f0 = RAIZ * 2 ** (g / 12) / 2
    for p in (0, 10):
        i = int((cc * paso * 16 + p * paso) * SR)
        m = min(int(SR * 0.55), n - i)
        if i < 0 or m <= 0:
            continue
        tt = np.arange(m) / SR
        cama[i:i + m] += np.sin(2 * np.pi * f0 * tt) * np.exp(-tt * 3.4) * 0.5

  # ruido de superficie: lo que hace que suene a sample y no a sintetizador
  sup = rng.normal(0, 1, n)
  F = np.fft.rfft(sup); f = np.fft.rfftfreq(n, 1 / SR)
  F[(f < 2000) | (f > 9000)] = 0
  cama += np.fft.irfft(F, n) * (0.006 if CALMA else 0.02)

# --- se le quita el filo: una cama nunca lleva agudos --------------------
F = np.fft.rfft(cama); f = np.fft.rfftfreq(n, 1 / SR)
F *= np.clip(1.0 - np.maximum(0, f - 5200) / 9000, 0.0, 1.0)
cama = np.fft.irfft(F, n)
cama /= np.max(np.abs(cama)) + 1e-9

# --- ducking: la envolvente real de la voz del video ------------------------
wav = os.path.join(tempfile.gettempdir(), "_voz_para_duck.wav")
subprocess.run(["ffmpeg", "-v", "error", "-i", src, "-vn",
                "-ac", "1", "-ar", str(SR), "-f", "wav", wav, "-y"], check=True)
w = wave.open(wav)
voz = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float64) / 32768
voz = np.pad(voz, (0, max(0, n - len(voz))))[:n]

win = int(SR * 0.05)
env = np.sqrt(np.convolve(voz ** 2, np.ones(win) / win, mode="same"))
env /= np.percentile(env, 97) + 1e-9
env = np.clip(env, 0, 1)
# ataque rapido y recuperacion lenta: si sube de golpe al acabar la frase, se nota
suave = np.copy(env)
a, r = 0.004, 0.35
ca, cr = np.exp(-1 / (SR * a)), np.exp(-1 / (SR * r))
y = 0.0
for i in range(n):
    x = env[i]
    y = x + (ca if x > y else cr) * (y - x)
    suave[i] = y
DUCK_DB = -9.0
gan = 10 ** ((DUCK_DB * suave) / 20)
cama *= gan

cama *= 10 ** (NIVEL_DB / 20)
pcm = (np.clip(cama, -1, 1) * 32767).astype(np.int16)
w = wave.open(out, "w")
w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
w.writeframes(struct.pack("<%dh" % len(pcm), *pcm))
w.close()
rms = 20 * np.log10(np.sqrt((cama ** 2).mean()) + 1e-12)
_desde = float(os.environ.get("MUSICA_DESDE", "0") or 0)
_que = (f"pista real {os.path.basename(PISTA)}" if PISTA else (f"cama tranquila sintetizada, {len(GRADOS)} acordes a {BPM} bpm" if CALMA else f"sample hip-hop sintetizado, {len(GRADOS)} acordes a {BPM} bpm"))
print(f"{out}: {_que}, {dur:.1f}s" + (f", en silencio hasta {_desde:.2f}s" if _desde > 0 else "")
      + f", ducking {DUCK_DB:.0f} dB bajo la voz, RMS {rms:.1f} dB")
