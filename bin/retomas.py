#!/usr/bin/env python3
"""Detecta retomas: el hablante arranca una frase, se corta, y la repite entera.

Por que no vale mirar el transcript completo: whisper alinea la palabra partida a
caballo de las dos tomas ("ansiedad" ocupando desde el intento roto hasta el bueno),
asi que el fragmento corto sale sin palabras propias y la retoma pasa desapercibida.
La forma fiable es transcribir el fragmento POR SEPARADO y compararlo con el arranque
de lo que viene detras.

Regla: un fragmento corto se DESCARTA si lo que dice es el arranque de lo que sigue
(retoma). Si no, se FUSIONA con el vecino, porque un fragmento suelto de menos de un
segundo en plano fijo se lee como un hipo.

Uso: bin/retomas.py cortes.json <media_fuente> [min_util] > cortes_limpios.json
"""
import difflib, json, os, subprocess, sys, tempfile, unicodedata
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cfg import cfg

from transcriptor import crear_motor

FFMPEG = "ffmpeg"

cortes = json.load(open(sys.argv[1]))
media = sys.argv[2]
MIN_UTIL = float(sys.argv[3]) if len(sys.argv) > 3 else cfg("cortes.fragmento_util", 1.2)
tmp = tempfile.mkdtemp()


def norm(t):
    t = unicodedata.normalize("NFD", t.lower())
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    return "".join(c for c in t if c.isalnum() or c.isspace()).split()


# El modelo se carga UNA vez. Antes esto llamaba al ejecutable mlx_whisper por
# cada fragmento: un video con 22 fragmentos cortos son 44 arranques del proceso,
# y cada uno vuelve a cargar large-v3 entero. Se iba a mas de diez minutos por
# video transcribiendo unos pocos segundos de audio. Con un solo motor en memoria,
# el modelo queda cacheado entre llamadas.
MOTOR = crear_motor()


def transcribe(ini, dur, etq):
    wav = os.path.join(tmp, f"{etq}.wav")
    subprocess.run([FFMPEG, "-v", "error", "-ss", f"{ini:.3f}", "-i", media,
                    "-t", f"{dur:.3f}", "-vn", "-ac", "1", "-ar", "16000", wav, "-y"],
                   check=True)
    return norm(MOTOR.transcribir(wav)["text"])


keep = [list(x) for x in cortes["keep"]]
notas, descartes, fusiones = [], 0, 0

i = 0
while i < len(keep):
    a, b = keep[i]
    if b - a >= MIN_UTIL or len(keep) == 1:
        i += 1
        continue

    corto = transcribe(a, b - a, f"corto{i}")
    if i + 1 < len(keep):
        na, nb = keep[i + 1]
        siguiente = transcribe(na, min(2.2, nb - na), f"sig{i}")
    else:
        siguiente = []

    # se compara por prefijo: la toma rota corta a media palabra, asi que
    # "tuanciet" tiene que casar contra "tu ansiedad"
    def pegado(ws):
        return "".join(ws)

    # Comparacion por SIMILITUD, no por prefijo exacto: la toma rota sale mal
    # transcrita justamente por estar cortada ("tuanciet" en vez de "tu ansied"),
    # asi que una sola letra distinta tumbaria la deteccion.
    es_retoma = False
    parecido = 0.0
    if corto and siguiente:
        c, s_ = pegado(corto), pegado(siguiente)
        n = max(4, min(len(c), 14))
        parecido = difflib.SequenceMatcher(None, c[:n], s_[:n]).ratio()
        es_retoma = parecido >= cfg("cortes.retoma_parecido", 0.6)

    if es_retoma:
        notas.append(f"RETOMA descartada {a:.3f}-{b:.3f} ({b - a:.2f}s): dice "
                     f"'{' '.join(corto)}' y la toma buena que viene detras empieza "
                     f"'{' '.join(siguiente[:4])}' (parecido {parecido:.2f})")
        del keep[i]
        descartes += 1
    elif i + 1 < len(keep):
        notas.append(f"fusionado {a:.3f}-{b:.3f} ({b - a:.2f}s) con el siguiente: "
                     f"dice '{' '.join(corto) or '(nada)'}', no es retoma "
                     f"(parecido {parecido:.2f})")
        keep[i][1] = keep[i + 1][1]
        del keep[i + 1]
        fusiones += 1
    else:
        keep[i - 1][1] = b
        del keep[i]
        fusiones += 1

cortes["keep"] = [(round(a, 3), round(b, 3)) for a, b in keep]
cortes["out_duration"] = round(sum(b - a for a, b in cortes["keep"]), 3)
cortes["segments"] = len(cortes["keep"])
cortes["retomas_descartadas"] = descartes
cortes["fusiones"] = fusiones
json.dump(cortes, sys.stdout, indent=1)
for n in notas:
    print(f"  {n}", file=sys.stderr)
