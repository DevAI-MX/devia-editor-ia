"""Pruebas del entorno comun de los scripts (bin/entorno.sh y bin/py)."""
import os
import shutil
import subprocess

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# En Windows, "bash" a secas abre el de WSL (System32 va antes que el PATH): se busca Git Bash.
BASH = shutil.which("bash") or "bash"


def bash(script):
    return subprocess.run([BASH, "-c", script], cwd=RAIZ, capture_output=True, check=True).stdout


def test_la_salida_de_python_capturada_por_bash_no_trae_retorno_de_carro():
    salida = bash('source bin/entorno.sh; N=$("$PY" -c "print(round(12.3456, 3))"); printf "[%s]" "$N"')
    assert salida == b"[12.346]"


def test_python_lee_y_escribe_acentos_sin_importar_el_idioma_del_sistema():
    salida = bash('source bin/entorno.sh; "$PY" -c "import sys; print(sys.flags.utf8_mode)"')
    assert salida.strip() == b"1"


def test_la_raiz_del_kit_es_una_ruta_que_python_puede_abrir():
    salida = bash('source bin/entorno.sh; "$PY" -c "import os,sys; print(os.path.isfile(sys.argv[1]))" '
                  '"$KIT_RAIZ/bin/cfg.py"; "$PY" -c "import os; print(os.path.isfile(\'$KIT_RAIZ/bin/cfg.py\'))"')
    assert salida.split() == [b"True", b"True"]


def test_bin_py_corre_scripts_del_kit():
    salida = bash("bash bin/py -c \"print('micrófono')\"")
    assert salida.decode("utf-8").strip() == "micrófono"


def test_la_salida_de_ffprobe_llega_sin_retorno_de_carro():
    salida = bash('source bin/entorno.sh; D=$(ffprobe -v error -show_entries format=duration -of csv=p=0 '
                  'tests/fixtures/prueba.mp4); printf "[%s]" "$D"')
    assert b"\r" not in salida and salida.startswith(b"[17.")


def test_el_path_de_bash_no_lleva_rutas_con_letra_de_unidad():
    # Bash separa PATH con ':': una entrada C:/... quedaria partida en "C" y "/...".
    primera = bash('source bin/entorno.sh; printf "%s" "$PATH" | tr ":" "\\n" | head -1').strip()
    assert primera.endswith((b".venv/bin", b".venv/Scripts"))


def test_las_rutas_temporales_van_entre_comillas_para_aguantar_espacios():
    # En Windows la carpeta del usuario suele llevar espacio (C:/Users/Maria Perez/...):
    # un > $KIT_TMP/x.log sin comillas da "ambiguous redirect" y aborta el render.
    sueltas = []
    for nombre in sorted(os.listdir(os.path.join(RAIZ, "bin"))):
        if not nombre.endswith(".sh") or nombre == "entorno.sh":
            continue
        with open(os.path.join(RAIZ, "bin", nombre), encoding="utf-8") as f:
            for n, linea in enumerate(f, 1):
                i = linea.find("$KIT_TMP")
                while i != -1:
                    if linea[i - 1] != '"':
                        sueltas.append(f"{nombre}:{n}")
                    i = linea.find("$KIT_TMP", i + 1)
    assert sueltas == []
