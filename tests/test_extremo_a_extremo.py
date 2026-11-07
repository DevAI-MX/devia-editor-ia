"""Edita el video de prueba de principio a fin, como lo pide editor-ia, y revisa la entrega.

El video (tests/fixtures/prueba.mp4) es una voz sintetizada en espanol con pausas largas
entre frases, para que el corte de silencios tenga trabajo.
"""
import json
import os
import shutil
import subprocess

import pytest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# En Windows, "bash" a secas abre el de WSL (System32 va antes que el PATH): se busca Git Bash.
BASH = shutil.which("bash") or "bash"
NOMBRE = "_prueba_e2e"
PALABRAS_DICHAS = {"trucos", "ventana", "micrófono", "vertical"}


def bash(comando, **entorno):
    r = subprocess.run([BASH, "-c", comando], cwd=RAIZ, capture_output=True, text=True,
                       encoding="utf-8", env={**os.environ, **entorno})
    assert r.returncode == 0, f"fallo: {comando}\n{r.stdout[-3000:]}\n{r.stderr[-3000:]}"
    return r.stdout


def ffprobe(ruta, campo):
    return subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", campo,
                           "-of", "csv=p=0", ruta], capture_output=True, text=True, check=True).stdout.strip()


@pytest.fixture(scope="module")
def edicion():
    entrada = os.path.join(RAIZ, "input", f"{NOMBRE}.mp4")
    shutil.copy(os.path.join(RAIZ, "tests", "fixtures", "prueba.mp4"), entrada)
    bash(f"bash bin/cortar.sh input/{NOMBRE}.mp4")
    bash(f"bash bin/py bin/cues.py input/{NOMBRE}.json > output/{NOMBRE}_cues.json")
    bash(f"echo '{{}}' > output/{NOMBRE}_beats.json && echo '[]' > output/{NOMBRE}_keywords.json")
    montaje = bash(f"bash bin/montar.sh input/{NOMBRE}_cut.mp4 output/{NOMBRE}_cues.json {NOMBRE} "
                   f"output/{NOMBRE}_beats.json output/{NOMBRE}_keywords.json input/{NOMBRE}.json",
                   FORMATO="limpio", SIN_REGISTRO="1")
    entrega = bash(f"bash bin/entregar.sh {NOMBRE} input/{NOMBRE}.json salida/{NOMBRE}.mp4", FORMATO="limpio")
    yield {"montaje": montaje, "entrega": entrega}
    for ruta in (f"input/{NOMBRE}*", f"output/{NOMBRE}*", f"salida/{NOMBRE}.mp4"):
        bash(f"rm -rf {ruta}")


@pytest.mark.lento
def test_el_transcript_tiene_lo_que_se_dice_palabra_por_palabra(edicion):
    with open(os.path.join(RAIZ, "input", f"{NOMBRE}.json"), encoding="utf-8") as f:
        t = json.load(f)
    palabras = {w["word"].strip(" ,.").lower() for s in t["segments"] for w in s["words"]}
    assert PALABRAS_DICHAS <= palabras
    assert all(w["end"] >= w["start"] for s in t["segments"] for w in s["words"])


@pytest.mark.lento
def test_el_corte_quita_las_pausas_largas(edicion):
    with open(os.path.join(RAIZ, "input", f"{NOMBRE}_cortes.json"), encoding="utf-8") as f:
        cortes = json.load(f)
    assert cortes["src_duration"] - cortes["out_duration"] > 1.5


@pytest.mark.lento
def test_los_tres_controles_de_subtitulos_salen_limpios(edicion):
    assert "PALABRAS QUE SE DICEN Y NO SE VEN: 0 de" in edicion["montaje"]
    assert "REVISION OK" in edicion["entrega"]


@pytest.mark.lento
def test_la_entrega_es_un_vertical_h264_para_reels(edicion):
    final = os.path.join(RAIZ, "salida", f"{NOMBRE}.mp4")
    assert ffprobe(final, "stream=codec_name") == "h264"
    assert ffprobe(final, "stream=width,height") == "1080,1920"
