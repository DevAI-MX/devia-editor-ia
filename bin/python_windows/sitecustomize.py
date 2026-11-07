"""Solo se carga en Windows (bin/entorno.sh). La salida de Python termina las lineas en \\n,
como en Mac: Bash conserva el \\r de \\r\\n al capturar la salida con $(...)."""
import sys

for flujo in (sys.stdout, sys.stderr):
    if hasattr(flujo, "reconfigure"):
        flujo.reconfigure(newline="\n")
