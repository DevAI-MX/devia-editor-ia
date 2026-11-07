#!/bin/bash
# setup.sh: deja el editor listo para editar. Se ejecuta una sola vez: bash setup.sh
# Mac (chip Apple o Intel), Windows (Git Bash; lo llama setup-windows.ps1) y Linux.
set -uo pipefail
cd "$(dirname "$0")"
K="$(pwd -W 2>/dev/null || pwd)"
ok(){ printf "  \033[32mOK\033[0m  %s\n" "$1"; }
no(){ printf "  \033[31m!!\033[0m  %s\n" "$1"; }
echo; echo "Editor de video con IA, de Devia Consulting: instalacion"; echo

case "$(uname -s)" in
  Darwin) SO=mac ;;
  MINGW*|MSYS*|CYGWIN*) SO=windows ;;
  *) SO=linux ;;
esac
CHIP_APPLE=0
[ "$SO" = mac ] && [ "$(uname -m)" = arm64 ] && CHIP_APPLE=1

# 1. Herramientas del sistema: ffmpeg, node 22+ (para npx) y uv (trae su propio Python)
source bin/requisitos.sh
FALTA="$(herramientas_que_faltan)"
if [ -n "$FALTA" ]; then
  case "$SO" in
    mac)
      command -v brew >/dev/null 2>&1 || { no "Falta Homebrew. Instalalo desde https://brew.sh y vuelve a ejecutar: bash setup.sh"; exit 1; }
      for pkg in ffmpeg uv; do
        command -v "$pkg" >/dev/null 2>&1 || { echo "  ..  instalando $pkg"; brew install "$pkg" >/dev/null 2>&1 || no "no se pudo instalar $pkg"; }
      done
      # brew install no actualiza un node viejo: por eso primero upgrade.
      node_al_dia || { echo "  ..  instalando node"; brew upgrade node >/dev/null 2>&1 || brew install node >/dev/null 2>&1 || no "no se pudo instalar node"; } ;;
    windows)
      no "Faltan:$FALTA. Ejecuta setup-windows.ps1 (instala todo con winget) y despues cierra y vuelve a abrir Claude Code."
      exit 1 ;;
    linux)
      # uv se instala sin sudo en ~/.local/bin; ffmpeg y node piden la contrasena del equipo.
      if ! command -v uv >/dev/null 2>&1; then
        echo "  ..  instalando uv"
        curl -LsSf https://astral.sh/uv/install.sh | sh >/dev/null 2>&1 || no "no se pudo instalar uv"
        export PATH="$HOME/.local/bin:$PATH"
      fi
      FALTA="$(herramientas_que_faltan)"
      if [ -n "$FALTA" ]; then
        no "Faltan:$FALTA. Pega esto en tu terminal (te pide tu contrasena) y vuelve a ejecutar: bash setup.sh"
        echo "      Ubuntu o Debian:"
        echo "      sudo apt-get install -y ffmpeg curl && curl -fsSL https://deb.nodesource.com/setup_${NODE_MINIMO}.x | sudo -E bash - && sudo apt-get install -y nodejs"
        echo "      Otra distribucion: instala ffmpeg y Node ${NODE_MINIMO} o mas nuevo con su gestor de paquetes."
        exit 1
      fi ;;
  esac
  FALTA="$(herramientas_que_faltan)"
  [ -z "$FALTA" ] || { no "siguen faltando:$FALTA"; exit 1; }
fi
ok "ffmpeg, node $(version_mayor_node) y uv"

# 2. Entorno de Python propio del kit. uv baja Python 3.12 si el equipo no lo tiene:
#    no depende del Python del sistema (en Windows, "python3" suele ser un atajo a la tienda).
if [ ! -d "$K/.venv" ]; then
  uv venv --quiet --python 3.12 "$K/.venv" || { no "no se pudo crear el entorno de Python"; exit 1; }
fi
if [ -f "$K/.venv/Scripts/python.exe" ]; then PY="$K/.venv/Scripts/python.exe"; else PY="$K/.venv/bin/python"; fi
pip_kit(){ uv pip install --quiet --python "$PY" "$@" >/dev/null 2>&1; }
pip_kit numpy pillow && ok "numpy y pillow" || { no "fallo numpy/pillow"; exit 1; }
if [ "$CHIP_APPLE" = 1 ]; then
  echo "  ..  instalando el transcriptor para chip Apple (mlx-whisper)"
  pip_kit mlx-whisper && ok "mlx-whisper" || { no "fallo mlx-whisper"; exit 1; }
else
  echo "  ..  instalando el transcriptor (faster-whisper, corre en el procesador)"
  # Version fija: es la que pasa las pruebas. Las nuevas cambian la API sin aviso.
  pip_kit "faster-whisper==1.2.1" && ok "faster-whisper" || { no "fallo faster-whisper"; exit 1; }
fi

# 3. Modelo de transcripcion: se baja ahora para que el primer video no se quede esperando
echo "  ..  descargando el modelo de transcripcion (unos 3 GB, solo la primera vez; depende de tu internet)"
bash "$K/bin/py" "$K/bin/transcriptor.py" --descargar-modelo >/dev/null 2>&1 \
  && ok "modelo de transcripcion" || no "no se pudo bajar el modelo; se bajara al editar el primer video"

# 4. Limpieza de voz (DeepFilterNet). Necesita Python 3.11: torch 2.0.1 no existe para 3.12.
echo "  ..  preparando la limpieza de voz"
uvx --python 3.11 --from deepfilternet --with "torch==2.0.1" --with "torchaudio==2.0.2" deepFilter --help >/dev/null 2>&1 \
  && ok "limpieza de voz" || no "la limpieza de voz no quedo lista; los videos saldran solo con EQ"

# 5. Motor de render
echo "  ..  preparando el motor de render"
npx -y hyperframes@0.7.110 --version >/dev/null 2>&1 && ok "motor de render" || no "el motor de render no respondio; se intentara al primer render"

# 6. Efectos de sonido: se generan aqui mismo, sin archivos de terceros
bash "$K/bin/gen-sfx.sh" "$K/assets/sfx" >/dev/null 2>&1 && ok "efectos de sonido ($(ls "$K/assets/sfx" | grep -c wav) generados)" || no "fallo la generacion de efectos"

# 7. Skill de Claude Code: es un archivo dentro de .claude/skills, no se instala nada
[ -f "$K/.claude/skills/editor-ia/SKILL.md" ] && ok "skill de Claude Code: /editor-ia" || no "no se encontro .claude/skills/editor-ia/SKILL.md"

mkdir -p "$K/input" "$K/output" "$K/salida" "$K/musica"
echo; echo "Listo. Abre Claude Code en esta carpeta y pidele que edite un video de input/."
echo "Si quieres una cancion tuya, ponla con licencia en la carpeta musica/."; echo
