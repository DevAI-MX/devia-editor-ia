"""Pruebas del transcriptor: elige el motor segun el equipo y entrega siempre el mismo JSON."""
import json
import os
import subprocess
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "bin"))
import transcriptor  # noqa: E402


def palabra(texto, inicio, fin):
    return SimpleNamespace(word=texto, start=inicio, end=fin, probability=0.9)


def segmento(id_, inicio, fin, texto, palabras):
    return SimpleNamespace(id=id_, seek=0, start=inicio, end=fin, text=texto, tokens=[1, 2],
                           temperature=0.0, avg_logprob=-0.2, compression_ratio=1.1,
                           no_speech_prob=0.01, words=palabras)


SEGMENTOS = [
    segmento(0, 0.0, 1.2, " Hola, hoy grabamos.", [palabra(" Hola,", 0.0, 0.3),
                                                    palabra(" hoy", 0.35, 0.6),
                                                    palabra(" grabamos.", 0.62, 1.2)]),
    segmento(1, 1.5, 2.5, " Ponte frente a la ventana.", [palabra(" Ponte", 1.5, 1.8),
                                                           palabra(" ventana.", 2.0, 2.5)]),
]


class TestEleccionDelMotor:
    def test_mac_con_chip_apple_usa_mlx(self):
        assert transcriptor.es_chip_apple("Darwin", "arm64")

    @pytest.mark.parametrize("sistema,maquina", [("Windows", "AMD64"), ("Linux", "x86_64"),
                                                 ("Darwin", "x86_64")])
    def test_cualquier_otro_equipo_usa_faster_whisper(self, sistema, maquina):
        assert not transcriptor.es_chip_apple(sistema, maquina)

    def test_sin_el_paquete_instalado_explica_como_instalarlo(self, monkeypatch):
        monkeypatch.setitem(sys.modules, "faster_whisper", None)
        with pytest.raises(transcriptor.TranscriptorNoInstalado, match="setup"):
            transcriptor.crear_motor(chip_apple=False)


class TestNombresDeModelo:
    @pytest.mark.parametrize("pedido,esperado", [
        ("large-v3", "large-v3"),
        ("mlx-community/whisper-large-v3-mlx", "large-v3"),
        ("mlx-community/whisper-large-v3-turbo", "large-v3-turbo"),
        ("small", "small"),
    ])
    def test_acepta_el_nombre_corto_y_el_del_repositorio_mlx(self, pedido, esperado):
        assert transcriptor.normalizar_modelo(pedido) == esperado

    def test_el_repositorio_mlx_de_large_v3_es_el_que_ya_usaba_el_kit(self):
        assert transcriptor.repositorio_mlx("large-v3") == "mlx-community/whisper-large-v3-mlx"

    def test_el_repositorio_mlx_de_turbo_no_lleva_sufijo(self):
        assert transcriptor.repositorio_mlx("large-v3-turbo") == "mlx-community/whisper-large-v3-turbo"


class TestFormatoComun:
    def test_faster_whisper_sale_con_la_forma_del_json_de_mlx(self):
        r = transcriptor.a_formato_whisper(SEGMENTOS, "es")
        assert set(r) == {"text", "segments", "language"}
        assert r["language"] == "es"
        assert r["text"] == " Hola, hoy grabamos. Ponte frente a la ventana."
        primero = r["segments"][0]
        assert {"id", "start", "end", "text", "words"} <= set(primero)
        assert primero["words"][0] == {"word": " Hola,", "start": 0.0, "end": 0.3, "probability": 0.9}

    def test_el_json_se_puede_escribir_sin_perder_acentos(self, tmp_path):
        r = transcriptor.a_formato_whisper([segmento(0, 0.0, 1.0, " micrófono", [palabra(" micrófono", 0, 1)])],
                                           "es")
        ruta = tmp_path / "t.json"
        transcriptor.escribir_json(r, ruta)
        assert json.loads(ruta.read_text(encoding="utf-8"))["text"] == " micrófono"


class TestSrt:
    def test_numera_los_bloques_y_formatea_los_tiempos(self):
        srt = transcriptor.a_srt(transcriptor.a_formato_whisper(SEGMENTOS, "es"))
        assert srt.split("\n")[:4] == ["1", "00:00:00,000 --> 00:00:01,200", "Hola, hoy grabamos.", ""]
        assert "2\n00:00:01,500 --> 00:00:02,500\nPonte frente a la ventana.\n" in srt

    def test_pasada_la_hora_no_se_desborda(self):
        assert transcriptor.tiempo_srt(3723.4567) == "01:02:03,457"


class TestLineaDeComandos:
    def test_escribe_json_y_srt_con_el_nombre_del_archivo(self, tmp_path):
        motor = SimpleNamespace(transcribir=lambda ruta, prompt=None: transcriptor.a_formato_whisper(SEGMENTOS, "es"))
        entrada = tmp_path / "video_cut.mp4"
        entrada.write_bytes(b"")
        transcriptor.main([str(entrada), "--output-dir", str(tmp_path)], crear=lambda modelo: motor)
        assert json.loads((tmp_path / "video_cut.json").read_text(encoding="utf-8"))["segments"]
        assert (tmp_path / "video_cut.srt").read_text(encoding="utf-8").startswith("1\n")

    def test_acepta_los_argumentos_de_mlx_whisper_que_ya_usaba_el_kit(self, tmp_path):
        pedidos = []

        def crear(modelo):
            pedidos.append(modelo)
            return SimpleNamespace(transcribir=lambda ruta, prompt=None: (pedidos.append(prompt),
                                   transcriptor.a_formato_whisper(SEGMENTOS, "es"))[1])
        entrada = tmp_path / "a.wav"
        entrada.write_bytes(b"")
        transcriptor.main([str(entrada), "--model", "mlx-community/whisper-large-v3-mlx", "--language", "es",
                           "--word-timestamps", "True", "--condition-on-previous-text", "False",
                           "--initial-prompt", "enfermeria", "--output-format", "all",
                           "--output-dir", str(tmp_path)], crear=crear)
        assert pedidos == ["large-v3", "enfermeria"]
        assert (tmp_path / "a.txt").read_text(encoding="utf-8").strip() == "Hola, hoy grabamos. Ponte frente a la ventana."

    def test_solo_transcribe_en_espanol(self, tmp_path):
        with pytest.raises(SystemExit):
            transcriptor.main([str(tmp_path / "a.wav"), "--language", "en"], crear=lambda m: None)


class TestLecturaDelAudio:
    """El audio lo decodifica ffmpeg y no PyAV: PyAV 19 rompio la llamada de faster-whisper 1.2.1."""
    FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "prueba.mp4")

    def test_entrega_16_mil_muestras_por_segundo_en_mono(self):
        audio = transcriptor.leer_audio(self.FIXTURE)
        dur_audio = float(subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a:0", "-show_entries",
                                          "stream=duration", "-of", "csv=p=0", self.FIXTURE],
                                         capture_output=True, text=True, check=True).stdout)
        assert audio.dtype.name == "float32"
        assert abs(len(audio) / transcriptor.MUESTREO - dur_audio) < 0.05
        assert 0 < abs(audio).max() <= 1.0

    def test_si_ffmpeg_no_puede_leerlo_dice_que_archivo_era(self, tmp_path):
        roto = tmp_path / "roto.mp4"
        roto.write_bytes(b"no es un video")
        with pytest.raises(transcriptor.AudioIlegible, match="roto.mp4"):
            transcriptor.leer_audio(roto)
