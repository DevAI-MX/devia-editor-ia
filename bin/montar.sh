#!/bin/bash
source "$(dirname "$0")/entorno.sh"
# montar.sh — ensambla el proyecto HyperFrames desde el video ya cortado.
#
# Uso: bin/montar.sh <video_cut.mp4> <cues.json> <nombre> [beats.json] [keywords.json]
# Deja el proyecto en output/<nombre>/ listo para:
#     npx -y hyperframes@0.7.110 preview        (revision visual)
#     npx -y hyperframes@0.7.110 render -o final.mp4

set -euo pipefail
FFPROBE=ffprobe
RAIZ="$KIT_RAIZ"

CUT="${1:?falta el video cortado}"
CUES="${2:?falta cues.json}"
NOMBRE="${3:?falta el nombre del proyecto}"
BEATS="${4:-}"
KEYS="${5:-}"
TRANS="${6:?falta el transcript por palabra: input/<video>.json (lo crea bin/cortar.sh)}"

PROY="$RAIZ/output/$NOMBRE"
mkdir -p "$PROY"

DUR=$($FFPROBE -v error -show_entries format=duration -of csv=p=0 "$CUT")
DUR=$("$PY" -c "print(round($DUR,3))")

cp "$RAIZ/plantilla/index.html" "$PROY/index.html"
cp "$CUT" "$PROY/aroll.mp4"
mkdir -p "$PROY/fuentes" && cp "$RAIZ"/plantilla/fuentes/*.ttf "$PROY/fuentes/"
# SERIF: la italica de acento. Cambiala aqui o con la variable de entorno.
# La configuracion de estilo manda: la plantilla solo trae valores de respaldo.
# El formato manda: cada formato tiene su propio archivo de configuracion.
FORMATO="${FORMATO:-dinamico}"
ESTILO="${ESTILO:-$RAIZ/formatos/$FORMATO.json}"
[ -f "$ESTILO" ] || { echo "ERROR: no existe la configuracion del formato '$FORMATO' ($ESTILO)" >&2; exit 1; }
# La configuracion viaja a TODO lo que se llame desde aqui (bin/cfg.py la lee del
# entorno). Sin esto los guardianes del final leian el formato por defecto y podian
# juzgar el video con reglas de otro formato.
export ESTILO FORMATO
SERIF="${SERIF:-$("$PY" -c "import json;print(json.load(open('$ESTILO'))['fuentes']['serif'])")}"
[ -f "$PROY/fuentes/$SERIF" ] || { echo "ERROR: no existe la serif $SERIF" >&2; exit 1; }
# palabra clave del CTA: se fija en pantalla hasta el final
CLAVE_TXT=""
if [ -n "$TRANS" ] && [ -f "$TRANS" ]; then
  "$PY" "$RAIZ/bin/palabraclave.py" "$TRANS" "$DUR" > "$PROY/clave.json"
  CLAVE_TXT=$("$PY" -c "import json;print(json.load(open('$PROY/clave.json')).get('palabra',''))")
fi

VOLMUS=$("$PY" -c "import json;print(json.load(open('$ESTILO'))['audio'].get('musica_vol',0.5))")
VOLSFX=$("$PY" -c "import json;print(json.load(open('$ESTILO'))['audio'].get('volumen_sfx',0.45))")
VOLVOZ=$("$PY" -c "import json;print(json.load(open('$ESTILO'))['audio'].get('voz_vol',1.0))")
# -i.bak funciona igual con el sed de Mac y con el de Git Bash; -i '' solo en Mac.
sed -i.bak "s/{{DUR}}/$DUR/g; s/{{SERIF}}/$SERIF/g; s/{{VOLMUS}}/$VOLMUS/g; s/{{VOLSFX}}/$VOLSFX/g; s/{{VOLVOZ}}/$VOLVOZ/g; s/{{CLAVE}}/$CLAVE_TXT/g" "$PROY/index.html"
rm -f "$PROY/index.html.bak"

# El titulo apilado del gancho (editorial): fija sus tiempos por el habla y
# quita de los subtitulos las palabras que ya estan escritas arriba.
if [ -n "$BEATS" ] && [ -n "$TRANS" ] && [ -f "$TRANS" ] && "$PY" -c "import json,sys; b=json.load(open('$BEATS')); sys.exit(0 if ((b.get('gancho') or {}).get('bloques') or b.get('italicas') or any(s.get('tipo') in ('color','broll','ficha') and s.get('at') is None for s in b.get('stingers',[])) or any(p.get('at') is None and p.get('frase') for p in b.get('props',[])) or any(r.get('at') is None for r in b.get('rotulos',[]))) else 1)"; then
  VENTANAS_OUT="$PROY/ventanas.json" "$PY" "$RAIZ/bin/gancho.py" "$BEATS" "$TRANS" "$CUES" "-o$PROY/beats_gancho.json" > "$PROY/cues_gancho.json" || exit 1
  export VENTANAS_JSON="$PROY/ventanas.json"
  BEATS="$PROY/beats_gancho.json"; CUES="$PROY/cues_gancho.json"
fi

# El texto del grafico ES lo que se dice mientras dura (si no se fijo a mano).
if [ -n "$BEATS" ] && [ -n "$TRANS" ] && [ -f "$TRANS" ]; then
  "$PY" "$RAIZ/bin/textograf.py" "$BEATS" "$TRANS" > "$PROY/beats_tx.json" || exit 1
  BEATS="$PROY/beats_tx.json"
fi

# El grafico entra cuando se dice su frase, no donde lo puse a ojo.
if [ -n "$BEATS" ] && [ -n "$TRANS" ] && [ -f "$TRANS" ]; then
  "$PY" "$RAIZ/bin/alinear.py" "$BEATS" "$TRANS" > "$PROY/beats_al.json" || exit 1
  BEATS="$PROY/beats_al.json"
fi

# Los motion graphics no pueden terminar justo antes de un corte del A-roll:
# se alargan hasta el corte para taparlo.
CORTES="${CUT%_cut.mp4}_cortes.json"
if [ -n "$BEATS" ] && [ -f "$CORTES" ]; then
  "$PY" "$RAIZ/bin/encajar.py" "$BEATS" "$CORTES" "" "$RAIZ" > "$PROY/beats.json" || exit 1
  BEATS="$PROY/beats.json"
fi

# keywords palabra por palabra, alineadas al habla cuando se puede
if [ -n "$KEYS" ]; then
  if [ -n "$TRANS" ] && [ -f "$TRANS" ]; then
    "$PY" "$RAIZ/bin/kw.py" "$TRANS" "$KEYS" > "$PROY/keywords.json"
  else
    echo "AVISO: sin transcript, las keywords se reparten uniformemente" >&2
    "$PY" -c "
import json,sys
ks=json.load(open('$KEYS'))
for k in ks:
    t=k['text'].split()
    paso=(k['dur']*0.65)/max(1,len(t))
    k['palabras']=[{'t':t[i],'at':round(k['at']+i*paso,3)} for i in range(len(t))]
json.dump(ks,open('$PROY/keywords.json','w'),ensure_ascii=False,indent=1)"
  fi
  KEYS="$PROY/keywords.json"
fi

# Lo que va a mostrar el motion graphic no se gasta antes en el subtitulo normal.
#
# PERO solo si ese motion graphic se dibuja. Hay formatos que no pintan el bloque de
# tres registros: en dos_lineas el texto son las parejas y en linea el enfasis va en
# cursiva dentro del propio subtitulo. Reservarles sitio a unos bloques que no
# existen borra subtitulos por nada: en el reflexivo se perdia el 25% del guion.
MODO_TXT=$("$PY" "$RAIZ/bin/leer.py" subtitulo.modo "")
KEYS_BLOQUE="${KEYS:-}"
case "$MODO_TXT" in
  dos_lineas|linea) KEYS_BLOQUE=""; echo "  (formato sin bloque: los subtitulos no se recortan)";;
esac

if [ -n "$TRANS" ] && [ -f "$TRANS" ]; then
  "$PY" "$RAIZ/bin/reservar.py" "$CUES" "${BEATS:-}" "$TRANS" "$KEYS_BLOQUE" > "$PROY/cues.json" || exit 1
  CUES="$PROY/cues.json"
fi

# Los subtitulos se resuelven contra los bloques AQUI, no en el render.
# OJO: el 4o argumento es DONDE cuadrar.py escribe las keywords ajustadas. En los
# formatos sin bloque se le pasa una lista vacia y escribia [] ENCIMA de las keywords
# reales de kw.py: se quedaban sin acento el reflexivo y el de dos lineas. Aqui se le
# da un archivo aparte que nadie lee.
KW_SALIDA="$PROY/keywords.json"
[ -z "$KEYS_BLOQUE" ] && KW_SALIDA="$PROY/keywords_bloque_descartado.json"
"$PY" "$RAIZ/bin/cuadrar.py" "$CUES" "$KEYS_BLOQUE" "${BEATS:-}" "$KW_SALIDA" \
  > "$PROY/cues_final.json" || exit 1
CUES="$PROY/cues_final.json"
[ -f "$PROY/keywords.json" ] && KEYS="$PROY/keywords.json"

# Editorial (modo linea): los subtitulos TERMINAN en la palabra clave. El CTA
# "Comenta X" ocupa la pantalla y el resto solo se oye. Se apuntan las palabras que
# se quedan sin rotular en tras_cta.json para que la auditoria no las cuente perdidas.
if "$PY" -c "import json,sys; sys.exit(0 if (json.load(open('$ESTILO')).get('palabra_clave') or {}).get('corta_subtitulos') else 1)" && [ -f "$PROY/clave.json" ]; then
  "$PY" - "$CUES" "$PROY/clave.json" "$PROY/tras_cta.json" <<'PY2'
import json, sys
cues = json.load(open(sys.argv[1])); cl = json.load(open(sys.argv[2])) or {}
if cl.get("desde") is not None:
    d0 = cl["desde"]
    fuera = [c for c in cues if c["start"] >= d0 - 0.05]
    dentro = []
    for c in cues:
        if c["start"] >= d0 - 0.05:
            continue
        # el cue que contiene la palabra clave se recorta: el CTA ocupa su sitio
        if c["end"] > d0 - 0.02:
            if d0 - 0.02 - c["start"] < 0.25:
                fuera.append(c); continue
            c = dict(c, end=round(d0 - 0.02, 3))
        dentro.append(c)
    json.dump([w for c in fuera for w in c["text"].split()], open(sys.argv[3], "w"), ensure_ascii=False)
    json.dump(dentro, open(sys.argv[1], "w"), ensure_ascii=False, indent=1)
    print(f"  subtitulos cortados en la palabra clave: {len(fuera)} cues despues de {cl['desde']}s", file=sys.stderr)
PY2
fi

# b-roll: se declara en el HTML (no por JS) y se copia el material
# MARCO y TITULAR (formato reflexivo). El titular es del VIDEO, no del formato: se
# pasa por entorno porque cambia en cada pieza y es lo unico que no sale del guion.
MARCO_HTML=""
if [ "$("$PY" "$RAIZ/bin/leer.py" marco.arriba "")" != "" ]; then
  MARCO_HTML=$(TITULAR="${TITULAR:-}" "$PY" - "$ESTILO" <<'PYM'
import json, os, sys
c = json.load(open(sys.argv[1]))
lineas = [l for l in os.environ.get("TITULAR", "").split("|") if l.strip()]
if not lineas:
    lineas = c.get("titular", {}).get("lineas", [])
esc = lambda t: (t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))
if c.get("titular", {}).get("mayusculas", True):
    lineas = [l.upper() for l in lineas]
tit = ""
if lineas:
    filas = "".join(f'<div class="t{min(i + 1, 2)}">{esc(l.strip())}</div>'
                    for i, l in enumerate(lineas))
    tit = f'      <div id="titular">{filas}</div>\n'
print('      <div id="marco"><div class="barra arriba"></div>'
      '<div class="barra abajo"></div></div>\n' + tit, end="")
PYM
)
  echo "  marco: barras de ${MARCO_ARRIBA:-formato} + titular ${TITULAR:-'(del formato)'}"
  # la cabeza entra completa, con aire, dentro de la banda (regla del usuario 25-sep)
  CAMARA_POS_Y=$("$PY" "$RAIZ/bin/encuadre.py" "$CUT" \
    "$("$PY" "$RAIZ/bin/leer.py" marco.arriba 16% | tr -d '%' | awk '{print $1/100}')" \
    "$("$PY" "$RAIZ/bin/leer.py" marco.abajo 16% | tr -d '%' | awk '{print $1/100}')" \
    "$("$PY" "$RAIZ/bin/leer.py" marco.aire 0.10)" 2>/dev/null)
  export CAMARA_POS_Y
  echo "  encuadre en el marco: plano al ${CAMARA_POS_Y:-50%} (cabeza completa, con aire)"
fi

PROPS_HTML=""
BROLL_HTML=""
if [ -n "$BEATS" ]; then
  BROLL_HTML=$("$PY" "$RAIZ/bin/broll.py" "$BEATS" "$RAIZ" "$PROY") || exit 1
  # recortes y tarjetas: las imagenes que ponen en escena lo que se dice
  PROPS_HTML=$("$PY" "$RAIZ/bin/props.py" "$BEATS" "$RAIZ" "$PROY") || exit 1
  # y el b-roll no puede ser el mismo que el del video anterior: si se repite, la
  # serie entera se lee como una sola pieza repetida.
  # SIN_REGISTRO=1: remontaje de un video YA registrado (p.ej. cambiarle la cancion).
  # Sin esto la puerta lo rechaza por sus propios clips, que constan como recien usados.
  if [ -z "${SIN_REGISTRO:-}" ]; then
    "$PY" "$RAIZ/bin/registro.py" revisar "$NOMBRE" "$BEATS" || exit 1
  else
    echo "  (remontaje: puerta de repeticiones de b-roll desactivada)"
  fi
fi
"$PY" - "$PROY/index.html" <<PYINJ
import sys
p = sys.argv[1]
s = open(p).read()
import os
s = s.replace("{{BROLL}}", """$BROLL_HTML""")
s = s.replace("{{PROPS}}", """$PROPS_HTML""")
d = os.path.join(os.path.dirname(p), "detras.html")
s = s.replace("{{DETRAS}}", open(d).read() if os.path.exists(d) else "")
s = s.replace("{{MARCO}}", """$MARCO_HTML""")
open(p, "w").write(s)
PYINJ

# GANCHO: en las referencias el arranque suele llevar las tres cosas a la vez — texto
# desde el fotograma 0, movimiento de camara, y una imagen que pone en escena lo que se
# dice. Las dos primeras las pone la plantilla siempre. La imagen NO es obligatoria: se
# pone cuando aporta. Pero si falta se avisa, para que sea una decision y no un olvido.
"$PY" - "$ESTILO" "$PROY/props.json" "${BEATS:-}" <<'PYGAN'
import json, os, sys
c = json.load(open(sys.argv[1]))
arr = c.get("arranque", {})
if not (arr.get("prop_recomendado") or arr.get("prop_obligatorio")):
    raise SystemExit(0)
vent = float(arr.get("ventana", 1.2))
props = json.load(open(sys.argv[2])) if os.path.exists(sys.argv[2]) else []
hay = [p for p in props if p["at"] < vent and p["at"] + p["dur"] > 0.2]
if not hay:
    if arr.get("prop_obligatorio"):
        print(f"ERROR: el gancho no lleva imagen y el formato la exige (primeros {vent}s).",
              file=sys.stderr)
        raise SystemExit(1)
    print(f"  gancho: texto + acercamiento, SIN imagen (opcional; declarala en 'props' "
          f"de beats.json si la escena la pide)")
else:
    print(f"  gancho: texto + acercamiento + {len(hay)} imagen(es)")

# Un prop apoyado abajo no puede subir hasta el texto. El borde de arriba cae en
# (1 - alto) de la altura, y el subtitulo baja hasta un 60% en el peor caso: por encima
# de 0.36 de alto la imagen empieza a comerse el renglon de abajo.
import json as _j
raw = _j.load(open(sys.argv[3])) if len(sys.argv) > 3 and sys.argv[3] and os.path.exists(sys.argv[3]) else {}
for q in raw.get("props", []):
    if str(q.get("sitio", "")).startswith("abajo") and float(q.get("alto", 0.46)) > 0.36:
        print(f"AVISO: el prop de {q['at']}s mide {float(q['alto']):.0%} de alto apoyado abajo: "
              f"su borde superior sube al {100 - float(q['alto']) * 100:.0f}% y el subtitulo baja "
              f"hasta el 60%. Bajalo a 0.34 o menos.", file=sys.stderr)
PYGAN
[ $? -eq 0 ] || exit 1

# iconos.js: solo los iconos declarados en beats.json, en linea
mkdir -p "$PROY"
"$PY" "$RAIZ/bin/iconos.py" "${BEATS:-}" "$RAIZ/plantilla/iconos" > "$PROY/iconos.js" || exit 1

# estilo.js: variables CSS + config para el JS, generadas desde estilo/estilo.json
#
# SUB_Y y BLOQUE_ALTO se pueden pasar por entorno para ESTE video. Donde va el texto
# depende del ENCUADRE, no del formato: la misma persona grabada mas cerca necesita
# el texto mas abajo. Se mide con una regla de porcentajes sobre un fotograma real y
# se pasa aqui, sin tocar la configuracion del formato.
if [ -n "${SUB_Y:-}" ] || [ -n "${BLOQUE_ALTO:-}" ]; then
  "$PY" - "$ESTILO" "$PROY/estilo_video.json" <<'PYSUB'
import json, os, sys
c = json.load(open(sys.argv[1]))
if os.environ.get("SUB_Y"):
    c["subtitulo"]["y"] = os.environ["SUB_Y"]
if os.environ.get("BLOQUE_ALTO"):
    c["bloque"]["alto_max"] = int(os.environ["BLOQUE_ALTO"])
json.dump(c, open(sys.argv[2], "w"), ensure_ascii=False, indent=1)
print(f"  texto de ESTE video: y={c['subtitulo']['y']}, alto_max={c['bloque']['alto_max']}",
      file=sys.stderr)
PYSUB
  ESTILO="$PROY/estilo_video.json"
  export ESTILO
fi
"$PY" "$RAIZ/bin/estilo.py" "$ESTILO" > "$PROY/estilo.js"

# nada inventado: todo el texto en pantalla tiene que decirse en el video
if [ -n "$TRANS" ] && [ -f "$TRANS" ]; then
  "$PY" "$RAIZ/bin/verificar.py" "$TRANS" "${KEYS:-}" "${BEATS:-}" || exit 1
else
  echo "AVISO: sin transcript no puedo verificar que el texto sea real" >&2
fi

# paleta cerrada: blanco por defecto, mostaza para enfasis, rojo excepcional
if [ -n "$KEYS" ]; then
  "$PY" - "$KEYS" <<'PY' || exit 1
import json, sys
PERMITIDOS = {"", "ocre"}          # color de bloque (legacy)
ACENTOS = {None, "chica", "nucleo", "grande", "remate", "serif"}
malos = [k for k in json.load(open(sys.argv[1])) if k.get("color", "") not in PERMITIDOS]
if malos:
    print("ERROR paleta: en el texto solo hay blanco y ocre. Nada mas.", file=sys.stderr)
    for k in malos:
        print(f"  '{k['text']}' usa color '{k.get('color')}'", file=sys.stderr)
    sys.exit(1)
ks = json.load(open(sys.argv[1]))
malos_ac = [k for k in ks if k.get("acento") not in ACENTOS]
if malos_ac:
    print("ERROR: 'acento' solo puede ser chica, nucleo/grande o remate/serif.", file=sys.stderr)
    for k in malos_ac:
        print(f"  '{k['text']}' usa acento '{k.get('acento')}'", file=sys.stderr)
    sys.exit(1)
# El 10% se mide sobre TODO el texto en pantalla, no sobre el numero de frases:
# las frases animadas ya son la capa destacada, asi que exigirles el 10% dejaba el
# recurso practicamente sin usar.
con = sum(1 for k in ks if k.get("acento") or k.get("color"))
print(f"  acento ocre en {con} de {len(ks)} frases animadas", file=sys.stderr)
PY
fi

# pulso de la cancion: hace falta ANTES que los zooms, porque los zooms se ajustan
# a el y porque la musica tiene que arrancar en el golpe que dice el analisis.
PISTA="${MUSICA_PISTA:-$("$PY" -c "import json;print(json.load(open('$ESTILO'))['audio'].get('pista',''))")}"
# la pista puede cambiar POR VIDEO (beats.audio.pista): entre un video y el siguiente
# la cancion tiene que variar un poco (regla del usuario, 10-sep)
if [ -n "$BEATS" ] && [ -f "$BEATS" ]; then
  _PB=$("$PY" -c "import json;print((json.load(open('$BEATS')).get('audio') or {}).get('pista',''))")
  if [ -n "$_PB" ]; then
    case "$_PB" in /*) PISTA="$_PB";; *) PISTA="$RAIZ/musica/$_PB";; esac
    echo "  pista de este video: $(basename "$PISTA")"
  fi
fi
MUSICA_INICIO=8
if [ -n "$PISTA" ] && [ -f "$PISTA" ]; then
  "$PY" "$RAIZ/bin/compas.py" "$PISTA" "$DUR" > "$PROY/compas.json" || rm -f "$PROY/compas.json"
  [ -f "$PROY/compas.json" ] && MUSICA_INICIO=$("$PY" -c "import json;print(json.load(open('$PROY/compas.json')).get('inicio_pista',8))")
fi

# numeros del guion: los puntos de una lista salen en grande arriba
if [ -n "$TRANS" ] && [ -f "$TRANS" ]; then
  "$PY" "$RAIZ/bin/numeros.py" "$TRANS" "$DUR" > "$PROY/numeros.json"
else
  echo "[]" > "$PROY/numeros.json"
fi

# estimulos: rellena con zooms cualquier tramo de mas de 3s sin nada
"$PY" "$RAIZ/bin/estimulos.py" "$CUES" "${BEATS:-}" "${KEYS:-}" "$DUR" > "$PROY/zooms_libres.json"

# y se les da un empujon de centesimas para que caigan con la musica, solo cuando
# el golpe queda a un pelo: si no, el zoom se queda encima de la palabra
"$PY" "$RAIZ/bin/ritmo.py" "$PROY/zooms_libres.json" "$PROY/compas.json" \
  > "$PROY/zooms.json" || cp "$PROY/zooms_libres.json" "$PROY/zooms.json"

# pares.json: subtitulos en DOS LINEAS (formato impacto). Se arman del transcript,
# que es lo unico que tiene tiempo por palabra, y el propio script comprueba que no
# se pierde ni se inventa una sola palabra.
MODO_SUB=$("$PY" -c "import json;print(json.load(open('$ESTILO')).get('subtitulo',{}).get('modo',''))")
if [ "$MODO_SUB" = "dos_lineas" ]; then
  [ -n "$TRANS" ] && [ -f "$TRANS" ] || { echo "ERROR: el modo dos_lineas necesita el transcript" >&2; exit 1; }
  ESTILO="$ESTILO" "$PY" "$RAIZ/bin/pares.py" "$TRANS" "${KEYS:-}" "$PROY/clave.json" \
    > "$PROY/pares.json" || exit 1
  echo "  subtitulos en dos lineas: $("$PY" -c "import json;print(len(json.load(open('$PROY/pares.json'))))") parejas"
else
  echo "[]" > "$PROY/pares.json"
fi

# Editorial: el gancho es voz desnuda y la musica entra EN el corte que lo
# cierra. Se busca el primer corte del A-roll despues del titulo (o de 4.5s).
MUSICA_DESDE=0; MUSICA_FADE_OUT=0.8
if "$PY" -c "import json,sys; sys.exit(0 if json.load(open('$ESTILO')).get('audio',{}).get('musica_desde')=='fin_gancho' else 1)"; then
  MUSICA_FADE_OUT=$("$PY" -c "import json;print(json.load(open('$ESTILO'))['audio'].get('musica_fade_out',0))")
  MUSICA_DESDE=$("$PY" - "${BEATS:-}" "$CORTES" "$ESTILO" <<'PYG'
import json, sys, os
beats = json.load(open(sys.argv[1])) if sys.argv[1] and os.path.exists(sys.argv[1]) else {}
cfg = json.load(open(sys.argv[3]))
t0 = float((cfg.get("audio", {}).get("musica_desde_min") or 4.5))
for bl in (beats.get("gancho") or {}).get("bloques", []):
    if bl.get("fin") is not None: t0 = max(t0, float(bl["fin"]))
bordes, acc = [], 0.0
if os.path.exists(sys.argv[2]):
    for a, b in json.load(open(sys.argv[2]))["keep"][:-1]:
        acc += b - a; bordes.append(round(acc, 3))
fin = next((c for c in bordes if c >= t0), t0)
print(f"{fin:.3f}")
PYG
)
  echo "{\"t\": $MUSICA_DESDE}" > "$PROY/gancho_fin.json"
  echo "  fin del gancho: la musica (y el riser) entran en el corte de ${MUSICA_DESDE}s"
fi

# Zoom en los cortes (editorial): un solo calculo para plantilla y sfx.
ZOOM_CORTES=""
if "$PY" -c "import json,sys; sys.exit(0 if (json.load(open('$ESTILO')).get('estimulos',{}).get('punch_en_cortes') or {}).get('activo') else 1)"; then
  T0=$("$PY" -c "import json;a=json.load(open('$ESTILO')).get('arranque',{});print((a.get('duracion') or a.get('dur') or 0.62)+0.05 if (a.get('activo') or a.get('modo')) else 0)")
  "$PY" "$RAIZ/bin/zoomcortes.py" "$CORTES" "$DUR" "$T0" > "$PROY/zooms_cortes.json" || exit 1
  ZOOM_CORTES="$PROY/zooms_cortes.json"
fi

# cues.js: todo lo variable del video en un solo archivo editable
export ESTILO_JSON="$ESTILO"
# Subtitulos DEBAJO de la cabeza (editorial): la altura se mide por video con la
# cara (bin/barbilla.py) cuando el formato dice subtitulo.y = "auto". beats.subtitulo.y manda si existe.
SUB_Y_AUTO=""
if "$PY" -c "import json,sys; sys.exit(0 if str(json.load(open('$ESTILO')).get('subtitulo',{}).get('y'))=='auto' else 1)"; then
  SUB_Y_AUTO=$("$PY" - "$CUT" "$ESTILO" "${BEATS:-}" "$RAIZ" <<'PYSY'
import json, subprocess, sys, os
cut, estilo, beats_p, raiz = sys.argv[1:5]
cfg = json.load(open(estilo)); sub = cfg.get("subtitulo", {})
b = json.load(open(beats_p)) if beats_p and os.path.exists(beats_p) else {}
if (b.get("subtitulo") or {}).get("y"):
    print(str(b["subtitulo"]["y"])); sys.exit(0)
r = subprocess.run([sys.executable, os.path.join(raiz, "bin", "barbilla.py"), cut], capture_output=True, text=True)
barb = float(r.stdout.strip().rstrip("%") or 66) / 100
y = min(barb + float(sub.get("bajo_barbilla", 0.06)), float(str(sub.get("y_max", "80%")).rstrip("%")) / 100)
print(f"{100 * y:.1f}%")
PYSY
)
  echo "{\"y\": \"$SUB_Y_AUTO\"}" > "$PROY/sub_y.json"
  echo "  subtitulos bajo la barbilla: centro al $SUB_Y_AUTO"
fi
export SUB_Y_AUTO
FOCO_CARA=""
if "$PY" -c "import json,sys; sys.exit(0 if json.load(open('$ESTILO')).get('arranque',{}).get('foco')=='auto' else 1)"; then
  FOCO_SAL=$("$PY" "$RAIZ/bin/foco.py" "$CUT" 2>/dev/null)
  FOCO_CARA=$(echo "$FOCO_SAL" | sed -n 1p); FOCO_ESCALA=$(echo "$FOCO_SAL" | sed -n 2p)
  echo "  foco del primer plano: la cara esta en $FOCO_CARA (escala propuesta $FOCO_ESCALA)"
fi
export FOCO_CARA FOCO_ESCALA CORTES_JSON="$CORTES"
"$PY" - "$CUES" "${BEATS:-}" "${KEYS:-}" "$PROY/zooms.json" "$PROY/clave.json" > "$PROY/cues.js" <<'PY'
import json, sys, os
cues = json.load(open(sys.argv[1]))
beats = json.load(open(sys.argv[2])) if len(sys.argv) > 2 and sys.argv[2] else {"stingers": [], "listas": []}
keys = json.load(open(sys.argv[3])) if len(sys.argv) > 3 and sys.argv[3] else []
zooms = json.load(open(sys.argv[4]))
out = lambda n, v: print(f"window.{n} = {json.dumps(v, ensure_ascii=False)};")
out("__CUES__", cues)
out("__BEATS__", beats)
out("__KEYWORDS__", keys)
out("__ZOOMS__", zooms)
clave = json.load(open(sys.argv[5])) if len(sys.argv) > 5 and sys.argv[5] else None
out("__CLAVE__", clave or None)
import os
nums_p = os.path.join(os.path.dirname(sys.argv[4]), "numeros.json")
out("__NUMEROS__", json.load(open(nums_p)) if os.path.exists(nums_p) else [])
pares_p = os.path.join(os.path.dirname(sys.argv[4]), "pares.json")
out("__PARES__", json.load(open(pares_p)) if os.path.exists(pares_p) else [])
props_p = os.path.join(os.path.dirname(sys.argv[4]), "props.json")
out("__PROPS__", json.load(open(props_p)) if os.path.exists(props_p) else [])
rot = beats.get("rotulos", []) if isinstance(beats, dict) else []
out("__ROTULOS__", rot)
det_p = os.path.join(os.path.dirname(sys.argv[4]), "detras.json")
out("__DETRAS__", json.load(open(det_p)) if os.path.exists(det_p) else [])
# editorial: donde esta la cara (para el primer plano) y los cortes del A-roll
# (para el punch zoom en cada corte) y el fin del gancho (para el punch 'hero')
out("__FOCO__", os.environ.get("FOCO_CARA", ""))
out("__SUB_Y__", os.environ.get("SUB_Y_AUTO", "") or None)
out("__FOCO_ESCALA__", float(os.environ.get("FOCO_ESCALA") or 0) or None)
_cortes_p = os.environ.get("CORTES_JSON", "")
_bordes, _acc = [], 0.0
if _cortes_p and os.path.exists(_cortes_p):
    for _a, _b in json.load(open(_cortes_p))["keep"][:-1]:
        _acc += _b - _a; _bordes.append(round(_acc, 3))
out("__CORTES__", _bordes)
_zc = os.path.join(os.path.dirname(sys.argv[4]), "zooms_cortes.json")
out("__ZOOM_CORTES__", json.load(open(_zc)) if os.path.exists(_zc) else [])
_gf = os.path.join(os.path.dirname(sys.argv[4]), "gancho_fin.json")
out("__GANCHO_FIN__", json.load(open(_gf))["t"] if os.path.exists(_gf) else None)
PY

# cama musical con ducking bajo la voz
# pista real de la libreria si esta declarada en el formato o en el entorno
MUSICA_CARACTER="$("$PY" "$RAIZ/bin/leer.py" audio.musica_caracter "")" MUSICA_PISTA="$PISTA" MUSICA_INICIO="$MUSICA_INICIO" MUSICA_DESDE="$MUSICA_DESDE" MUSICA_FADE_OUT="$MUSICA_FADE_OUT" "$PY" "$RAIZ/bin/musica.py" "$CUT" "$DUR" "$PROY/musica.wav" \
  "$("$PY" -c "import json;print(json.load(open('$ESTILO'))['audio'].get('musica_db',-26))")"

# pista de SFX (clicks por cue + whoosh/impacto por stinger)
CORTES_JSON="$CORTES" ZOOM_CORTES="$ZOOM_CORTES" GANCHO_FIN="$MUSICA_DESDE" "$PY" "$RAIZ/bin/sfx.py" "$CUES" "$DUR" "$PROY/sfx.wav" "${BEATS:-}" "$PROY/zooms.json" "${KEYS:-}"

# Aviso si una frase animada choca con un motion graphic (gana el grafico)
"$PY" - "${KEYS:-}" "${BEATS:-}" <<'PYCHOQUE'
import json, sys
if len(sys.argv) > 2 and sys.argv[1] and sys.argv[2]:
    ks = json.load(open(sys.argv[1])); bs = json.load(open(sys.argv[2])).get("stingers", [])
    for k in ks:
        # el b-roll no descarta la frase: va debajo de la narracion
        ch = [b for b in bs if b.get("tipo") != "broll"
              and k["at"] < b["at"] + b.get("dur", 0)
              and k["at"] + k.get("dur", 0) > b["at"]]
        if ch:
            print(f"  AVISO: la frase '{k['text']}' choca con el motion graphic de "
                  f"{ch[0]['at']}s y NO se mostrara (manda el grafico)", file=sys.stderr)
PYCHOQUE

# Los stingers NO son automaticos: se ponen a mano en beats.json. Este aviso
# existe para que no se conviertan en un tic sin que nos demos cuenta.
"$PY" "$RAIZ/bin/densidad.py" "${BEATS:-}" "$DUR" "$ESTILO"

# GATE: ejecuta la composicion en Chrome y falla si hay error de JS. Un fallo de
# ejecucion (una constante usada antes de declararse, por ejemplo) no lo detecta
# ninguna comprobacion de sintaxis, y deja el video sin subtitulos sin avisar.
if ! (cd "$PROY" && npx -y hyperframes@0.7.110 check >"$KIT_TMP/hf_check.log" 2>&1); then
  echo "ERROR: la composicion no pasa 'hyperframes check'." >&2
  tail -20 "$KIT_TMP/hf_check.log" >&2
  exit 1
fi
echo "  check: la composicion se ejecuta sin errores"

# GATE 2: auditoria de contenido. Falla si algo que se dice no llega a pantalla o
# si un motion graphic va desfasado respecto a su frase. Es el chequeo que faltaba:
# el video puede renderizar perfecto y aun asi haber perdido palabras.
if [ -n "$TRANS" ] && [ -f "$TRANS" ]; then
  if ! "$PY" "$RAIZ/bin/auditar.py" "$PROY" "$TRANS" >"$KIT_TMP/hf_audit.log" 2>&1; then
    echo "ERROR: la auditoria encuentra fallos de contenido:" >&2
    cat "$KIT_TMP/hf_audit.log" >&2
    exit 1
  fi
  grep -E "PALABRAS|DESFASE" "$KIT_TMP/hf_audit.log" | sed 's/^/  /'

  # GATE 3: TRIPLE REVISION de subtitulos. Obligatoria, no opcional.
  # Los subtitulos han fallado de cuatro maneras distintas (repeticiones, cues
  # duplicados, texto que no aparece, bloques solapados) y ninguna se caza a ojo.
  if ! "$PY" "$RAIZ/bin/revisar.py" "$PROY" "$TRANS" >"$KIT_TMP/hf_subs.log" 2>&1; then
    echo "ERROR: la triple revision de subtitulos encuentra problemas:" >&2
    cat "$KIT_TMP/hf_subs.log" >&2
    exit 1
  fi
  tail -1 "$KIT_TMP/hf_subs.log" | sed 's/^/  /'
fi

[ -n "$BEATS" ] && [ -z "${SIN_REGISTRO:-}" ] && "$PY" "$RAIZ/bin/registro.py" apuntar "$NOMBRE" "$BEATS" >/dev/null

echo "proyecto: $PROY  (duracion $DUR s)"
echo "  preview: cd $PROY && npx -y hyperframes@0.7.110 preview"
echo "  render : cd $PROY && npx -y hyperframes@0.7.110 render -o final.mp4"
