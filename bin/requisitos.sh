# requisitos.sh: que herramientas del sistema le faltan al editor. Lo carga setup.sh.
# hyperframes 0.7.110 (el motor de render) declara node >= 22 en su campo engines.
NODE_MINIMO=22

version_mayor_node() { node -v 2>/dev/null | tr -d 'v\r' | cut -d. -f1; }

node_al_dia() {
  local mayor
  mayor="$(version_mayor_node)"
  [ -n "$mayor" ] && [ "$mayor" -ge "$NODE_MINIMO" ] 2>/dev/null
}

# Imprime lo que falta separado por espacios; nada si esta todo.
herramientas_que_faltan() {
  local falta=""
  for b in ffmpeg ffprobe uv uvx; do command -v "$b" >/dev/null 2>&1 || falta="$falta $b"; done
  { node_al_dia && command -v npx >/dev/null 2>&1; } || falta="$falta node$NODE_MINIMO"
  echo "$falta"
}
