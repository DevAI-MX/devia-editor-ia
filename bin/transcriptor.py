#!/usr/bin/env python3
"""Transcripcion por palabra, igual en cualquier equipo.

Mac con chip Apple: mlx-whisper, que corre en la GPU del chip.
Windows, Linux y Mac con Intel: faster-whisper en el procesador (int8). Con una
tarjeta NVIDIA y CUDA instalado se puede pedir la GPU con KIT_WHISPER_DISPOSITIVO=cuda.

Los dos motores entregan el mismo JSON (text, segments con words, language), que es
lo que leen cues.py y el resto del kit. Siempre en espanol y sin condicionar cada
tramo al anterior: con condition_on_previous_text, whisper repite frases enteras.

Uso: bin/py bin/transcriptor.py <audio_o_video> [--output-dir DIR] [--initial-prompt TEXTO]
     bin/py bin/transcriptor.py --descargar-modelo
Acepta tambien los argumentos de mlx_whisper que usaba el kit (--model, --language,
--word-timestamps, --condition-on-previous-text, --output-format).
"""
import argparse
import json
import os
import platform
import subprocess
import sys

IDIOMA = "es"
MUESTREO = 16000
MODELO = os.environ.get("KIT_MODELO_WHISPER", "large-v3")
# mlx-community no nombra igual todos sus repositorios: turbo va sin el sufijo -mlx.
REPOS_MLX = {
    "large-v3": "mlx-community/whisper-large-v3-mlx",
    "large-v3-turbo": "mlx-community/whisper-large-v3-turbo",
}


class TranscriptorNoInstalado(RuntimeError):
    pass


class AudioIlegible(RuntimeError):
    pass


def es_chip_apple(sistema=None, maquina=None):
    sistema = sistema or platform.system()
    maquina = maquina or platform.machine()
    return sistema == "Darwin" and maquina == "arm64"


def normalizar_modelo(nombre):
    corto = nombre.rsplit("/", 1)[-1]
    corto = corto.removeprefix("whisper-").removesuffix("-mlx")
    return corto


def repositorio_mlx(modelo):
    return REPOS_MLX.get(modelo, f"mlx-community/whisper-{modelo}-mlx")


class MotorMlx:
    def __init__(self, modelo):
        import mlx_whisper
        self._mlx = mlx_whisper
        self._repo = repositorio_mlx(modelo)

    def transcribir(self, ruta, prompt=None):
        return self._mlx.transcribe(str(ruta), path_or_hf_repo=self._repo, language=IDIOMA,
                                    word_timestamps=True, condition_on_previous_text=False,
                                    initial_prompt=prompt, verbose=None)

    def descargar(self):
        from huggingface_hub import snapshot_download
        snapshot_download(self._repo)


class MotorFaster:
    def __init__(self, modelo):
        from faster_whisper import WhisperModel
        self._crear = lambda: _modelo_faster(WhisperModel, modelo)
        self._modelo = None

    def _cargado(self):
        # El modelo se carga una vez y se reusa: retomas.py transcribe decenas de tramos.
        if self._modelo is None:
            self._modelo = self._crear()
        return self._modelo

    def transcribir(self, ruta, prompt=None):
        segmentos, info = self._cargado().transcribe(leer_audio(ruta), language=IDIOMA, word_timestamps=True,
                                                     condition_on_previous_text=False,
                                                     initial_prompt=prompt)
        return a_formato_whisper(list(segmentos), info.language)

    def descargar(self):
        self._cargado()


def leer_audio(ruta):
    """Audio a 16 kHz, mono, float32 entre -1 y 1, que es lo que recibe whisper.

    Lo decodifica ffmpeg, que el kit ya necesita. faster-whisper lo haria con PyAV, y
    PyAV 19 quito el argumento metadata_errors que faster-whisper 1.2.1 le pasa.
    """
    import numpy as np
    r = subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-i", str(ruta), "-f", "f32le",
                        "-ac", "1", "-ar", str(MUESTREO), "-"], capture_output=True)
    if r.returncode != 0:
        raise AudioIlegible(f"ffmpeg no pudo leer {ruta}: {r.stderr.decode('utf-8', 'replace').strip()}")
    return np.frombuffer(r.stdout, dtype=np.float32)


def _modelo_faster(clase, modelo):
    if os.environ.get("KIT_WHISPER_DISPOSITIVO") == "cuda":
        return clase(modelo, device="cuda", compute_type="float16")
    return clase(modelo, device="cpu", compute_type="int8", cpu_threads=os.cpu_count() or 4)


def crear_motor(modelo=MODELO, chip_apple=None):
    if chip_apple is None:
        chip_apple = es_chip_apple()
    try:
        return MotorMlx(modelo) if chip_apple else MotorFaster(modelo)
    except ImportError as e:
        raise TranscriptorNoInstalado(
            f"No esta instalado el transcriptor ({e.name}). Ejecuta 'bash setup.sh' en la carpeta del editor.") from e


def a_formato_whisper(segmentos, idioma):
    return {
        "text": "".join(s.text for s in segmentos),
        "segments": [_segmento(s) for s in segmentos],
        "language": idioma,
    }


def _segmento(s):
    return {
        "id": s.id, "seek": s.seek, "start": round(s.start, 3), "end": round(s.end, 3), "text": s.text,
        "tokens": list(s.tokens), "temperature": s.temperature, "avg_logprob": s.avg_logprob,
        "compression_ratio": s.compression_ratio, "no_speech_prob": s.no_speech_prob,
        "words": [{"word": w.word, "start": round(w.start, 3), "end": round(w.end, 3),
                   "probability": round(w.probability, 4)} for w in (s.words or [])],
    }


def tiempo_srt(segundos):
    ms = round(segundos * 1000)
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def a_srt(resultado):
    bloques = [f"{i}\n{tiempo_srt(s['start'])} --> {tiempo_srt(s['end'])}\n{s['text'].strip()}\n"
               for i, s in enumerate(resultado["segments"], 1)]
    return "\n".join(bloques)


def escribir_json(resultado, ruta):
    with open(ruta, "w", encoding="utf-8", newline="\n") as f:
        json.dump(resultado, f, ensure_ascii=False)


def _escribir_texto(texto, ruta):
    with open(ruta, "w", encoding="utf-8", newline="\n") as f:
        f.write(texto)


def _argumentos(argv):
    p = argparse.ArgumentParser(description="Transcripcion por palabra en espanol.")
    p.add_argument("entrada", nargs="?")
    p.add_argument("--output-dir")
    p.add_argument("--initial-prompt")
    p.add_argument("--model", default=MODELO)
    p.add_argument("--language", default=IDIOMA, choices=[IDIOMA])
    p.add_argument("--output-format", default="json+srt", choices=["json+srt", "json", "srt", "txt", "all"])
    p.add_argument("--word-timestamps", help="siempre por palabra; se acepta por compatibilidad")
    p.add_argument("--condition-on-previous-text", help="siempre False; se acepta por compatibilidad")
    p.add_argument("--descargar-modelo", action="store_true")
    a = p.parse_args(argv)
    if not a.entrada and not a.descargar_modelo:
        p.error("falta el audio o video a transcribir")
    return a


def _formatos(pedido):
    return {"json+srt": {"json", "srt"}, "all": {"json", "srt", "txt"}}.get(pedido, {pedido})


def main(argv=None, crear=crear_motor):
    a = _argumentos(sys.argv[1:] if argv is None else argv)
    motor = crear(normalizar_modelo(a.model))
    if a.descargar_modelo:
        motor.descargar()
        return
    resultado = motor.transcribir(a.entrada, prompt=a.initial_prompt)
    carpeta = a.output_dir or os.path.dirname(os.path.abspath(a.entrada))
    base = os.path.join(carpeta, os.path.splitext(os.path.basename(a.entrada))[0])
    formatos = _formatos(a.output_format)
    if "json" in formatos:
        escribir_json(resultado, base + ".json")
    if "srt" in formatos:
        _escribir_texto(a_srt(resultado), base + ".srt")
    if "txt" in formatos:
        _escribir_texto(resultado["text"].strip() + "\n", base + ".txt")


if __name__ == "__main__":
    try:
        main()
    except (TranscriptorNoInstalado, AudioIlegible) as e:
        sys.exit(f"ERROR: {e}")
