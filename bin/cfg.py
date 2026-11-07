#!/usr/bin/env python3
"""Lector de la configuracion del formato, compartido por todos los scripts.

La configuracion tiene que MANDAR de verdad: si un valor esta en el json pero el
script lo lleva escrito a mano, cambiar el json no hace nada y la configuracion
engana. Todos los scripts leen de aqui.

  from cfg import cfg
  cfg("cortes.silencio_db", -32)
"""
import json, os

_RUTA = os.environ.get("ESTILO") or os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "formatos", os.environ.get("FORMATO", "dinamico") + ".json")

try:
    _C = json.load(open(_RUTA))
except Exception:
    _C = {}


def cfg(ruta, defecto=None):
    """cfg("bloque.cuerpo_max", 168) -> valor del json o el defecto."""
    n = _C
    for k in ruta.split("."):
        if not isinstance(n, dict) or k not in n:
            return defecto
        n = n[k]
    return n
