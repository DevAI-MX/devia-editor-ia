#!/usr/bin/env python3
"""Genera la pista de SFX sincronizada a los cues y beats. Todo sintetizado en local.

Piezas:
  click   ~14ms, ruido filtrado 2.5-6kHz con decaimiento rapido. Va en cada cue
          de subtitulo: es el "tic" al aparecer la palabra.
  whoosh  ~380ms, ruido con barrido de filtro ascendente. Va antes de cada stinger.
  impact  ~500ms, golpe de 55Hz + capa de click. Va en la entrada del stinger.
  corte   ~90ms, transitorio seco tipo empalme de pelicula. Marca la aparicion y
          la salida del b-roll: sin el, el cambio de imagen se siente flotante.

Salida: un unico WAV de la duracion del video -> se monta como UN solo <audio>
en la composicion (mucho mas barato que N elementos de audio).

Uso: bin/sfx.py cues.json <duracion_seg> salida.wav [beats.json] [zooms.json] [keywords.json]
"""
import json, os, subprocess, sys, wave, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cfg import cfg
import numpy as np

SR = 48000
rng = np.random.default_rng(7)


def env(n, decay):
    return np.exp(-np.linspace(0, decay, n))


def click(level=0.16):
    n = int(SR * 0.014)
    x = rng.normal(0, 1, n)
    # banda 2.5-6 kHz via FFT (suficiente y sin dependencias)
    F = np.fft.rfft(x)
    f = np.fft.rfftfreq(n, 1 / SR)
    F[(f < 2200) | (f > 6500)] = 0
    x = np.fft.irfft(F, n)
    x *= env(n, 9)
    return x / (np.max(np.abs(x)) + 1e-9) * level


def whoosh(level=0.22):
    n = int(SR * 0.38)
    x = rng.normal(0, 1, n)
    F = np.fft.rfft(x)
    f = np.fft.rfftfreq(n, 1 / SR)
    F[(f < 300) | (f > 9000)] = 0
    x = np.fft.irfft(F, n)
    sweep = np.linspace(0, 1, n) ** 2          # sube de energia hacia el final
    x *= sweep * np.hanning(n)
    return x / (np.max(np.abs(x)) + 1e-9) * level


def impact(level=0.5):
    n = int(SR * 0.5)
    t = np.arange(n) / SR
    f0 = 90 * np.exp(-t * 7) + 45              # pitch cayendo: golpe cinematico
    body = np.sin(2 * np.pi * np.cumsum(f0) / SR) * env(n, 7)
    x = body.copy()
    c = click(1.0)
    x[: len(c)] += c * 0.5
    return x / (np.max(np.abs(x)) + 1e-9) * level


def sala(x, decay=2.6, mezcla=0.34, pre=0.012):
    """Cola de sala. Es lo que hace que un sonido suene 'cinematico' en vez de
    pegado: sin cola, el efecto se oye ENCIMA del video; con cola, se oye DENTRO.
    Reverb sintetica = convolucion con ruido que decae exponencialmente."""
    n = int(SR * decay)
    ir = rng.normal(0, 1, n) * np.exp(-np.linspace(0, 7, n))
    # la sala se come los agudos antes que los graves, como una sala de verdad
    F = np.fft.rfft(ir); f = np.fft.rfftfreq(n, 1 / SR)
    F *= np.clip(1.0 - (f / 9000) ** 1.4, 0.02, 1.0)
    ir = np.fft.irfft(F, n)
    ir /= np.max(np.abs(ir)) + 1e-9
    mojado = np.convolve(x, ir)[: len(x) + n]
    mojado /= np.max(np.abs(mojado)) + 1e-9
    seco = np.pad(x, (0, len(mojado) - len(x)))
    y = seco * (1 - mezcla) + np.roll(mojado, int(SR * pre)) * mezcla
    return y / (np.max(np.abs(y)) + 1e-9)


def marea(level=0.16, dur=1.3):
    """SUSTITUYE AL RISER, que era el unico efecto que no encajaba: un barrido de
    ruido subiendo llama la atencion sobre si mismo, es lenguaje de trailer.
    Esto es un swell de graves que crece poco y se apoya en la cola de sala, no en
    el volumen. El resto de efectos se quedan como estaban."""
    n = int(SR * dur)
    t = np.arange(n) / SR
    sube = (np.linspace(0, 1, n) ** 1.6)
    cuerpo = (np.sin(2 * np.pi * 52 * t) * 0.6 + np.sin(2 * np.pi * 78 * t) * 0.4) * sube
    aire = rng.normal(0, 1, n)
    F = np.fft.rfft(aire); f = np.fft.rfftfreq(n, 1 / SR)
    F[(f < 90) | (f > 1400)] = 0                 # solo medios-graves, nada de sibilancia
    aire = np.fft.irfft(F, n) * sube * 0.25
    x = cuerpo + aire
    return sala(x, decay=2.2, mezcla=0.30)[:n + SR] * level


def subdrop(level=0.42):
    """Caida de sub-graves. Peso, no volumen: se siente mas que se oye."""
    n = int(SR * 0.75)
    t = np.arange(n) / SR
    f0 = 120 * np.exp(-t * 4.5) + 28
    x = np.sin(2 * np.pi * np.cumsum(f0) / SR) * env(n, 4.5)
    return x / (np.max(np.abs(x)) + 1e-9) * level


def reversa(level=0.24, dur=0.55):
    """Barrido invertido: el sonido crece hasta el corte y se corta en seco.
    Es lo que hace que un cambio de plano se sienta 'succionado'."""
    n = int(SR * dur)
    x = rng.normal(0, 1, n)
    F = np.fft.rfft(x); f = np.fft.rfftfreq(n, 1 / SR)
    F[(f < 700) | (f > 9000)] = 0
    x = np.fft.irfft(F, n) * (np.linspace(0, 1, n) ** 2.8)
    return x / (np.max(np.abs(x)) + 1e-9) * level


def brillo(level=0.16):
    """Destello agudo para revelados: una campana corta y cristalina."""
    n = int(SR * 0.45)
    t = np.arange(n) / SR
    x = sum(np.sin(2 * np.pi * fr * t) * np.exp(-t * d)
            for fr, d in [(3200, 9), (4800, 12), (6400, 16), (9100, 22)])
    return x / (np.max(np.abs(x)) + 1e-9) * level


def glitch(level=0.22):
    """Corte digital: trocitos de ruido con silencios entre medias."""
    n = int(SR * 0.16)
    x = rng.normal(0, 1, n)
    F = np.fft.rfft(x); f = np.fft.rfftfreq(n, 1 / SR)
    F[(f < 900) | (f > 8000)] = 0
    x = np.fft.irfft(F, n)
    paso = n // 8
    for i in range(0, n, paso * 2):
        x[i:i + paso] *= 0.06
    return x / (np.max(np.abs(x)) + 1e-9) * level


def corte(level=0.34):
    """Transitorio seco de cambio de plano: ruido de banda ancha con caida muy
    rapida y un poco de cuerpo grave. No es un golpe dramatico, es el 'clac' que
    hace que el cambio de imagen se sienta hecho a proposito."""
    n = int(SR * 0.09)
    x = rng.normal(0, 1, n)
    F = np.fft.rfft(x)
    f = np.fft.rfftfreq(n, 1 / SR)
    F[(f < 400) | (f > 11000)] = 0
    x = np.fft.irfft(F, n) * env(n, 16)
    t = np.arange(n) / SR
    cuerpo = np.sin(2 * np.pi * (160 * np.exp(-t * 26) + 70) * t) * env(n, 13) * 0.55
    x = x / (np.max(np.abs(x)) + 1e-9) + cuerpo
    return x / (np.max(np.abs(x)) + 1e-9) * level


def arranque(level=0.34):
    """El golpe del primer frame. No es el mismo whoosh que anuncia un stinger.

    Aquel SUBE de energia porque anticipa algo que va a pasar; este CAE, porque
    el zoom out ya esta pasando en el frame 0 y el sonido tiene que acompanarlo
    hacia afuera. Ataque instantaneo, barrido de filtro descendente y una cola
    grave corta que le da cuerpo. Puesto a subir, sonaba a que faltaba algo
    despues."""
    n = int(SR * 0.62)
    x = rng.normal(0, 1, n)
    F = np.fft.rfft(x)
    f = np.fft.rfftfreq(n, 1 / SR)
    F[(f < 220) | (f > 12000)] = 0
    x = np.fft.irfft(F, n)
    # el filtro se cierra: el ruido pasa de brillante a oscuro mientras se apaga
    corte = np.linspace(1.0, 0.12, n)
    x = x * corte * np.exp(-np.linspace(0, 5.5, n))
    # cuerpo grave que cae, para que el zoom out tenga peso y no solo aire
    t = np.arange(n) / SR
    cuerpo = np.sin(2 * np.pi * np.cumsum(320 * np.exp(-t * 4.5) + 58) / SR) * np.exp(-t * 6.0)
    x = x / (np.max(np.abs(x)) + 1e-9) + cuerpo * 0.65
    return x / (np.max(np.abs(x)) + 1e-9) * level


cues = json.load(open(sys.argv[1]))
dur = float(sys.argv[2])
out = sys.argv[3]
beats = json.load(open(sys.argv[4])) if len(sys.argv) > 4 and sys.argv[4] else {}
zooms = json.load(open(sys.argv[5])) if len(sys.argv) > 5 and sys.argv[5] else []
keys = json.load(open(sys.argv[6])) if len(sys.argv) > 6 and sys.argv[6] else []

track = np.zeros(int(SR * dur) + SR, dtype=np.float64)


def place(sig, at, gain=1.0):
    i = int(at * SR)
    if i < 0:
        sig = sig[-i:]; i = 0
    if i >= len(track):
        return                      # el efecto cae fuera del video: no hay donde ponerlo
    j = min(i + len(sig), len(track))
    if j <= i:
        return
    track[i:j] += sig[: j - i] * gain


CLICK = click()
# NO hay click en el subtitulo normal: el tic solo marca las frases principales.
# Si sonara en cada cue dejaria de significar nada.

# Cada tipo de motion graphic suena distinto: si todos entran con el mismo golpe,
# a la tercera vez el oido lo descuenta y deja de funcionar. La paleta se elige por
# lo que muestra el grafico, igual que se elige el fondo.
# Paleta cinematica: grave, con cola de sala y de nivel bajo. La regla es que el
# efecto se mezcle con el ambiente, no que se monte encima. Por eso NO hay risers
# de ruido subiendo: eso llama la atencion sobre el propio efecto.
PALETA = {
    "pulso":   ["marea", "subdrop"],       # cuerpo, urgencia
    "alerta":  ["glitch", "impact"],       # error, peligro
    "cifra":   ["reversa", "brillo"],      # el dato aterriza
    "flecha":  ["marea", "brillo"],        # algo que sube
    "barras":  ["reversa", "impact"],      # comparacion
    "anillos": ["marea", "subdrop"],       # algo que se propaga
    "malla":   ["reversa", "impact"],      # sistema
    "orbe":    ["marea", "brillo"],        # revelado
    "ondas":   ["reversa", "subdrop"],     # algo que llega
    "icono":   ["reversa", "brillo"],      # pictograma que aparece
}
# Niveles bajados: el barrido (reversa) y la marea se oian por encima de la voz.
# Los clicks de las frases se quedan como estaban, que esos si gustan.
N = lambda k, d: cfg("audio.sfx." + k, d)

# --- efectos de archivo ---------------------------------------------------
# Los golpes sinteticos valen para los clicks, pero un cambio de plano pide un
# sonido con cuerpo. Estos salen de la libreria propia (assets/sfx y
# assets/sfx-cine) y se declaran en el formato, no aqui.
# Dos bibliotecas: la del repo y la del usuario. Las rutas del formato se buscan en
# las dos, en orden, asi que se escriben cortas y sin depender de donde este cada una.
RAICES = [
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets"),
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "musica"),
]
_cache = {}


def archivo(ruta, nivel=1.0, maxdur=None):
    """Carga un efecto de la libreria y lo devuelve a SR mono, normalizado."""
    if not ruta:
        return None
    full = ruta if os.path.isabs(ruta) else None
    if full is None:
        for r in RAICES:
            cand = os.path.join(r, ruta)
            if os.path.exists(cand):
                full = cand
                break
    if not full or not os.path.exists(full):
        print(f"  AVISO: no encuentro el efecto {ruta}", file=sys.stderr)
        return None
    if full not in _cache:
        crudo = subprocess.run(
            ["ffmpeg", "-v", "error", "-i", full,
             "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"],
            capture_output=True).stdout
        a = np.frombuffer(crudo, dtype=np.float32).astype(np.float64)
        # Se le quita el silencio de delante. Muchos efectos de biblioteca traen
        # relleno al principio — el obturador de camara trae 165 ms — y si no se
        # recorta, el golpe cae tarde respecto al corte por mucho que se ajuste el
        # adelanto. Recortado, el sonido empieza donde empieza de verdad.
        if len(a):
            env = np.abs(a)
            fuera = np.where(env > env.max() * 0.06)[0]
            if len(fuera) and fuera[0] > 0:
                a = a[fuera[0]:]
        pico = np.max(np.abs(a)) if len(a) else 0
        _cache[full] = a / pico if pico > 0 else a
    a = _cache[full].copy()
    if maxdur:
        n = int(maxdur * SR)
        if len(a) > n:
            a = a[:n] * np.concatenate([np.ones(n - 400), np.linspace(1, 0, 400)])
    return a * nivel
CAPAS = {"marea": lambda: (marea(N("marea", .09)), -1.15),
         "subdrop": lambda: (subdrop(N("subdrop", .26)), -0.02),
         "reversa": lambda: (reversa(N("reversa", .12)), -0.52),
         "brillo": lambda: (brillo(N("brillo", .10)), 0.02),
         "glitch": lambda: (glitch(N("glitch", .13)), -0.10),
         "impact": lambda: (impact(N("impact", .15)), -0.04)}

# Si el formato lo pide, el cambio de plano suena SOLO con el efecto de archivo (el
# obturador de camara a la entrada y a la salida) y la paleta sintetica se calla.
# Regla del usuario: "que solo suene el sonido de la camara, de entrada y de salida".
SOLO_ARCHIVO = bool(cfg("audio.sfx_archivo.solo_archivo", False))
for b in beats.get("stingers", []):
    for nombre in ([] if SOLO_ARCHIVO else PALETA.get(b.get("tipo"), ["reversa", "impact"])):
        sig, desfase = CAPAS[nombre]()
        place(sig, b["at"] + desfase)
    # El cambio de plano: si el formato declara un efecto de archivo se usa ese,
    # que tiene cuerpo de verdad; si no, el transitorio sintetico de siempre.
    ent = archivo(cfg("audio.sfx_archivo.broll_entra", ""),
                  N("archivo_entra", .55), cfg("audio.sfx_archivo.max_dur", 1.1))
    if ent is not None:
        place(ent, b["at"] - cfg("audio.sfx_archivo.adelanto", 0.22))
    else:
        place(corte(N("corte_entrada", .20)), b["at"] - 0.15)
    sal = archivo(cfg("audio.sfx_archivo.broll_sale", ""),
                  N("archivo_sale", .34), cfg("audio.sfx_archivo.max_dur", 1.1))
    if sal is not None:
        place(sal, b["at"] + b.get("dur", 1.0) - 0.20)
    else:
        place(corte(N("corte_vuelta", .15)), b["at"] + b.get("dur", 1.0) - 0.14)

# --- golpe dramatico ------------------------------------------------------
# Un boom de trailer debajo de la palabra que pesa. No va en cada corte: eso cansa
# y deja de significar nada. Va SOLO en las palabras con acento, y aun asi
# racionado, porque un golpe cada dos frases se convierte en ruido de fondo.
DRAM = cfg("audio.sfx_archivo.dramatico", None)
n_boom = 0
if DRAM and DRAM.get("archivo"):
    pares_p = os.path.join(os.path.dirname(os.path.abspath(out)), "pares.json")
    momentos = []
    if os.path.exists(pares_p):
        for par in json.load(open(pares_p)):
            for w in par.get("palabras", []):
                if w.get("acento") or w.get("ambar"):
                    momentos.append(w["at"])
    else:   # sin pares (formatos de bloque) se usa el arranque de cada frase animada
        momentos = [k["at"] for k in keys]
    boom = archivo(DRAM["archivo"], DRAM.get("nivel", 0.30), DRAM.get("max_dur", 2.6))
    if boom is not None:
        cada = DRAM.get("cada", 14.0)
        puestos = []
        for t in sorted(momentos):
            if puestos and t - puestos[-1] < cada:
                continue
            place(boom, t - DRAM.get("adelanto", 0.12))
            puestos.append(t)
            n_boom += 1

# EL GANCHO SUENA. En los primeros segundos cada palabra que entra lleva su propio
# click ligero: es lo que hace que el ojo siga la linea palabra a palabra en vez de
# leerla de un vistazo y soltar el video. Fuera del gancho NO suena — si sonara todo
# el rato dejaria de significar nada (por eso el subtitulo normal va mudo).
GANCHO = cfg("gancho.dur", 0.0)
n_gancho = 0
if GANCHO:
    _pares_p = os.path.join(os.path.dirname(os.path.abspath(out)), "pares.json")
    if os.path.exists(_pares_p):
        _nivel = cfg("gancho.click_nivel", 0.85)
        for par in json.load(open(_pares_p)):
            for w in par.get("palabras", []):
                if w["at"] < GANCHO:
                    place(CLICK, w["at"], gain=_nivel)
                    n_gancho += 1

# CLICK POR SUBTITULO. Cada vez que entra una pareja de lineas (o un cue, en los
# formatos de una linea) suena un click pequeno. Pedido por el editor. Dentro del
# gancho ya suena uno por palabra, asi que ahi no se dobla.
CLICK_SUB = cfg("audio.click_subtitulo", None)
n_sub = 0
if CLICK_SUB:
    _nivel = float(CLICK_SUB.get("nivel", 0.45)) if isinstance(CLICK_SUB, dict) else 0.45
    _pares_p = os.path.join(os.path.dirname(os.path.abspath(out)), "pares.json")
    if os.path.exists(_pares_p):
        momentos_sub = [par["at"] for par in json.load(open(_pares_p))]
    else:
        momentos_sub = [c["start"] for c in cues]
    for t in momentos_sub:
        if t >= GANCHO:
            place(CLICK, t, gain=_nivel)
            n_sub += 1

# cada palabra de keyword entra con su propio click, un poco mas presente que
# el del subtitulo: es el sonido que hace que la palabra "caiga" en su sitio
n_pal = 0
for k in keys:
    for i, p in enumerate(k.get("palabras", [])):
        place(CLICK, p["at"], gain=1.5 if i == 0 else 1.15)
        n_pal += 1

# gancho auditivo del arranque: cae en el frame 0, a la vez que el zoom out.
# Solo si el formato lo pide (el whoosh de apertura es de la marca, no de todos).
n_arranque = cfg("arranque.activo", False)
_arr_arch = cfg("arranque.sfx_archivo", "")
if n_arranque and _arr_arch:
    # GANCHO AUDITIVO desde la biblioteca (regla del usuario, 10-sep): un whoosh en el
    # frame 0 cuyo PICO cae donde aterriza el zoom out (`sfx_pico_en`, 0.17s). El
    # archivo se recorta por delante para que empiece justo en el 0.
    _w = archivo(_arr_arch, float(cfg("arranque.sfx_nivel", 0.5)), float(cfg("arranque.sfx_max_dur", 1.4)))
    if _w is not None:
        _env = np.abs(_w); _W = int(SR * 0.02)
        _sm = np.convolve(_env, np.ones(_W) / _W, mode="same"); _pk = int(_sm.argmax())
        _des = max(0, _pk - int(float(cfg("arranque.sfx_pico_en", 0.17)) * SR))
        place(_w[_des:], 0.0)
elif n_arranque:
    place(arranque(cfg("arranque.sfx_nivel", cfg("audio.sfx.whoosh_arranque", 0.34))), 0.0)

# ============ EDITORIAL: riser que cierra el gancho + tick doble en cada corte ============
# Medido en las 6 referencias: el gancho es voz desnuda; a 1.0-1.7s del corte que lo
# cierra sube un riser (ruido filtrado que trepa + rumble) que pica MAS ALTO que la
# voz y se corta EN SECO en el jump cut; ahi mismo entra la musica. En el cuerpo, el
# unico efecto es un tick doble (dos transitorios de 5-10 ms a 70-120 ms) pegado a
# cada punch-in/corte. Sin obturador, sin boom, sin whoosh de zoom.
RISER = cfg("audio.riser", None)
_fin_g = float(os.environ.get("GANCHO_FIN", "0") or 0)
n_riser = 0
if RISER and RISER.get("archivo") and _fin_g > 0:
    r = archivo(RISER["archivo"], RISER.get("nivel", 0.55), None)
    if r is not None:
        dur_r = float(RISER.get("dur", 1.4))
        # se alinea el PICO del riser con el corte y se corta ahi en seco
        env_r = np.abs(r); W = int(SR * 0.05)
        sm = np.convolve(env_r, np.ones(W) / W, mode="same")
        pico = int(sm.argmax())
        ini = max(0, pico - int(dur_r * SR))
        trozo = r[ini:pico].copy()
        if len(trozo) > SR * 0.2:
            fi = int(SR * 0.25)
            trozo[:fi] *= np.linspace(0, 1, fi)          # entra desde nada
            place(trozo, _fin_g - len(trozo) / SR)
            n_riser = 1

TICK = cfg("audio.tick_cortes", None)
n_tick = 0
if TICK and TICK.get("activo"):
    _cortes_p = os.environ.get("CORTES_JSON", "")
    bordes, acc = [], 0.0
    if _cortes_p and os.path.exists(_cortes_p):
        for a_, b_ in json.load(open(_cortes_p))["keep"][:-1]:
            acc += b_ - a_; bordes.append(round(acc, 3))
    sep = float(TICK.get("separacion", 0.08)); niv = float(TICK.get("nivel", 0.5))
    # El tick sale de la BIBLIOTECA del usuario si el formato lo declara (regla del
    # usuario: los efectos se toman de la carpeta de edicion), y solo si no hay
    # archivo se sintetiza. Se recorta a `max_dur` para que siga siendo un tick.
    _arch = archivo(TICK.get("archivo", ""), 1.0, TICK.get("max_dur", 0.12)) if TICK.get("archivo") else None
    if _arch is not None:
        t1 = _arch; t2 = _arch * 0.8
    else:
        t1 = click(1.0); t2 = click(0.8)
    if not TICK.get("doble", True):
        t2 = None
    # si hay zooms decididos por zoomcortes.py, el tick va SOLO en los cortes con
    # cambio de encuadre (regla del usuario: no tantos ni tan de pronto)
    _zc = os.environ.get("ZOOM_CORTES", "")
    if _zc and os.path.exists(_zc):
        bordes = [z["at"] for z in json.load(open(_zc)) if z.get("cambio")]
    for c in bordes:
        place(t1, c, gain=niv)
        if t2 is not None:
            place(t2, c + sep, gain=niv)
        n_tick += 1

# el zoom seco pide un golpe: sin sonido, el punch se lee como un fallo de video
for z in zooms:
    if z.get("tipo") == "punch":
        place(impact(N("impacto_zoom", .18)), z["at"])
    else:
        place(whoosh(N("whoosh_zoom", .06)), z["at"] - 0.18)

peak = np.max(np.abs(track))
if peak > 0.95:
    track *= 0.95 / peak

pcm = (np.clip(track, -1, 1) * 32767).astype(np.int16)
w = wave.open(out, "w")
w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
w.writeframes(struct.pack("<%dh" % len(pcm), *pcm))
w.close()
if n_arranque:
    print("  whoosh de arranque en el 0 (gancho auditivo)")
if n_boom:
    print(f"  {n_boom} golpes dramaticos bajo las palabras con acento")
print(f"{out}: {n_gancho} clicks del gancho + {n_sub} clicks de subtitulo + {n_pal} clicks de frase principal + {n_riser} riser + {n_tick} ticks de corte + "
      f"{len(beats.get('stingers', []))} transiciones (paleta por tipo + corte de "
      f"entrada y de vuelta) + {len(zooms)} zooms, "
      f"{len(pcm)/SR:.1f}s, pico {np.max(np.abs(track)):.2f}")
