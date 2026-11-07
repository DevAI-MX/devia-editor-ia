#!/usr/bin/env python3
"""Lee un valor de la configuracion desde bash.  Uso: bin/leer.py ruta.al.valor [defecto]"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cfg import cfg
print(cfg(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else ""))
