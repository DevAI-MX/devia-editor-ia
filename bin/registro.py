#!/usr/bin/env python3
"""Registro de b-roll ya usado: impide que dos videos parezcan el mismo.

Repetir los mismos clips de un video a otro es lo que hace que la serie entera se
lea como una sola pieza repetida. La regla: de un video al siguiente puede repetirse
COMO MUCHO uno, y ninguno puede haber salido ya dos veces.

Uso:
  bin/registro.py apuntar <nombre> <beats.json>   guarda lo que usa este video
  bin/registro.py revisar <nombre> <beats.json>   avisa (y falla) si se repite
  bin/registro.py libres [carpeta]                lista lo que aun no se ha usado
"""
import json, os, sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REG = os.path.join(RAIZ, "input", "broll_usados.json")
# Un clip PUEDE repetirse, pero no de un video al siguiente: tiene que haber al menos
# dos videos de por medio. Y del video anterior no puede venir mas de una cuarta parte
# del b-roll — si se comparte mas, los dos videos se leen como el mismo.
DISTANCIA_MIN = 2
DIFERENTE_MIN = 0.75


def carga():
    return json.load(open(REG)) if os.path.exists(REG) else {"orden": [], "videos": {}}


def clips(beats_p):
    if not beats_p or not os.path.exists(beats_p):
        return []
    b = json.load(open(beats_p))
    return sorted({s["media"] for s in b.get("stingers", [])
                   if s.get("tipo") == "broll" and s.get("media")})


def main():
    if len(sys.argv) < 2:
        print(__doc__, file=sys.stderr); sys.exit(2)
    accion = sys.argv[1]
    r = carga()

    if accion == "libres":
        carpeta = sys.argv[2] if len(sys.argv) > 2 else os.path.join(RAIZ, "input", "broll")
        usados = {c for v in r["videos"].values() for c in v}
        todos = []
        for base, _, fs in os.walk(carpeta):
            for f in fs:
                if f.lower().endswith((".mp4", ".mov")):
                    todos.append(os.path.relpath(os.path.join(base, f), carpeta))
        libres = sorted(set(todos) - usados)
        print(f"{len(libres)} clips sin usar de {len(todos)}:")
        for c in libres:
            print(" ", c)
        return

    nombre, beats_p = sys.argv[2], sys.argv[3]
    usa = clips(beats_p)

    if accion == "apuntar":
        r["videos"][nombre] = usa
        if nombre in r["orden"]:
            r["orden"].remove(nombre)
        r["orden"].append(nombre)
        os.makedirs(os.path.dirname(REG), exist_ok=True)
        json.dump(r, open(REG, "w"), ensure_ascii=False, indent=1)
        print(f"  registro: {nombre} usa {len(usa)} clips")
        return

    if accion == "revisar":
        if not usa:
            return

        # El b-roll tiene que ser del TEMA del formato. Un plano de ambiente no dice
        # nada del guion y rompe el hilo: paso con un cuarto desordenado y una puerta
        # en un video sobre como acercarse a una mujer.
        try:
            sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
            from cfg import cfg
            carpeta = cfg("broll.carpeta", "")
        except Exception:
            carpeta = ""
        # la reserva puede ser MAS DE UNA carpeta (Fresco tiene su material en fresco/ y dubai/)
        carpetas = cfg("broll.carpetas", None) or ([carpeta] if carpeta else [])
        if carpetas:
            reservas = [os.path.basename(str(c).rstrip("/")) for c in carpetas]
            # la carpeta base del kit (input/broll) es reserva en si misma: un clip suelto
            # ahi dentro ("clip.mp4", sin subcarpeta) sale de ella
            en_raiz = any(str(c).rstrip("/").endswith("input/broll") for c in carpetas)
            fuera = [c for c in usa if not any(c.startswith(r + "/") for r in reservas)
                     and not (en_raiz and "/" not in c)]
            carpeta = ", ".join(str(c) for c in carpetas)
            if fuera:
                print(f"ERROR: este formato pide b-roll de {cfg('broll.tema', [])}.",
                      file=sys.stderr)
                print("  estos clips no salen de la reserva del tema (" + carpeta + "):",
                      file=sys.stderr)
                for c in fuera:
                    print("   ", c, file=sys.stderr)
                sys.exit(1)
        previos = [v for v in r["orden"] if v != nombre]
        anterior = previos[-1] if previos else None

        # a cuantos videos de distancia salio cada clip por ultima vez
        distancia = {}
        for i, v in enumerate(reversed(previos), start=1):
            for c in r["videos"].get(v, []):
                distancia.setdefault(c, i)

        repes_ant = [c for c in usa if anterior and c in r["videos"].get(anterior, [])]
        cercanos = [c for c in usa if distancia.get(c, 99) < DISTANCIA_MIN]
        distinto = 1 - (len(repes_ant) / max(len(usa), 1))

        problemas = []
        if cercanos:
            problemas.append(
                f"estos clips salieron hace menos de {DISTANCIA_MIN} videos: "
                + ", ".join(f"{c} (hace {distancia[c]})" for c in cercanos))
        if distinto < DIFERENTE_MIN:
            problemas.append(
                f"solo el {distinto:.0%} del b-roll cambia respecto a '{anterior}'; "
                f"tiene que cambiar al menos el {DIFERENTE_MIN:.0%}")

        if problemas:
            print("ERROR: el b-roll se repite y los videos van a parecer el mismo:",
                  file=sys.stderr)
            for p in problemas:
                print("  " + p, file=sys.stderr)
            print("  mira que queda libre con: bin/registro.py libres", file=sys.stderr)
            sys.exit(1)
        print(f"  b-roll: {len(usa)} clips, {distinto:.0%} distinto del video anterior")


main()
