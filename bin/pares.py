#!/usr/bin/env python3
"""Subtitulos en DOS LINEAS para el formato impacto.

En las referencias no hay bloque de tres registros ni serifa: TODO el texto son
dos lineas de la misma sans — la entradilla pequena arriba y las palabras clave
grandes debajo — y las dos se van juntas. Las palabras de la linea grande entran
una a una, al ritmo del habla.

Este script arma esas parejas directamente del transcript, que es lo unico que
tiene tiempo por palabra. Por construccion no puede perder ni inventar texto:
recorre las palabras en orden y solo decide donde cortar de linea. Al final lo
comprueba comparando la secuencia de palabras de salida con la de entrada, y si
no cuadra falla en vez de entregar un video con texto de menos.

Uso: bin/pares.py transcript.json [keys.json] [clave.json] > pares.json
"""
import json, os, re, sys, unicodedata

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cfg import cfg

PAL_MAX = cfg("subtitulo.palabras_max", 4)
CAR_MAX = cfg("subtitulo.caracteres_max", 24)
PAUSA = cfg("subtitulo.pausa_corte", 0.35)
CUE_MIN = cfg("subtitulo.cue_min", 0.38)
HOLD_MAX = cfg("subtitulo.hold_max", 1.10)
SOLA_MAX = cfg("subtitulo.hueco_pareja", 1.00)
ENTRA = cfg("subtitulo.entrada", 0.18)     # lo que tarda una palabra en aparecer
SALE = cfg("subtitulo.salida", 0.12)       # lo que tarda la pareja en irse
ENFASIS_CFG = [w.lower() for w in cfg("subtitulo.enfasis", [])]

# Las palabras de enlace no pueden cerrar una linea: "y es el de / las preguntas"
# funciona porque el corte cae donde caeria al hablar. Si cierra en preposicion,
# la linea de arriba se lee coja.
ENLACE = set("""a ante bajo con contra de desde durante en entre hacia hasta mediante para por
segun sin sobre tras y e o u ni que pero sino porque aunque si cuando mientras como donde pues
el la los las un una unos unas lo al del mi tu su mis tus sus este esta ese esa esos esas estos
estas no ya se te me le les nos mas menos muy tan es son era eran""".split())


def norm(t):
    t = unicodedata.normalize("NFD", t.lower())
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    return "".join(c for c in t if c.isalnum())


def enlace(t):
    return norm(t) in ENLACE


def palabras_de(data):
    out = []
    for seg in data.get("segments", []):
        for w in seg.get("words", []):
            t = w.get("word", "").strip()
            if t:
                out.append({"t": t, "s": float(w["start"]), "e": float(w["end"])})
    # UN SIGNO SUELTO NO ES UNA PALABRA. Whisper parte "99 %" en dos tokens y acababan
    # en renglones distintos: en pantalla se leia "que el 99" y el "%" llegaba despues.
    PEGADOS = {"%", "º", "ª", "€", "$", "¢"}
    junto = []
    for w in out:
        if w["t"] in PEGADOS and junto:
            junto[-1] = {**junto[-1], "t": junto[-1]["t"] + w["t"], "e": w["e"]}
        else:
            junto.append(w)
    return junto


def cortar(ws, forzados=()):
    """Parte el habla en lineas cortas por donde se corta al hablar.

    `forzados` son indices de palabra que TIENEN que empezar linea. Se usa con la
    palabra del CTA: en las referencias va sola y en grande debajo de "comenta",
    nunca metida en mitad de una frase.
    """
    forzados = set(forzados)
    lineas, act = [], []
    for i, w in enumerate(ws):
        if act and i in forzados:
            lineas.append(act)
            act = []
        elif act:
            prev = act[-1]
            fuerte = re.search(r"[.!?…]$", prev["t"])
            suave = re.search(r"[,;:]$", prev["t"])
            hueco = w["s"] - prev["e"]
            largo = sum(len(x["t"]) + 1 for x in act) + len(w["t"])
            if (fuerte or hueco > PAUSA or len(act) >= PAL_MAX
                    or (largo > CAR_MAX and not enlace(prev["t"]))
                    or (suave and len(act) >= 2)):
                # nunca se cierra en palabra de enlace: se arrastra a la siguiente
                arrastre = []
                while (len(act) > 1 and enlace(act[-1]["t"])
                       and not re.search(r"[.!?,;:…]$", act[-1]["t"])):
                    arrastre.insert(0, act.pop())
                lineas.append(act)
                act = arrastre
        act.append(w)
    if act:
        lineas.append(act)

    # Toda linea tiene que decir algo. "es que" o "a la" sueltos en pantalla no
    # dicen nada: si una linea no lleva ni una palabra con contenido, se funde con
    # la siguiente (o con la anterior si es la ultima).
    n = 0
    while n < len(lineas):
        L = lineas[n]
        vacia = all(enlace(w["t"]) for w in L) and not re.search(r"[.!?…]$", L[-1]["t"])
        if vacia and n + 1 < len(lineas) and len(L) + len(lineas[n + 1]) <= PAL_MAX + 1:
            lineas[n + 1] = L + lineas[n + 1]
            lineas.pop(n)
            continue
        if vacia and n > 0 and len(L) + len(lineas[n - 1]) <= PAL_MAX + 1:
            lineas[n - 1] = lineas[n - 1] + L
            lineas.pop(n)
            continue
        n += 1
    return lineas


def texto(linea):
    return " ".join(w["t"] for w in linea).strip()


# El acento de color es AMARILLO, uno solo para todo: la palabra de enfasis y la del
# CTA. Antes eran dos (rojo para el enfasis, ambar para el CTA) copiando las
# referencias, pero el rojo se apagaba contra la camisa negra y el fondo oscuro.
ACENTO_CADA = cfg("subtitulo.acento_cada", cfg("subtitulo.rojo_cada", 12.0))
# Los primeros segundos son el GANCHO: ahi el acento no se raciona y cada palabra
# entra con su propio click. Es donde se juega la retencion entera del video.
GANCHO_DUR = float(cfg("gancho.dur", 3.0))
GANCHO_ACENTOS = int(cfg("gancho.acentos", 3))


def acentos(keys):
    """Las palabras que pueden llevar ACENTO, en dos grupos.

    ELEGIDAS A MANO: si la keyword trae un `bloque`, la fila marcada como "grande"
    dice exactamente que palabra pesa — es una decision tomada al montar el video, no
    una suposicion — y lleva acento si o si. Lo mismo con las que se declaren en
    `subtitulo.enfasis` del formato.

    DEDUCIDAS: del resto de frases se saca la palabra con mas cuerpo, y esas ya
    compiten entre ellas por el hueco.
    """
    mano, deducidas = set(), set()
    for k in keys or []:
        filas = k.get("bloque")
        if filas:
            for texto, rol in filas:
                if rol == "grande":
                    for t in texto.split():
                        if not enlace(t):
                            mano.add(norm(t))
            continue
        trozos = [t for t in k.get("text", "").split() if t]
        cand = [t for t in trozos if not enlace(t)] or trozos
        if cand:
            deducidas.add(norm(max(cand, key=lambda t: len(norm(t)))))
    for w in ENFASIS_CFG:
        mano.add(norm(w))
    mano.discard("")
    deducidas -= mano
    deducidas.discard("")
    return mano, deducidas


def elegir_acento(ws, mano, deducidas):
    """Que palabras llevan ACENTO de color, decidido sobre el habla y no sobre las lineas.

    El acento se gasta si se usa mucho: en las referencias sale dos o tres veces por
    minuto y siempre en la palabra que duele. Se deja como mucho una cada
    `acento_cada` segundos y en cada tramo gana la de mas peso — la mas larga — no la
    primera que caiga. Y se decide aqui, antes de cortar, porque la palabra elegida
    tiene que ir SOLA en su renglon y caer en la linea grande: en la entradilla el
    enfasis no se ve.
    """
    puestas, elegidas = [], set()
    for i, w in enumerate(ws):                       # las de mano no compiten
        if norm(w["t"]) in mano:
            elegidas.add(i)
            puestas.append(w["s"])
    cand = [(i, w) for i, w in enumerate(ws) if norm(w["t"]) in deducidas]

    # EL GANCHO NO RACIONA Y NO ESPERA A LAS KEYWORDS. Fuera del gancho el acento se
    # gasta si se usa mucho y solo compiten las palabras que salen de una keyword.
    # En los primeros segundos eso deja el gancho SIN un solo acento (medido: 0 en
    # comenta3), justo donde se decide si el video se ve entero. Asi que aqui el
    # acento se elige por peso propio: las `gancho.acentos` palabras mas largas que
    # no sean enlace. Regla del usuario: "la mayor capacidad de retencion debe estar
    # en el gancho, acentua las palabras clave de los primeros 3 segundos".
    for i, w in cand:
        if w["s"] < GANCHO_DUR:
            elegidas.add(i)
    en_gancho = [(i, w) for i, w in enumerate(ws)
                 if w["s"] < GANCHO_DUR and not enlace(w["t"]) and len(norm(w["t"])) >= 4]
    en_gancho.sort(key=lambda c: (-len(norm(c[1]["t"])), c[1]["s"]))
    for i, w in en_gancho[:GANCHO_ACENTOS]:
        elegidas.add(i)
    for i, w in sorted(cand, key=lambda c: (-len(norm(c[1]["t"])), c[1]["s"])):
        if w["s"] < GANCHO_DUR:
            continue                                  # ya resuelto arriba
        if any(abs(w["s"] - u) < ACENTO_CADA for u in puestas if u >= GANCHO_DUR):
            continue
        elegidas.add(i)
        puestas.append(w["s"])
    return elegidas


def linea_de(lineas, i_palabra):
    vistas = 0
    for n, L in enumerate(lineas):
        if vistas <= i_palabra < vistas + len(L):
            return n
        vistas += len(L)
    return None


def main():
    data = json.load(open(sys.argv[1]))
    arg = lambda n: sys.argv[n] if len(sys.argv) > n and sys.argv[n] and os.path.exists(sys.argv[n]) else None
    keys = json.load(open(arg(2))) if arg(2) else []
    clave = json.load(open(arg(3))) if arg(3) else None

    ws = palabras_de(data)
    for i, w in enumerate(ws):
        w["__i"] = i
    if not ws:
        print("[]")
        return

    # La palabra del CTA se aisla en su propia linea para que caiga en la grande de
    # abajo, en ambar, con "comenta" de entradilla encima.
    forzados, i_cta = [], None
    if clave and clave.get("palabra"):
        n_cta = norm(clave["palabra"])
        for i, w in enumerate(ws):
            if norm(w["t"]) == n_cta and w["s"] >= clave.get("desde", 0) - 0.5:
                forzados += [i, i + 1]
                i_cta = i
                break

    # las palabras con acento tambien se aislan: solas en su renglon y abajo,
    # que es como salen en las referencias
    acentos_elegidos = elegir_acento(ws, *acentos(keys))
    for i in sorted(acentos_elegidos):
        forzados += [i, i + 1]

    for i in acentos_elegidos:
        ws[i]["__acento"] = True

    lineas = cortar(ws, forzados)
    cta = norm(clave["palabra"]) if clave and clave.get("palabra") else None

    # Emparejado: la primera linea entra pequena arriba, la segunda grande debajo.
    # Si entre las dos hay un silencio largo no son la misma idea, y cada una va
    # sola en grande. La linea del CTA se recoloca obligando a la anterior a abrir
    # pareja, para que "comenta" quede de entradilla y la palabra clave debajo.
    i_linea = linea_de(lineas, i_cta) if i_cta is not None else None
    abre = {i_linea - 1} if i_linea else set()
    for i in acentos_elegidos:
        n = linea_de(lineas, i)
        if n:
            abre.add(n - 1)

    # No todo va emparejado. Una linea SOLA en grande pesa mucho mas que la misma
    # linea con una entradilla encima, asi que se reserva para los dos sitios donde
    # hace falta ese peso:
    #   - la linea que lleva la palabra con acento (en las referencias la palabra
    #     fuerte sale sola en pantalla, no colgando de otra);
    #   - la que abre frase, justo despues de un punto.
    # Y de paso el ritmo deja de ser el mismo compas una y otra vez.
    def sola(n):
        # La del CTA y su entradilla quedan fuera de esta regla: esa pareja esta
        # decidida antes ("comenta" arriba, la palabra clave abajo y en amarillo). Sin
        # esta excepcion, un punto justo delante rompia la paridad y la palabra clave
        # acababa de entradilla — pequena y arriba, que es justo donde no se ve.
        if i_linea is not None and n in (i_linea, i_linea - 1):
            return False
        L = lineas[n]
        if any(w.get("__acento") for w in L):
            return True
        if n == 0:
            return False
        return bool(re.search(r"[.!?…]$", lineas[n - 1][-1]["t"]))

    pares, i = [], 0
    while i < len(lineas):
        a = lineas[i]
        b = lineas[i + 1] if i + 1 < len(lineas) else None
        if sola(i) or (i + 1) in abre or not b or b[0]["s"] - a[-1]["e"] > SOLA_MAX:
            pares.append((None, a))
            i += 1
        elif sola(i + 1):
            # la de abajo tiene que ir sola: esta se queda sola tambien, no de
            # entradilla huerfana
            pares.append((None, a))
            i += 1
        else:
            pares.append((a, b))
            i += 2

    out = []
    for n, (lead, clv) in enumerate(pares):
        prox = None
        if n + 1 < len(pares):
            sig = pares[n + 1]
            prox = (sig[0] or sig[1])[0]["s"]
        # La pareja se apaga ANTES de que arranque la siguiente: si se pisan, se
        # leen dos textos encima en el mismo sitio y no se entiende ninguno.
        ini = (lead or clv)[0]["s"]
        fin = clv[-1]["e"] + HOLD_MAX
        if fin - ini < CUE_MIN:
            fin = ini + CUE_MIN
        fin = max(fin, clv[-1]["e"] + 0.06)
        if prox is not None:
            fin = min(fin, prox - 0.02)
        # Las palabras tienen que acabar de ENTRAR antes de que la pareja empiece a
        # irse: si la ultima entra pasado ese punto, su entrada y la salida animan la
        # misma opacidad, gana la que acaba mas tarde y la pareja se queda pegada en
        # pantalla — o se pisa con la siguiente. Se adelanta lo justo.
        tope = fin - (ENTRA + SALE + 0.02)
        ats = [w["s"] for w in clv]
        for j in range(len(ats) - 1, -1, -1):
            if ats[j] > tope:
                ats[j] = tope
                tope -= 0.04
        ats = [max(ini, a) for a in ats]

        out.append({
            "at": round(ini, 3),
            "fin": round(fin, 3),
            "lead": texto(lead) if lead else "",
            "clave": texto(clv),
            "palabras": [{
                "t": w["t"],
                "at": round(ats[j], 3),
                "acento": w.get("__acento", False),
                "ambar": bool(cta and norm(w["t"]) == cta and clave
                              and w["s"] >= clave.get("desde", 0) - 0.5),
            } for j, w in enumerate(clv)],
        })

    # LOS SUBTITULOS TERMINAN EN LA PALABRA CLAVE. Cuando dice "comenta X", ahi se
    # acaban: lo que viene despues solo se oye. Es una decision del formato, no un
    # descuido, asi que las parejas posteriores se marcan y el auditor las respeta.
    fin_cta = None
    for par in out:
        if any(w.get("ambar") for w in par["palabras"]):
            fin_cta = par["fin"]
            break
    if fin_cta is not None:
        for par in out:
            if par["at"] >= fin_cta:
                par["tras_cta"] = True

    # --- comprobacion: ni una palabra perdida ni una inventada ----------------
    dentro = [norm(w["t"]) for w in ws if norm(w["t"])]
    fuera = [norm(t) for p in out for t in (p["lead"] + " " + p["clave"]).split() if norm(t)]
    if dentro != fuera:
        d = next((i for i, (x, y) in enumerate(zip(dentro, fuera)) if x != y),
                 min(len(dentro), len(fuera)))
        sys.stderr.write("pares.py: el texto de salida no coincide con el transcript "
                         f"(entran {len(dentro)}, salen {len(fuera)}; primera diferencia "
                         f"en {d}: {dentro[d:d+4]} vs {fuera[d:d+4]})\n")
        sys.exit(1)

    # Ya comprobado que no falta nada, se recorta la pareja del CTA en la propia
    # palabra clave: en pantalla queda "comenta CLASE" y nada mas. Se hace al final,
    # despues de verificar, para que la comprobacion siga mirando el guion entero.
    # Lo que sobra tras la palabra clave NO se tira: pasa a una pareja propia marcada
    # tras_cta (no se dibuja, y el auditor la exime). Tirarlo sin marcar hacia que la
    # auditoria reclamara esas palabras como perdidas ("Comenta divierte y te...", 15-sep).
    for idx, par in enumerate(out):
        ks = [i for i, w in enumerate(par["palabras"]) if w.get("ambar")]
        if ks:
            k = ks[-1]
            if k + 1 < len(par["palabras"]):
                sobra = par["palabras"][k + 1:]
                par["palabras"] = par["palabras"][:k + 1]
                par["clave"] = " ".join(w["t"] for w in par["palabras"])
                out.insert(idx + 1, {"at": sobra[0]["at"], "fin": par["fin"], "lead": "",
                                     "clave": " ".join(w["t"] for w in sobra),
                                     "palabras": sobra, "tras_cta": True})
            break

    json.dump(out, sys.stdout, ensure_ascii=False, indent=1)


main()
