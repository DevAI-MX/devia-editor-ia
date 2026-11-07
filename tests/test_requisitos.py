"""Pruebas de bin/requisitos.sh: que herramientas del sistema faltan antes de instalar."""
import os
import shutil
import subprocess

import pytest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASH = shutil.which("bash") or "bash"


def con_node(definicion, orden):
    """Corre una orden de requisitos.sh con un node de mentira, definido como funcion de bash."""
    script = f"{definicion}\nsource bin/requisitos.sh\n{orden}"
    return subprocess.run([BASH, "-c", script], cwd=RAIZ, capture_output=True, text=True)


@pytest.mark.parametrize("version", ["v22.11.0", "v24.1.0", "v22.1.0\\r"])
def test_node_22_o_mas_nuevo_esta_al_dia(version):
    assert con_node(f"node() {{ printf '{version}\\n'; }}", "node_al_dia").returncode == 0


@pytest.mark.parametrize("definicion", ["node() { printf 'v20.18.0\\n'; }",
                                        "node() { return 127; }",
                                        "node() { printf 'basura\\n'; }"])
def test_node_viejo_ausente_o_ilegible_no_esta_al_dia(definicion):
    assert con_node(definicion, "node_al_dia").returncode != 0


def test_un_node_viejo_cuenta_como_herramienta_que_falta():
    r = con_node("node() { printf 'v20.18.0\\n'; }", "herramientas_que_faltan")
    assert "node22" in r.stdout.split()


def test_con_todo_instalado_no_falta_nada():
    r = con_node("node() { printf 'v22.11.0\\n'; }", "herramientas_que_faltan")
    assert r.stdout.strip() == ""
