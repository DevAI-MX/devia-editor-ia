# entorno.sh: el mismo entorno para todos los scripts del kit, en Mac, Linux y Windows (Git Bash).
# Se carga al principio de cada script con:  source "$(dirname "$0")/entorno.sh"
# Deja listos KIT_RAIZ (la carpeta del kit), PY (el Python del kit) y KIT_TMP (archivos de paso).

# En Git Bash, pwd da /c/Users/...; Python y ffmpeg de Windows no entienden esa forma
# cuando va dentro de un texto (open('/c/...')). pwd -W da C:/Users/..., que entienden todos.
ruta_absoluta() {
  (cd "$1" && { pwd -W 2>/dev/null || pwd; })
}

KIT_RAIZ="$(ruta_absoluta "$(dirname "${BASH_SOURCE[0]}")/..")"
if [ -f "$KIT_RAIZ/.venv/Scripts/python.exe" ]; then
  KIT_VENV_BIN="$KIT_RAIZ/.venv/Scripts"
  PY="$KIT_VENV_BIN/python.exe"
  # En Windows, print() escribe \r\n y $(...) se queda con el \r: los numeros llegan
  # rotos a ffmpeg. sitecustomize.py vuelve la salida de Python a \n.
  export PYTHONPATH="$KIT_RAIZ/bin/python_windows${PYTHONPATH:+;$PYTHONPATH}"
else
  KIT_VENV_BIN="$KIT_RAIZ/.venv/bin"
  PY="$KIT_VENV_BIN/python"
fi
# exit y no return: si falta el entorno, el script que cargo este archivo tiene que detenerse.
[ -f "$PY" ] || { echo "ERROR: el editor no esta instalado. Ejecuta 'bash setup.sh' en la carpeta del editor." >&2; exit 1; }
# PATH se separa con ':', asi que la entrada va en la forma de Bash (/c/...), no C:/...
if command -v cygpath >/dev/null 2>&1; then
  export PATH="$(cygpath -u "$KIT_VENV_BIN"):$PATH"
else
  export PATH="$KIT_VENV_BIN:$PATH"
fi
# ffprobe.exe termina sus lineas en \r\n y $(...) se queda con el \r. Se quita aqui, para
# todos los scripts, y en Mac y Linux no cambia nada.
ffprobe() { command ffprobe "$@" | tr -d '\r'; }
# Transcripts, guiones y estilos van en UTF-8. Sin esto, Python en Windows lee con la
# codificacion del sistema y rompe los acentos.
export PYTHONUTF8=1
KIT_TMP="$KIT_RAIZ/output/.tmp"
mkdir -p "$KIT_TMP"
