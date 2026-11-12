# Especificación del editor de video · Devia Consulting

Hecho por Devia Consulting.

Este documento es el manual técnico del editor: cada medida y cada regla, con su porqué. Lo usa Claude al editar; no hace falta leerlo para usar el kit.

Monólogo a cámara, plano fijo, vertical 1080×1920 a 30fps, para Instagram y TikTok.

**Estilos que trae el kit: `limpio`, `dinamico` y `reflexivo`.** `dinamico` parte de los
valores del antiguo `pulso`; `limpio` es `pulso` sin frases animadas, sin graficos, sin
b-roll y sin relleno de zooms (modo `linea`); `reflexivo` se queda como estaba. Lo que
cada uno permite colocar esta en su clave `contenido`. Las menciones a otros estilos que
aparecen abajo (fresco, editorial, impacto...) son historial de como se midieron los
valores: esos archivos ya no vienen en el kit.

**Encuadre dentro del marco (reflexivo, 25-sep-2026).** La banda va centrada y en 4:5
exacto (14.84% arriba y abajo, 1080x1350) y el plano se coloca con `bin/encuadre.py`: detecta
la cara, estima el borde de arriba de la cabeza (el pelo sube ~25% del alto de la cara,
medido; antes se suponia 40% y quedaba casi un 20% de fondo vacio encima) y deja
`marco.aire` (7% de la banda en el momento mas alto, ~9% el resto) libre por encima. Regla del
usuario: la cabeza se ve completa, con aire, y un poco de torso. Antes la banda iba
14.9%/26.5% y el video se recortaba por el centro: cortaba la cabeza.
Todo lo de aquí está medido sobre las referencias medidas (`referencia1/2/3.mp4`) o
decidido por él explícitamente. Lo que se apartó de la referencia está marcado.

**La edición depende del formato.** Estas reglas valen para talkinghead. Otro formato
(lista acumulativa, b-roll dominante, entrevista a dos) se edita distinto y necesita
su propio archivo en `formatos/`.

Configuración de máquina: `formatos/<formato>.json`. Ese archivo manda; los valores
del HTML son solo respaldo por si se abre suelto. Hay uno por cliente (ver la tabla
en la sección 0).

---

## 0. Las reglas que no se negocian

1. **Nada inventado.** Todo el texto en pantalla es cita literal de lo que se dice.
   Única excepción: el gancho fijo de cabecera. `bin/verificar.py` aborta el montaje
   si algo no se dice, es estricto: rechaza "el escalofrío" si lo dicho es "un
   escalofrío".
2. **Todo lo que se dice, se ve, y a tiempo.** Ni una palabra sin aparecer, ninguna
   antes o después de su momento. Si un bloque va a tapar habla, el texto del bloque
   ES esa habla.
3. **Nunca más de 3s sin estímulo.** Cuentan: frase animada, motion graphic, b-roll,
   zoom. El hueco se mide de fin a inicio, no entre inicios.
4. **Nada se da por hecho: se mide.** Tres puertas obligatorias abortan el montaje:
   `hyperframes check` (que la composición se ejecute), `bin/auditar.py` (contenido) y
   **`bin/revisar.py`** (triple revisión de subtítulos).

### El orden de trabajo
**1) Limpiar la voz. 2) Elegir la música. 3) Lo demás.** En ese orden, siempre.
La limpieza va dentro del corte, que es el primer paso del pipeline.

### La configuración manda
`formatos/<formato>.json` es la fuente de verdad y los scripts la leen con
`bin/cfg.py`. Ningún valor vive escrito a mano en el código: si estuviera en los dos
sitios, cambiar el json no haría nada y la configuración mentiría.

### Un formato por cliente
`formatos/<nombre>.json` y se monta con `FORMATO=<nombre> bin/montar.sh …`. El
formato base es `talkinghead`; lo que cambia entre clientes es la PALETA y los
extras, nunca la estructura ni las reglas de arriba.

| formato | para quién | qué cambia |
|---|---|---|
| `talkinghead` | impacto () | acento ocre `#FFDE21`, beat de trap, sin arranque |
| `fresco` | salud y bienestar | acento **verde `#8FE6A6`**, jazz/lofi/soul instrumental, arranque con gancho triple |

La clave del acento se sigue llamando `ocre` en las dos porque así la leen los
scripts; en el formato de la marca su valor es un verde. Su marca es luminosa (verde,
blanco, crema) y el dorado pertenece al formato de impacto.

---

## 1. Cadena de herramientas y por qué

| Pieza | Herramienta | Por qué |
|---|---|---|
| Corte | ffmpeg, una pasada | 6.5× tiempo real |
| Transcripción | whisper large-v3, español: mlx-whisper en Mac con chip Apple, faster-whisper (CPU, int8) en Windows, Linux y Mac Intel | ~2× tiempo real en M5 con mlx; ~1× en el CPU del M5 con faster-whisper. Las dos dan las mismas palabras (medido: diferencia máxima de 0.02 s por palabra) |
| Composición y render | HyperFrames 0.7.110 (HTML+GSAP) | 1.1× tiempo real |
| SFX y música | sintetizados en local con numpy | sin licencias, duración exacta |

**Medido: el corte NO se hace dentro de HyperFrames.** Un clip de vídeo + gráficos
renderiza 9.8s en 8.6s; el mismo corte hecho con 3 `<video>` tarda 99s por 9s, 11×
más fresco. Se corta en ffmpeg y HyperFrames recibe **una sola pieza**.


---

## 2. El corte

```bash
bash bin/cortar.sh input/video.mp4 [umbral_dB] [dur_min_silencio]
```

- Silencios a **-32 dB, > 0.28s**, con 0.10s de aire a cada lado.
- **Los silencios se detectan sobre una copia normalizada a -16 LUFS.** El umbral es
  absoluto: en material grabado bajo (uno venía a -39.9 LUFS) caía por encima de parte
  del habla y el corte entraba DENTRO de las palabras. El transcript salía lleno de
  sílabas partidas ("e inicia...", "esa... ...horía de amigo").
- **El vídeo empieza en la primera palabra** (`bin/arranque.py`). El detector marca el
  fin del silencio en cuanto sube algo de energía (una respiración, un roce del micro)
  así que el corte arrancaba medio segundo antes de hablar. Se deja 0.05s de aire.
- Reencodeo con **`-g 30 -keyint_min 30`**. Sin esto los keyframes salen dispersos,
  HyperFrames avisa de seeks fallidos y el render tarda ~30% más.
- Audio siempre reencodeado a AAC 192k. Nunca `-c copy` a secas.

### Limpieza de voz (primer paso, siempre)
1. **DeepFilterNet3** separa voz de ruido con red neuronal: quita sala, aire y zumbido
   sin el sonido "bajo el agua" de un reductor clásico. ~50× tiempo real.
2. **EQ**: -2.5 dB en 250 Hz (turbidez), +3.5 dB en 3.2 kHz (presencia, donde vive la
   inteligibilidad), +2.5 dB en 7.5 kHz (aire).
3. Deesser, compresión suave y **loudnorm a -14 LUFS**. La voz es lo que más se oye.

Medido en un caso real: de -39.9 a -15.1 LUFS, con la banda de presencia subiendo del
8.9% al 13.5% de la energía. Efecto secundario importante: **la transcripción mejora
mucho**, pasó de "frontera de amigo" a "categoría de amigo".

Los filtros van encadenados en un solo `-af` junto al corte. Un segundo `-af` sobreescribe
al primero: pasó, y quedó un vídeo de 46s con audio de 67s.

### Retomas (crítico)
El hablante arranca una frase, se corta y la repite. Si se dejan los dos intentos,
el vídeo empieza con una toma rota. `bin/retomas.py` transcribe **el fragmento corto y
el arranque siguiente por separado** y los compara por similitud (≥0.6).

- Es retoma → se **descarta**.
- No es retoma → se **fusiona** con el vecino, porque un fragmento suelto de menos de
  1.2s en plano fijo se lee como un hipo, no como un corte.

Por qué así: mirar el transcript completo no sirve, whisper alinea la palabra partida
a caballo de las dos tomas. Y comparar por prefijo exacto tampoco: la toma rota se
transcribe mal justamente por estar cortada ("tuanciet" vs "tu ansiedad").

---

## 3. Subtítulos normales

| Propiedad | Valor | Origen |
|---|---|---|
| Fuente | Inter **SemiBold 600** | decision de estilo (la referencia usa menos peso) |
| Color | blanco, **solo** blanco | - |
| Cuerpo | 68px (baja a 46 si hace falta) | medido: 2.8% de tinta |
| Interletrado | **-0.038em** | Inter Regular abre visualmente; necesita más ajuste que la Black |
| Centro vertical | **62%** | petición: justo sobre la línea del tercio inferior |
| Margen lateral | 10% | medido: mínimo 12.8% |
| Ritmo | ~64 cambios/min | medido |
| Animación | **ninguna** | aparecen y desaparecen en seco |
| Sombra | halo oscuro suave alrededor | sin borde |

Reglas de troceado (`bin/cues.py`), 2-4 palabras, **una sola línea**:
- Ningún cue termina en preposición, conjunción o artículo: esa palabra se empuja al
  siguiente.
- Cada cue dura hasta que empieza el siguiente. **Ni huecos ni solapes**, aunque haya
  una pausa al hablar.
- Corte forzado en puntuación y en pausa > 0.35s.
- **Sin puntos** en pantalla (ni suspensivos). Las comas sí.

---

## 4. Frases animadas (el bloque)

Bloque de tres registros, medido en `referencia1` frame 51.35s:

| Registro | Ratio | Fuente | Caja |
|---|---|---|---|
| chica (arriba) | **0.50** | Inter Bold | minúsculas |
| grande (centro) | **1.00** | Inter Black | MAYÚSCULAS |
| serif (remate) | **0.75** | Playfair Display Italic | minúsculas |

- **Solo la grande cambia de tamaño.** Busca el cuerpo más grande que quepa en la zona
  segura (techo 168px), así una palabra corta llena la pantalla. La chica y la serifa
  se calculan sobre `cuerpo_ref` (112px) con tope: **no crecen** con ella.
- Ancho máximo **84%**; contenedor al 8%/92%. Medido en render: el bloque más ancho va
  de 8.3% a 91.7%.
- Interlineado 0.90, sin solape en la chica, -0.12 en la serifa.
- Interletrado: grande -0.03em, serifa **-0.055em** (va más apretada).
- Sombra: brillo del propio color (`currentColor`) al **35%/30px** + halo oscuro flojo
  **sin el componente desplazado**, que es el que se leía como borde.

### Cómo se reparten las palabras
Conectores del principio → chica; las **2** primeras palabras con contenido → grande;
desde el siguiente conector → serifa. Si la frase no empieza por conector y tiene ≥4
palabras, la primera sube igualmente: sin línea de arriba el bloque queda descabezado.

### Aparición
- **Palabra por palabra, con timing real del habla** (`bin/kw.py` busca la frase en el
  transcript). Si es paráfrasis, reparte uniforme y lo avisa.
- **Cada palabra ya está en su posición definitiva desde el frame cero**; solo se
  revela (opacity, scale, y). Una palabra que apareció **no se mueve nunca**.
- Entrada por registro: chica desde la izquierda (-34px), grande desde abajo (+30px),
  serifa desde la derecha (+38px). 0.30s, `power3.out`.
- Al acabar se van **todas juntas** en 0.16s. El siguiente subtítulo **no entra** hasta
  que ha desaparecido del todo (+0.04 de margen).
- La ventana se amplía sola si no cubría hasta la última palabra.
- Acomodo: seis variantes que rotan por orden, para que no se repita nunca igual.

### Mayúsculas
**Solo la primerísima línea de todo el guion.** El resto en minúsculas. La línea grande
va en mayúsculas por rol tipográfico, no por ortografía.

---

## 5. Color

| Color | Uso | Valor |
|---|---|---|
| Blanco | ~90% de todo el texto | `#ffffff` |
| Amarillo | ~10%: la palabra con énfasis | **`#FFDE21`** |

No hay un tercer color. El acento puede ir en **cualquier registro** (`acento`:
`chica` / `nucleo` / `remate`), no solo en el central. La auditoría mide la proporción
real sobre todo el texto en pantalla y avisa por encima del 25%.

---

## 6. Motion graphics

**No son automáticos.** Se colocan a mano en `beats.json`. Lo único automático es la
regla de los 3s, que se rellena con zooms. `bin/densidad.py` avisa por encima de
**8/min**: si salen siempre, dejan de ser un golpe y pasan a ser el fondo.

### Tipos de fondo (se elige por lo que se dice)
`anillos` propagación · `malla` sistema · `barras` comparación · `pulso` cuerpo/urgencia
· `flecha` crecimiento · `cifra` estadística · `alerta` peligro · `orbe` revelado ·
`ondas` algo que llega · `icono` cualquier concepto concreto.

Tonos: `navy`, `rojo`, `negro`, `verde`. El acento del gráfico sale del tono.

### Profundidad (3 capas, solo la de abajo se mueve)
1. `.grafico`, push lento 1.00→1.12, ease lineal, origen 50%/48%.
2. `.dof`, `backdrop-filter: blur(18px)` enmascarado radialmente; entra a 30px y se
   limpia a 18px en 0.9s. **Verificado**: con brillo equiparable, el borde tiene 72%
   menos detalle que el centro.
3. `.vineta` (13%/26%, muy suave) + `.grano` (feTurbulence al 11%, `overlay`).

**El texto va por encima de las tres y no se mueve**: medido, su caja es idéntica al
píxel en 7.60s y 7.90s mientras el gráfico crece.

### Entrada y salida
Entra con fundido cruzado de 0.34s. **Sale en seco.** Un fundido de salida destapa el
clip de abajo justo cuando puede haber un corte y se leen dos saltos donde debería
haber uno.

**Nunca termina justo antes de un corte del A-roll**: `bin/encajar.py` lo alarga hasta
el corte (ventana 0.6s) para taparlo. Nunca lo acorta.

**Entra cuando se dice su frase**: `bin/alinear.py` lo mueve al instante real del
transcript. El `at` que se escribe a mano es solo una pista de zona.

### Iconos
Biblioteca **Lucide 1.31.0 (ISC)**, ~2000 iconos de trazo con `currentColor`, en
`plantilla/iconos/`. Se incrusta solo el que se usa.

Tamaño base **470px**, halo 700px, trazo afinado a 1.35. Grandes a propósito: uno
pequeño en medio de un fondo oscuro deja la pantalla vacía y no protagoniza.

Tratamiento obligatorio: halo radial detrás, doble `drop-shadow` del color, entrada
desenfocada (blur 18px→0 en 0.52s, como una lente enfocando) y respiración de escala.

Ocho composiciones que rotan **por orden de aparición** (no por hash del instante: dos
iconos podían caer en la misma por casualidad):
`duo` · `asomado-izq` · `esquinas` · `inclinado-der` · `patron` · `asomado-der` ·
`centro` · `inclinado-izq`.

### Dónde va el texto del gráfico
Usa **el mismo bloque** que las frases animadas. Su posición la decide **dónde queda el
hueco de la composición**, no `icono_pos`:

| Composición | Piezas | Texto |
|---|---|---|
| duo, esquinas | arriba y abajo / en las esquinas | **centro** (50%) |
| asomado | a un lado | centro-bajo (55%) |
| centro, inclinado, patrón | ocupan una mitad | al lado contrario |
| pulso, barras, cifra, alerta | objeto arriba | abajo (63%) |
| ondas, flecha | objeto abajo | arriba (38%) |
| malla | sin objeto | medio |

---

## 6b. B-roll

Material del usuario, en `input/broll/`. Se declara en `beats.json`:
```json
{"at": 6.3, "dur": 3.0, "tipo": "broll", "media": "friendzone.mp4", "media_start": 0.4}
```

Recibe **el mismo tratamiento** que un gráfico generado (push, desenfoque de bordes,
viñeta, grano): eso es lo que hace que el material propio y los motion graphics
parezcan de la misma pieza.

**No lleva texto propio.** Un motion graphic trae su texto y se queda con el hueco del
subtítulo; el b-roll va DEBAJO de la narración, así que los subtítulos siguen
corriendo por encima. Lleva un velo degradado para que se lean sobre material claro.

Tres gotchas verificados, cada uno costó un diagnóstico:
- Un `<video>` inyectado por JS **no se registra**: HyperFrames compila los clips del
  HTML inicial. Se declara en el HTML durante el montaje, y necesita `id` o sale
  congelado.
- Un vídeo temporizado **dentro** de otro elemento temporizado se congela en el render.
- `<img class="clip">` no funciona: HyperFrames solo gobierna `<video>` por la línea de
  tiempo. Las imágenes las revela GSAP.

Coste medido: +1.5s de render por un inserto corto. El 11× de la sección 1 era por
trocear todo el A-roll, no por b-rolls.

**Al elegir b-roll, mirarlo.** Los nombres de archivo no dicen nada (`c103.mp4`): hay
que sacar frames y revisar hojas de contacto. Y el clip de prueba tiene que ser
visualmente distinto del A-roll, o un fallo de "no se ve" es indistinguible de un
acierto, pasó dos veces.

## 6c. El texto del motion graphic

**Es lo que se dice mientras dura**, compuesto del transcript con el tiempo real de
cada palabra (`bin/textograf.py`). Antes se elegía un titular a mano y todo lo demás
que sonaba durante esos segundos no aparecía en ninguna parte.

Se le aplica la regla de coherencia: la ventana se recorta hasta la última palabra con
contenido, para que no acabe en conector ("tus intenciones **e**"). Lo que sobra vuelve
a los subtítulos.

El gráfico se va **0.08s después de su última palabra**. Con más margen tapaba lo que
ya se estaba diciendo.

## 6d. La palabra clave del CTA

Cuando el vídeo pide "comenta X y te mando Y", esa palabra es lo único que el
espectador tiene que recordar. `bin/palabraclave.py` detecta el verbo de llamada
(comenta, escribe, manda, pon, teclea, di, responde, contesta), toma la palabra
siguiente saltándose artículos, y la **fija en pantalla desde que se dice hasta el
final del vídeo**.

En mayúsculas, ocre, 138px, con pastilla oscura detrás (sobre fondo claro el amarillo
solo con glow se perdería). Va al **20.5% de altura**: dentro de la banda útil y por
encima de la cabeza. Medido en el render: ocupa del 18% al 21.8%, y el pelo empieza
sobre el 26%.

## 2b. La cadencia: que no pare de hablar

Más de medio segundo de silencio seguido rompe la retención. La regla del formato es
más dura: **nada por encima de `cortes.pausa_max` (0.28s)**, y lo que pase se recorta
hasta dejar `cortes.pausa_deja` (0.16s).

**Por qué hace falta un segundo paso.** `silencedetect` usa un umbral ABSOLUTO y por
bien que se calibre se le escapa casi todo. Medido sobre el corte ya hecho de
la marca quedaban **29 silencios de más de 0.3s que sumaban 14 segundos**, con picos
de 0.88s. El corte parecía limpio y no lo estaba.

**Por qué no vale medirlo por palabras.** Fue el primer intento y falló: whisper
alarga el final de cada palabra hasta bien entrado el silencio, así que un hueco real
de 0.9s se medía como 0.2s. Con los tiempos de palabra se cerraban 5 huecos; midiendo
energía, 46.

**Cómo se mide entonces.** El umbral es RELATIVO a su voz: se toma el percentil 92 de
la envolvente como "nivel de habla" y se considera silencio todo lo que baje del
`nivel_rel` (12%) de eso. Da igual si grabó bajo o alto, o si cambió de habitación.

**De dónde se corta.** Siempre del CENTRO del silencio, nunca de los bordes: así entre
el corte y la voz queda medio respiro y no se come ni la consonante final ni el ataque
de la palabra siguiente.

**Islas.** Una palabra corta y dicha flojito ("sí", "ya", "mira") puede quedar por
debajo del umbral y desaparecer dentro de un silencio, pasó, se perdió un "sí" de los
258 de un vídeo. Antes de cortar se busca dentro del hueco cualquier repunte que dure
más de 0.08s y el hueco se parte por ahí.

Resultado en los tres vídeos: de 29/36/40 silencios a **cero por encima de 0.30s**, y
-14.8s / -12.0s / -14.2s de duración sin perder una palabra.

Los dos recortes (silencio y cadencia) se aplican en la MISMA pasada de ffmpeg: el
segundo se calcula sobre el audio del primero y después se traduce a tiempo de la
fuente, así que el vídeo se codifica una sola vez.

## 2c. Las capas

El orden del DOM no basta, y el z-index tampoco es toda la historia. Dos problemas
distintos, los dos con el mismo sintoma (el b-roll tapando los subtitulos):

**1. z-index.** El b-roll estaba declarado ANTES que `#subs` y aun asi lo tapaba, en
los diez tramos de un video sin una sola excepcion. Se fija a mano:

| capa | quien | por que |
|---|---|---|
| 1 | `.stinger.broll` | es fondo: la narracion sigue corriendo por encima |
| 2 | `.stinger` (motion graphics) | toman la pantalla y traen su propio texto |
| 5 | `#subs` | |
| 6 | `#keys` (frases animadas) | |
| 8 | `#clave` (palabra del CTA) | nunca la tapa nada |

**2. HDR.** Y aun con el z-index puesto, UN vídeo de los tres seguía fallando. La
causa: dos de sus b-rolls eran grabaciones **HLG del iPhone** y las etiquetas de color
viajaban dentro del clip. Basta **un** clip HDR para que HyperFrames detecte HDR en
todo el proyecto, se vaya por su rama HDR (salida HEVC en vez de H.264) y en esa rama
los subtitulos queden POR DEBAJO del b-roll en el mp4. En la composicion se veian
bien: `snapshot` pasaba y solo fallaba el render.

Se arregla en el origen: `bin/escena.sh` etiqueta **siempre** bt709 con `setparams`
(los `-color_*` de salida no bastan, ffmpeg los hereda del input). Los pixeles no se
tocan, HLG bien expuesto se lee correcto como bt709, comprobado contra el A-roll. Y
el render se lanza con `--sdr` como segunda barrera.

**Como se caza:** si el mp4 sale en HEVC teniendo todo lo demas igual, hay un clip HDR
dentro. `ffprobe -show_entries stream=color_transfer` sobre cada b-roll lo canta:
`arib-std-b67` es HLG, `smpte2084` es PQ.

## 2d. Dónde va el texto

**Se mide por ENCUADRE, no por formato ni por cliente.** La misma persona grabada más
cerca necesita el texto más abajo: en los primeros vídeos de la marca la barbilla caía
entre el 57% y el 62% y el texto fue al 74%; en los siguientes, grabados mucho más
cerca, cayó entre el 62% y el 68% y hubo que bajarlo al 77%. Por eso `SUB_Y` y
`BLOQUE_ALTO` se pueden pasar por entorno para UN vídeo, sin tocar la configuración
del formato:

```bash
SUB_Y=77% BLOQUE_ALTO=270 FORMATO=fresco bin/montar.sh …
```

Se mide igual siempre: una regla de porcentajes sobre un fotograma real de ese vídeo.

`subtitulo.y` es el centro tanto del subtítulo normal como del bloque animado. Se mide
sobre los encuadres reales del cliente, no se elige de memoria: con una regla de
porcentajes encima de un fotograma de cada vídeo.

En los de la marca la barbilla cae entre el 57% y el 62%, así que el texto al 62% le
cruzaba la cara. Entre la barbilla y el borde de la banda útil (83%) solo quedan 19
puntos de pantalla, y ahí tiene que caber el bloque entero: `subtitulo.y` 74% y
`bloque.alto_max` 340px (justo el 18%).

## 6e. El gancho de apertura (arranque)

Los tres ganchos caen JUNTOS en el primer segundo, o no hay gancho:

| gancho | qué es | dónde vive |
|---|---|---|
| visual | zoom out: el vídeo abre a escala 1.55 sobre su cara y se abre a 1.0 | `arranque` en el formato → `#camara` en la plantilla |
| auditivo | un whoosh que CAE en el frame 0 | `arranque()` en `bin/sfx.py` |
| de texto | la primera frase animada | primer `keywords.json` |

Se activa con el bloque `arranque` del formato:

```json
"arranque": { "activo": true, "escala": 1.55, "duracion": 0.62, "ease": "power3.out", "sfx_nivel": 0.34 }
```

Dos cosas medidas, no opinadas:

- **La duración tiene que ser menor que un segundo.** Por encima deja de leerse como
  un golpe y se lee como un movimiento de cámara. 0.62s.
- **El whoosh CAE, no sube.** El whoosh que anuncia un motion graphic sube de energía
  porque anticipa algo que va a pasar. Este acompaña un zoom que ya está pasando en
  el frame 0: ataque instantáneo, filtro que se cierra y una cola grave corta. Puesto
  a subir sonaba a que faltaba algo detrás.

El arranque cuenta como estímulo en `bin/estimulos.py`: sin eso se metía un zoom
encima del propio arranque y los dos peleaban por el mismo `transform` de `#camara`.

## 6b2. El b-roll no se oscurece

El b-roll llevaba un velo negro de arriba abajo para que el subtitulo se leyera
encima. Se quita: apagaba justo el material que se ha ido a buscar. Lo unico que
queda alrededor es el desenfoque de bordes (`.dof`); la vineta tambien se retira en
el b-roll (en los motion graphics sigue).

La legibilidad la sostiene el halo del propio subtitulo. Comprobado sobre el plano
mas brillante y mas ruidoso que habia (un puesto de fruta a pleno sol): se lee sin
problema y la imagen mantiene su color.

## 6b3. Que dure hasta el corte

Si un b-roll o un motion graphic va a terminar a menos de `stingers.encaje` (1.2s)
de un corte del A-roll, se ALARGA hasta el corte y sale de golpe. Asi se ve UN salto
de plano donde si no se verian dos seguidos, y el video se siente mas natural.

Lo hace `bin/encajar.py`, que ya existia pero apenas disparaba por dos motivos:

- la ventana eran 0.6s y los cortes caian a 0.85s y 1.09s;
- el recorte por metraje del clip se aplicaba **despues**, deshaciendo la extension.

Ahora la ventana sale de la configuracion y el estirado respeta desde el principio
tres topes: el corte, la pieza siguiente y el metraje real del clip (un b-roll al que
se le pide mas de lo que dura se queda congelado en su ultimo fotograma).

## 6f. B-roll sacado de una película

`bin/escena.sh <película> <inicio> <duración> <desvío -1..1> <salida.mp4> [luz]`

Recorta a sangre a 9:16 desde cualquier fuente (16:9, 4K vertical, 4096×1728) y deja
el clip listo para `input/broll/`.

**Siempre a sangre, nunca en carta sobre fondo desenfocado.** Probado y descartado: un
16:9 metido a lo ancho dentro de un 9:16 ocupa el 32% de la altura y se ve diminuto,
con más relleno borroso que película.

El precio de recortar es perder los lados, y el sujeto casi nunca está en el centro
exacto: para eso está el **desvío**, que mueve la ventana de recorte (0 centro, -1
pegado a la izquierda, 1 a la derecha). Sin él, un plano de Miranda a la izquierda del
cuadro se convertía en un plano de Andy.

El parámetro **luz** levanta brillo, contraste y saturación a la vez. El diario de
Un clip oscuro está rodado muy oscuro y cálido; con la viñeta y el velo del b-roll
encima, la cara se perdía en un móvil. Con 0.10 vuelve sin lavar la película.

**Cómo se eligen las escenas sin ver la película entera:** hojas de contactos. Un
fotograma cada 6s en mosaico para localizar las zonas, y después un fotograma por
segundo de las zonas que interesan para clavar la entrada y la salida. Después de
cortar, otra hoja con tres momentos de cada clip (0.3s, 1.3s, 2.3s): la mitad de los
clips que parecían buenos en el primer fotograma acababan en un plano borrido o con
el sujeto ya fuera de cuadro.

## 6g. Los efectos al ritmo de la canción

El objetivo es que los golpes caigan con la música **sin que se note forzado**. Dos
piezas:

`bin/compas.py` saca el pulso de la pista sin librerías de análisis musical: flujo
espectral → autocorrelación entre 70 y 165 BPM para el tempo → fase por tren de
pulsos → primer tiempo de compás por peso. Después corrige compás a compás con el
pico real de la señal, porque **la rejilla se desvía**: 114.8 BPM medidos frente a los
~117 reales son dos segundos de deriva al final de un vídeo de dos minutos.

Y elige dónde arranca la canción: en un golpe de verdad pasada la intro, no a los 8s
fijos de antes. Así el frame 0 del vídeo cae en el uno del compás y el whoosh de
apertura suena CON la música.

`bin/ritmo.py` empuja cada zoom hasta `ritmo.ajuste` (0.13s) para que coincida con un
golpe. **La regla es no forzar**: si el golpe queda más lejos, el zoom se queda donde
estaba, encima de la palabra. Vale más un efecto fuera del compás que uno fuera de la
frase. Como el SFX de cada zoom sale de ese mismo archivo, el efecto queda pegado al
beat sin tocar nada más.

Dos rejillas por orden: primero el "uno" del compás, que es el que se siente; si ese
queda lejos, el tiempo suelto. Ajustarse solo al uno dejaba fuera casi todos los zooms
(con compases de 1.5s, una probabilidad entre seis).

## 6h. Motion graphics en claro

El fondo de un motion graphic es oscuro por defecto (`navy`, `negro`, `rojo`,
`verde`). Para la marca van en CLARO: `crema`, `menta`, `salvia`.

Sobre claro hay que invertir tres cosas o no se lee nada, y las tres se declaran
juntas en el mismo bloque CSS:

| variable | oscuro | claro | por qué |
|---|---|---|---|
| `--tinta` | blanco | `#16302a` | obvio |
| `--ocre` (acento) | verde claro | `#0f7a4c` | el verde claro de los subtítulos sobre crema desaparece |
| `--glow-bloque` | halo negro | halo blanco | un halo negro alrededor de letra oscura la ensucia |

La viñeta del tratamiento común también se baja al 18%: en oscuro da profundidad, en
claro solo ensucia el fondo.


El texto del gráfico sale de `stingers.cuerpo` (126 para la marca). Estaba fijo en 96
y se quedaba pequeño al lado de las frases animadas, que llegan a 168; sobre un fondo
claro y vacío se notaba aún más.

Dos cosas que se aprendieron colocándolos:

- **Una frase animada que choca con un motion graphic NO se muestra** (manda el
  gráfico) y con ella se pierden todas sus palabras. El montaje lo avisa; hay que
  colocar los gráficos en huecos donde no haya frase.
- **Cuanto más larga es la ventana del gráfico, más texto compone** y más encoge el
  bloque para caber. Con 2.9s salían ocho palabras, el cuerpo bajaba mucho y aun así
  una fila se salía por la derecha. Menos ventana, menos texto, más tamaño.

## 6i. TalkingHeadImpacto, subtítulos en dos líneas

Formato `impacto` (`formatos/impacto.json`). Se monta con
`FORMATO=impacto bin/montar.sh …`. Imita los cinco reels de
`~/Downloads/referencias`, manteniendo Inter como pidió el editor.

**Lo que cambia respecto a `talkinghead`: el sistema de texto entero.** En las
referencias no hay bloque de tres registros ni serifa de acento. Todo lo escrito son
**dos líneas de la misma sans**:

- una **entradilla pequeña** arriba (el trozo anterior de la frase),
- las **palabras clave grandes** debajo, que entran **una a una** al ritmo del habla,
- y las dos **se van juntas** cuando entra la pareja siguiente.

### Lo que está medido, no elegido a ojo

Sobre los cinco vídeos de referencia (720×1280), llevado a 1920 de alto:

| medida | referencia | cómo queda |
|---|---|---|
| tinta de la línea pequeña | 52 px | `cuerpo_lead` 83 |
| tinta de la línea grande | 72 px | `cuerpo_clave` 108 |
| ancho de la línea grande | 44% de mediana | `ancho_max` 0.80 (tope) |
| centro del bloque | 56% de la altura | `y` 55% |
| hueco entre las dos líneas | 20% del alto de la letra | `pegado` 0.22 |
| acento (énfasis y CTA) | - | `colores.ocre` `#FFDE21` |

### Reglas del texto

- **No todo va emparejado.** Una línea sola en grande pesa mucho más que la misma
  línea con una entradilla encima, así que se reserva para donde hace falta ese peso:
  la línea que lleva la palabra con acento, y la que abre frase justo después de un
  punto. Sale en torno a un 38% de líneas solas, y de paso el ritmo deja de ser el
  mismo compás una y otra vez.
- **La palabra del CTA se queda en pantalla.** Sale en grande y en amarillo con su
  pareja, y cuando el resto se apaga ella no se va: viaja despacio hasta una esquina y
  se queda ahí hasta el final, para que se entienda que es lo importante
  (`subtitulo.cta_fijo`). El viaje sale **primero de lado y luego sube**: en línea
  recta cruzaría por encima del subtítulo siguiente. No pasa del 19% de altura, que
  por encima está la zona donde Instagram pinta su interfaz.
- **Dos palabras por renglón** (`palabras_max` 2, `caracteres_max` 24). Con tres o
  cuatro el cuerpo tiene que encoger y el bloque pierde el golpe: en las referencias
  la línea grande es siempre corta ("una charla", "de pelotudear").
- **Sin puntos ni comas** (`sin_puntos`). La pausa la marca el cambio de pareja. Las
  interrogaciones y exclamaciones sí se quedan: cambian el tono de lo que se lee.
- **Ninguna línea puede ser solo palabras de enlace.** "es que" o "a la" sueltos no
  dicen nada; se funden con la vecina (con tope, para no crear un renglón kilométrico).
- **Ninguna línea se parte en dos.** `white-space: nowrap` y el cuerpo baja hasta que
  entra. Cada línea se ajusta **por su cuenta**, con la entradilla topada al 85% de la
  grande para no perder la jerarquía.
- **UN SOLO acento de color: amarillo**, tanto para la palabra de énfasis como para la
  del CTA. Las referencias usan rojo `#D9000A` y ámbar `#FEB403` por separado, pero el
  rojo se apaga contra la camisa negra y el fondo oscuro.
- **El amarillo lleva halo propio.** Medido en el render: el núcleo del glifo daba 197
  de luminancia contra 255 del blanco, un 26% más oscuro. Puesto solo con el color, la
  palabra acentuada llamaba MENOS que el texto normal. El halo del mismo amarillo no
  sube la luminancia del glifo pero enciende el área alrededor, y multiplica por 6 la
  superficie que atrae al ojo.
- **El acento se raciona**: como mucho uno cada `acento_cada` segundos (12 por defecto).
  Si la keyword trae `bloque`, la fila `grande` manda y va en rojo sí o sí; el resto
  compite y gana la palabra con más cuerpo. La palabra con acento va **sola en su renglón
  y abajo**, en la entradilla el énfasis no se ve.
- **El CTA lleva el mismo acento amarillo**, en la línea grande, con "comenta" de entradilla encima. Se
  fuerza el corte para que caiga así. El chapón rojo de `#clave` no se dibuja en este
  formato: sería un segundo CTA a la vez.
- **Los motion graphics no llevan texto.** El gráfico se queda, el titular se va: un
  titular encima de la pareja son dos textos pisándose en el mismo sitio.

### Props: las imágenes que ponen en escena lo que se dice

Es lo que separa las referencias de un talking head normal. Además del b-roll a
pantalla completa hay **recortes limpios** pegados junto al que habla (un grupo de
gente, una cara, un objeto), **tarjetas** con una foto, y **capturas** de mensajes.

Van en `props` dentro de `beats.json` y se declaran en HTML, nunca por JS (HyperFrames
compila los medios del HTML inicial). Capa **por encima del plano y del b-roll, por
debajo del texto**: en las referencias el subtítulo cruza por delante del recorte,
nunca al revés. **Sin desenfoque de bordes ni velo**: son piezas limpias, y eso es lo
que las hace parecer parte de la escena en vez de un adorno pegado.

```json
{"at": 0.0, "dur": 3.5, "archivo": "amigos.png",
 "tipo": "recorte", "sitio": "abajo-der", "alto": 0.44}
```

- `tipo`: `recorte` (PNG transparente apoyado en el borde) · `tarjeta` (esquina
  redondeada con filo blanco; **acepta foto o vídeo**) · `captura` (se dibuja, no
  lleva archivo).
- `sitio`: `abajo` `abajo-izq` `abajo-der` `izq` `der` `arriba-izq` `arriba-der`.
- `alto`: fracción de la altura del cuadro.

**Detrás del que habla.** Un prop con `"detras": true` no busca hueco: se le pone
detrás. `bin/matte.py` saca una copia del A-roll con el fondo transparente, solo el
sujeto, y esa copia se pinta encima del elemento, así que el cuerpo y las manos pasan
por delante. Cuesta ~1s por fotograma y se cachea (la firma va por el TAMAÑO del
A-roll, no por su fecha: el montaje lo vuelve a copiar cada vez).

Tres cosas que hay que saber antes de usarlo:

- El zoom se anima **por clase** (`.camara`), no por id, para que el recorte del sujeto
  se mueva exactamente igual que el plano. Si no, el plano se acerca y el recorte se
  queda quieto: doble desalineado.
- El alfa de la segmentación va **duro** (todo lo que pasa de la mitad, opaco del
  todo). Con el alfa suave el elemento de detrás se transparenta a través del cuerpo y
  se ve un fantasma sobre la ropa.
- **Depende del encuadre, y en muchos no cabe.** Probado en el vídeo del 25 de agosto:
  él y el sillón ocupan del 10% al 90% del ancho, así que un recorte de cuerpo entero
  puesto detrás se queda escondido, centrado lo tapa él entero, y a un lado se sale
  de cuadro. Funciona cuando hay sitio libre a los lados del sujeto, que es como está
  grabada la referencia. Si no lo hay, el recorte va DELANTE, apoyado abajo.

**Dónde puede ir sin tapar nada.** Medido sobre fotogramas reales de este encuadre: la
cara acaba en el **48%** y el texto nunca baja del **59,4%**. Un recorte apoyado abajo
con `alto: 0.34` empieza en el 66%: no toca ni una cosa ni la otra, y queda centrado.
Por encima de `0.36` el montaje avisa, porque el borde de arriba ya se mete en el
renglón de abajo del subtítulo.

El material sale de `input/props/` o del `input/broll/` que ya tiene el proyecto (ver
`input/props/LEEME.md`). Una tarjeta con vídeo es la pieza de la referencia donde una
escena corre dentro de un rectángulo al lado del que habla, y no hace falta traer nada
nuevo: sirve el b-roll que no se esté usando a pantalla completa. Para recortar una
foto o un fotograma: `bin/recortar.py <archivo|video> <segundo> salida.png`, que
segmenta con `isnet-general-use` y **falla** si la máscara sale vacía, antes eso
producía un PNG entero transparente y el prop salía invisible sin que nadie se
enterase hasta ver el vídeo.

**Capturas** (notificaciones de mensaje y chats). No llevan archivo: se dibujan en
markup, así el texto sale nítido a cualquier tamaño. Todo en **español neutro**, con
nombres de pila genéricos: el avatar es la inicial sobre un círculo, nunca una cara,
una cara real en una notificación recreada sería suplantar a alguien.

```json
{"at": 7.4, "dur": 3.0, "tipo": "captura", "estilo": "dm",
 "sitio": "arriba-der", "alto": 0.30,
 "items": [{"de": "Ana", "texto": "hola, ¿cómo estás?", "cuando": "hace 2 min"}]}

{"at": 33.6, "dur": 3.2, "tipo": "captura", "estilo": "chat",
 "sitio": "der", "alto": 0.56, "contacto": "Ana",
 "mensajes": [{"lado": "yo", "texto": "hola, ¿cómo estás?", "hora": "21:36"}]}
```

Las notificaciones **caen de una en una**, no las tres de golpe: así se lee como un
teléfono que va sonando, que es lo que cuenta la escena.

Una captura solo entra si el guion **habla de mensajes**. Puestas porque sí no
ilustran nada y se leen como relleno: en el vídeo del 25 de agosto se probaron dos y
hubo que quitarlas, porque en todo el guion no se menciona ni un chat.

### Los zooms: ligeros y lentos

El formato base empuja un 12% de golpe seco y un 9% en 1,6s. Aquí no: el movimiento
tiene que sentirse fresco, no llamar la atención.

| | base | impacto |
|---|---|---|
| golpe | 12%, **corte seco** | 4,5%, **rampa** de 1,2s |
| entrada | 9% en 1,6s | 3% en **2,6s** |
| salida | 9% en 1,4s | 3% en **2,4s** |

El corte seco es lo que rompía la sensación de pieza cara: el ojo lo lee como un salto
de montaje, no como una cámara que se acerca. Con `zoom_seco: false` el golpe pasa a
ser una rampa.

**Cada zoom se corta antes de que arranque el siguiente.** Con rampas de 2,6s y zooms
cada 1,8s los dos tweens se pisan sobre la misma escala, y al renderizar por saltos de
fotograma GSAP recoge el valor de partida equivocado y se ve un tirón.

El **arranque** no se toca: el zoom out de apertura (1,75 → 1,0 en 0,55s) es el gancho
visual y tiene que golpear. Lo que se suaviza son los zooms del cuerpo del vídeo.

### La ficha: pantalla clara con un símbolo

Es lo que hace que el vídeo no sea puro b-roll. El plano **corta** a una pantalla clara
(`#f7f6f3` con trama de puntos tipo lienzo, no blanco liso) con un **emoji 3D grande**
elegido por lo que se está diciendo, y vuelve. Sacado del vídeo de HIELO: fondo claro,
texto negro, símbolo grande. Los emojis salen de `musica//IMAGENES/Emojis`
(copiados a `input/props/emoji/`).

```json
{"at": 9.8, "dur": 2.4, "tipo": "ficha", "emoji": "cerebro.png", "emoji_sitio": "arriba"}
```

**El emoji y el subtítulo se componen como un bloque** dentro del área de respeto,
los tres quintos de en medio, **20%–80%**. Por debajo del 80% lo tapa la interfaz de
la app. Dos composiciones:

| `emoji_sitio` | emoji | subtítulo |
|---|---|---|
| `arriba` (o `arriba-izq` / `arriba-der`) | 22%–46% | baja al 62% |
| `abajo` (o `abajo-izq` / `abajo-der`) | 54%–78% | sube al 38% |

El subtítulo **no se calla** durante la ficha: sigue corriendo, pintado en **negro**,
y el negro dura exactamente lo que dura el fondo claro, ni un fotograma antes ni
después. **Las palabras con acento también van en negro sobre la ficha**: el amarillo
sobre blanco no se lee. Tienen su propio color por CSS, así que hay que pisarlo a
propósito y devolverlo al salir. Callarlo se comía palabras; ponerlo negro con una clase fija dejaba negro el
trozo que se salía al plano oscuro.

**Hay que alternar el sitio** de una ficha a la siguiente. Puesto siempre en el
centro, todos los vídeos empiezan a parecer el mismo. Y no repetir el emoji de la
referencia sobre un guion parecido (la diana en "cambia el objetivo" quedaba calcado).

### El gancho

En las referencias el arranque suele llevar las tres cosas a la vez: **texto desde el
fotograma 0**, **movimiento de cámara** y **una imagen que pone en escena lo que se
dice**. Las dos primeras las pone la plantilla siempre. La imagen **no es
obligatoria** ( se pone cuando aporta ) pero si falta el montaje lo avisa, para que
sea una decisión y no un olvido (`arranque.prop_recomendado`).

Si la imagen va en el gancho, se declara con **`at: 0`** y entonces **no entra: ya
está puesta en el fotograma 0**. Deslizando tardaba tres décimas en verse y el primer
golpe de vista se perdía, que es justo lo que no puede pasar en el arranque. El resto
de props sí entran deslizando desde su borde.

### Cómo se arma

`bin/pares.py transcript.json keys.json clave.json > pares.json`, que corre dentro de
`montar.sh` cuando `subtitulo.modo` vale `dos_lineas`. Trabaja **directamente sobre el
transcript**, que es lo único con tiempo por palabra: recorre las palabras en orden y
solo decide dónde cortar. Al terminar compara la secuencia de palabras de salida con
la de entrada y **falla** si no cuadra, en vez de entregar un vídeo con texto de menos.

Las tres puertas siguen valiendo: `auditar.py` y `revisar.py` detectan el modo y
auditan **las parejas**, que es lo que se dibuja, en vez de los cues y los bloques.

## 6j. TalkingHeadImpactoLento, el mismo formato, al otro ritmo

`cinematico`. Mismo sistema de texto que el de impacto, dos líneas
de Inter, acento amarillo, palabra clave que se queda, pero con el ritmo al otro lado.
Para guiones melancólicos o reflexivos, donde acelerar mata lo que se cuenta.

| | rápido | lento |
|---|---|---|
| silencio permitido | 0,28s | **0,55s** |
| estímulo cada | 3,0s | **5,5s** |
| zoom | 4,5% en 2,6s | **2,8% en 3,4s** |
| música | beat de hip hop | **orquestal** |
| nivel de música | 0,62 | **0,72** |
| efectos | 0,55 | **0,34** |
| click por palabra | sí | **no** |
| arranque | 1,75 en 0,55s + destello | **1,30 en 1,6s, sin destello** |
| golpe dramático | 0,30 cada 14s | **0,38 cada 10s** |

Las decisiones que no son solo "bajarle a todo":

- **Aquí el silencio suma.** En el rápido no se permite medio segundo de silencio
  porque mata la retención; aquí la pausa es parte de lo que se cuenta. Se sigue
  cortando lo muerto, pero se deja el doble de aire.
- **Sin click por palabra.** El click es un recurso de ritmo rápido: en un vídeo lento
  suena a máquina de escribir y pelea con la orquesta.
- **El obturador de cámara no vale**: es un chasquido y corta el aire. El cambio de
  plano lo hace un whoosh cinematográfico largo, que entra con la imagen en vez de
  golpearla. Y sin efecto de vuelta: el regreso al plano se deja limpio.
- **El boom pesa más y sale más seguido** (0,38 cada 10s contra 0,30 cada 14). Con
  menos efectos alrededor tiene sitio para respirar, y es el que marca el peso
  emocional.
- **El gancho no golpea, se abre.** El zoom out del rápido es un puñetazo; aquí la
  cámara se abre despacio y sin flash. El texto sigue entrando desde el fotograma 0.
- **La música manda.** Con pocos efectos, es lo que sostiene el vídeo.

## 6l. TalkingHeadImpactoJazz, el punto medio, con jazz

`nocturno`. El editor pidió "un poco más pausado", no el lento entero:
el melancólico (6j) frena tanto que un guion con consejo dentro se cae. Este formato se
sienta **entre los dos**, y cambia de familia musical.

| | rápido | **jazz** | lento |
|---|---|---|---|
| pausa permitida | 0,28s | **0,42s** | 0,55s |
| aire que se deja | 0,22s | **0,32s** | 0,42s |
| hueco sin estímulo | 3,0s | **4,5s** | 5,5s |
| zoom | 4,5% / 2,6s | **3,6% / 3,0s** | 2,8% / 3,4s |
| música | beat de hip hop | **jazz de club** | orquestal |
| nivel de música | 0,62 | **0,66** | 0,72 |
| efectos | 0,55 | **0,42** | 0,34 |

**Por qué jazz y no clásica.** El editor pidió "buen ritmo pero distinta, clásica o jazz".
La clásica de la biblioteca (*Claro de Luna*, Debussy) no tiene pulso: es rubato, y los
zooms no tienen dónde caer, el formato engancha los estímulos a los golpes de la canción
(`ritmo.ajuste`). El jazz sí lleva pulso, así que el ritmo se sostiene solo sin empujar
como el hip hop. Pista: `INSTRUMENTAL/alex-morgan-jazz-midnight-club-music-556242.mp3`.

**Todas verificadas sin voz cantada** con la prueba mid/side (una voz va centrada y
dispara la banda de 300-3000 Hz en el canal central; aquí el centro queda POR DEBAJO de
los lados en las tres):

| pista | centro | lados |
|---|---|---|
| alex-morgan-jazz-midnight-club | 48% | 61% |
| freegroove-seduction-jazz | 43% | 56% |
| grand_project-sensual-jazz | 48% | 55% |
| *clair-de-lune (descartada)* | *69%* | *70%* |

**El b-roll va a la mitad.** Regla del usuario para esta tanda: donde antes iban 5 clips
en 70s, ahora van 2-3. Las fichas de emoji NO se reducen, son lo que impide que el vídeo
sea puro plano fijo, y con menos b-roll pesan más.

**Gotcha de los emojis.** Cuatro archivos de `input/props/emoji/` estaban mal nombrados y
salió una **pizza** donde el guion decía "te quedas congelado": `nieve.png` era la pizza,
`pensando.png` era el copo, `trofeo.png` era la cara pensando y `copa.png` el trofeo.
Renombrados (1-sep-2026) para que cada archivo sea lo que dice. Si un emoji sale absurdo
en un montaje, mirar la hoja de contactos antes que el código.

**Canciones nuevas (11-sep-2026), ya en `AUDIOS/MUSICA/INSTRUMENTAL`.** El editor pidió
dejar de usar *Without Me* en este formato y ordenar lo que descarga en la biblioteca.
Prueba mid/side (banda 300-3000 Hz, centro contra lados) y tempo de `bin/compas.py`:

| pista | centro | lados | BPM | nota |
|---|---|---|---|---|
| Base de rap pensativo - Hip hop jazz saxofon | 28% | 83% | 92 | usada en `regalasviajes`; la batería entra en el 43,9s |
| Drake - Circadian Rhythm (Instrumental) | 14% | 53% | 97 | sin voz |
| Smooth Jazz Ballad - Backing Track in Dm | 4% | 47% | 146 | balada sin solista, la más calmada |
| Thelonious Monk - Round Midnight (1947) | - |, | 110 | MONO: la prueba mid/side no vale; grabación de época |
| Lofi suave (Instrumental) | 20% | 64% | - | sin voz |

Una canción distinta por vídeo: se declara en `beats.audio.pista`.

## 6m. El gancho: donde se juega la retención

Regla del usuario: *"la mayor capacidad de retención debe estar en el gancho"*. Los
primeros `gancho.dur` segundos (3,0 por defecto) juegan con otras reglas que el resto:

- **El acento no se raciona.** Fuera del gancho sale uno cada `acento_cada` segundos y
  solo compiten palabras que vengan de una keyword. Medido en `comenta3`, eso dejaba el
  gancho con **cero acentos**: ninguna de sus frases generaba keyword. Así que dentro
  del gancho el acento se elige **por peso propio**, las `gancho.acentos` (3) palabras
  más largas que no sean enlace. En `comenta3` eso da *cualquiera*, *hablar*,
  *comunicarse*.
- **Cada palabra suena.** Al entrar, cada palabra lleva su propio click ligero
  (`gancho.click_nivel`, 0,85). Fuera del gancho el subtítulo va **mudo** a propósito:
  si el tic sonara todo el rato dejaría de significar nada. Entre 6 y 15 clicks por
  vídeo, según cuántas palabras entren en esos 3 segundos.

Esto se suma al gancho triple que ya existía (§6i): zoom out, whoosh en el frame 0 y
primera frase animada.

## 6m-bis. La apertura va más densa que el resto

Medido en `comentasocialing`: **nada visual hasta el segundo 15,4** y **cero zooms
dentro del gancho**. La causa era el propio relleno de `bin/estimulos.py`: el zoom out
de apertura cuenta como estímulo (bien, si no se pisaba con él), y a partir de ahí
esperaba el hueco COMPLETO del formato ( 4,5s en jazz ) antes de meter el siguiente.

Ahora hay dos límites: `estimulos.apertura_hueco` (2,0 rápido / 2,4 jazz / 2,8 lento)
durante los primeros `estimulos.apertura_dur` (15s), y `hueco_max` para el resto. El
usuario: *"la gente se va a ir corriendo si en los primeros 3 segundos no los estimulas
bien y después solo estoy hablando con subtítulos"*.

Además, **el primer b-roll o ficha va antes del segundo 3,5** en los cuatro vídeos: los
zooms sostienen, pero no sustituyen a un corte de plano.

## 6ñ. Dos cosas que el texto no puede hacer

**Los nombres propios no bajan.** Todo el guion se pasa a minúsculas salvo la primera
línea (§6i), y eso convertía *Daniel* en *daniel*, que se lee como falta y no como
estilo, justo en la frase donde el nombre del cliente ES la prueba. Los nombres van
declarados a mano en `subtitulo.propios`: deducirlo por la mayúscula no vale, porque la
palabra que abre frase también va capitalizada.

**Un signo suelto no es una palabra.** Whisper parte `99 %` en dos tokens y el troceador
los repartía en cues distintos: en pantalla se leía *"que el 99"* y el `%` llegaba
después, como si fueran dos ideas. `%`, `º`, `ª` y las monedas se pegan al token
anterior en `cues.py` y en `pares.py` (los dos leen el transcript por su cuenta).

## 6o. Los cortes del A-roll se disfrazan

Regla del usuario: *"si hay cortes en el video, lo más preferible es disfrazarlos lo más
posible"*. Un salto de plano a cara descubierta se ve mal; tapado por un gráfico, no
existe. `bin/encajar.py` lo resuelve en dos capas:

1. **Pegar lo que ya hay.** Si un corte cae hasta `stingers.encaje` (2,0s) DESPUÉS del
   final de un gráfico, el gráfico se alarga hasta el corte exacto. Y si cae hasta 2,0s
   ANTES del inicio de un b-roll, el b-roll **adelanta su entrada** al corte. Las fichas
   no se adelantan (su emoji va con una frase concreta). Crece como mucho
   `encaje_crece_max` en total entre los dos lados: sin tope, un b-roll con corte a cada
   lado se iba a 6s y tapaba dos frases.
2. **Cantar los que quedan.** El montaje imprime `CORTES AL DESCUBIERTO` con el instante
   de cada uno: ahí va un b-roll que **empiece en el corte**. En `comenta100` (12 cortes
   en 52s) quedaron 9 al aire; con b-rolls puestos en ellos, 0.

Dos gráficos con una décima de plano entre medias se leen como OTRO corte: se pegan
(el primero termina donde empieza el segundo).

**Repetición de clips entre vídeos:** la chica bebiendo de la copa salió en tres vídeos
seguidos (`cita_brindis`, `cita_copa`, `ella_cita_copa` son la misma idea). El registro
mira nombres de archivo, no ideas: cuando dos clips cuentan lo mismo, cuentan como uno.

## 6p. El reparto de pantalla y el sonido que va con él

Regla del usuario: **~50% su plano, ~30% b-roll, ~20% motion graphic**. `estimulos.py`
imprime el reparto real en cada montaje (`reparto: cara 48% / b-roll 31% / mg 21%`).
Si hace falta bajar b-roll sin destapar cortes, un b-roll puede pasar a ficha (mismo
corte tapado, otro reparto) y el resto se acorta a ~1,8s.

**Los zooms se retiran cuando la pantalla ya cambia sola:** si los gráficos cubren más de
`estimulos.cobertura_alta` (45%), el hueco permitido se multiplica por
`cobertura_factor` (1,5). En `comenta100` eso bajó los zooms de 11 a 2.

**Sonido, versión sobria** (1-sep-2026): efectos al 78% de lo que estaban, boom al 75%.
El cambio de plano suena **solo con el obturador de cámara, a la entrada y a la salida**
(`sfx_archivo.solo_archivo`): la paleta sintética (marea, subdrop, reversa…) se calla.
Y **cada pareja de subtítulos entra con un click pequeño** (`audio.click_subtitulo`,
0,45), salvo dentro del gancho, donde ya suena uno por palabra.

## 6n. Fichas con foto: la cara del cliente

Una ficha puede llevar `foto` en vez de `emoji`, la cara de un cliente cuando el guion
lo nombra. Va **enmarcada** (radio 22px y sombra), ocupando el 40% de la altura, no a
sangre: a sangre compite con el talking head y deja de leerse como una prueba puesta
sobre la ficha. Entra posándose (`power3.out`, sin el rebote del emoji: una cara dando
botes se lee como broma). El archivo va en `input/props/fotos/` y `bin/broll.py` lo
copia al proyecto, igual que los emojis.

**Gotcha del material:** dos clips de la reserva no eran del tema y se colaron al subir
el b-roll un 50%, `ella_campo` es alguien jugando al tenis y `rosa_pared` una imagen
abstracta amarilla. Y `flores_manos` venia **girado 90°** dentro de un lienzo vertical
(sin metadata de rotacion que lo delatara: 1080x1920 "correcto" con la escena tumbada);
se enderezo con `transpose=2` y recorte 9:16 al 62% del ancho. Mirar la hoja de
contactos de la carpeta antes de elegir, no fiarse del nombre del archivo.

**Regla que no se salta:** la foto va donde el guion respalda lo que se ve. La de
`dante.jpg` (pinchando en una cabina) entra en `comentasocialing`, que dice *"mi cliente
Dante… lo llamaron para hacer un concierto como DJ"*. En `comenta3` el cliente es Daniel
y no hay foto suya: ahí no se pone ninguna.

## 6q. TalkingHeadEditorial, el estilo de Fresco, medido en seis reels

`editorial`. Referencias en `referencias/editorial/fresco*.mp4`
(6 reels, 720×1280, 67-81s), medidas el 4-sep-2026 con seis lentes (gancho,
subtítulos, gráficos, ritmo, audio, guion) sobre fotogramas a 10 y 30 fps, escaladas
a 1080×1920. Huella mediana en `huellas/ref_editorial_media.json`.

### El gancho (0 a 3s), lo que más importa

| t | qué pasa | medida |
|---|---|---|
| 0.00 | **Primer plano** de la cara (2-4×) con la **primera línea del título YA escrita** | 5 de 6; `arranque.modo zoom_out`, `foco auto` (bin/foco.py) |
| 0.00-0.17 | **Zoom out continuo** de 4-6 frames hasta el plano medio, sin corte | `escala 2.4`, `duracion 0.17`, ease in-out |
| 0.20-0.30 y 0.37-0.43 | (ejemplos, ejemplos) **doble flash** de silueta blanca | `primer_frame.destello_doble` en el beats |
| 0.4-0.8 | entra la **línea 2, fina** (Montserrat 300), **en seco** | 1 frame, sin fade ni pop |
| 1.0-1.3 | entra la **línea 3, negrita** (3 de 6) | seco |
| 1.75-2.4 | el bloque se **sustituye en seco** por un segundo bloque centrado (3 de 6), o se retira (2.8-3.3s) | `bloques[].at` |
| 1.1-1.5 | primer subtítulo abajo, si la frase sigue | las palabras del título NO se repiten abajo (`bin/gancho.py` las quita) |
| ~5-6 | **corte que cierra el gancho**: riser de 1-1.7s que sube y se corta en seco, y **entra la música** | `audio.musica_desde fin_gancho` |

**El título es transcripción literal** de las primeras 2-5 palabras (verificar.py lo
comprueba línea a línea y juntas): línea 1 = el arranque condicional en negrita ("Si
tienes", "Si estás", "Si crees que", "Estas son"), línea 2 = el complemento en fina (el
diagnóstico, la edad, "comprando"), línea 3 opcional en negrita con el sustantivo
fuerte. Condensaciones permitidas: cifras ("tres"→"3", "mayores de 40"→"+40",
"dólares"→"USD"), marca→logotipo (`ln.img`), diagnóstico en Title Case. Cada línea entra
cuando empieza a decirse (gancho.py fija los `at` por el transcript).

**Tipografía del título:** Montserrat ExtraBold 800 (negrita) y Light 300 (fina),
tracking -0.08em, **blanco plano sin sombra** (medido: luminancia a 2-4px del glifo =
fondo). Negrita 116px (141 cuando va sola y grande), fina 118px, tercera línea 110px;
paso entre líneas ~105-114px (`interlinea 0.92`); centro de la línea 1 al 18-20%
(`y 15.2%`). Composición **centrada** (ejemplos, ejemplos) o en **escalera** (`alinear:
"escalera"`: línea 1 anclada a la izquierda al 9% y las siguientes con el borde derecho
a ras). Los dígitos de una línea fina van un 22% más grandes que su palabra ("las 3",
"+40").

**Sonido del gancho: ninguno.** Voz mono desnuda; sin whoosh en el 0, sin clicks por
palabra, sin acentos amarillos. Lo que engancha es el zoom out + el título + el flash.

### El cuerpo

- **Subtítulos:** Inter 600, 78px (tinta medida 68-81px), tracking -0.02em, blanco con
  halo oscuro difuso sin offset (`0 0 14px rgba(0,0,0,.6)`), una línea, 1-7 palabras
  (mediana 3), 0.8s por cue, **entran y salen en seco**. Centro al **63%** (bajo la
  barbilla, 6/6), o al **25%** sobre la cabeza cuando no hay título (fresco, ejemplos,
  ejemplos: `y_alto`), y al **68%** mientras hay un título de lista (`y_con_rotulo`).
  Terminan en la palabra clave (`corta_subtitulos`).
- **Ritmo:** cámara en trípode y TODO el movimiento en post. 18-27 cortes/min (mediana
  1.8-2.8s entre cortes, nunca >6s), **punch zoom instantáneo de +10%** al entrar y
  vuelta a base al salir, alternando; dentro del clip **deriva de +3-5%/s** que se
  suelta en el corte siguiente; punch "hero" de +20% en el título de sección y en el
  CTA (`estimulos.punch_en_cortes`). Se cortan TODOS los silencios (`pausa_max 0.40`).
- **Ficha de color** (ejemplos, 6 veces = 20%): oliva `#626A2D` exacto, Playfair Display
  Italic 600 blanca, tracking -0.09em, interlínea 0.88, tamaños **alternados**
  grande/normal por línea (170/118px), centradas al 52%. Entra y sale en **corte
  seco**, ~0.1s vacía, y las líneas se construyen al ritmo de las palabras: cada una
  **sube 130px con fade de 0.27s**. Esconde el subtítulo. Son literales: el veredicto
  del gancho, la tesis ("es porque…"), la lista de negaciones, el término técnico, el
  resultado de la prueba. `{"tipo":"color","lineas":[...]}`.
- **Título de lista** (fresco): "1- Proteína" en Poppins Bold 700 amarillo `#F6E040`,
  120px (cap 86), centro al 23%, halo oscuro de 36px, Title Case, seco, dura el punto
  entero. `rotulos[]` con `num` y `txt`.
- **Foto de testimonio** (fresco): recorte PNG de la marca sin fondo sobre su plano,
  cara difuminada, fundido de 0.3s. `props` tipo recorte.
- **B-roll:** solo 1 de 6 (ejemplos, 7 planos seguidos de stock médico a sangre). No es
  parte del estilo; se permite.
- **CTA** (6/6): "Comenta" en Inter 600 blanco (100px) y debajo la palabra en
  **MAYÚSCULAS, amarilla `#F2DA3D`, entre comillas**, Poppins Bold 700 (135px), sin
  caja, halo oscuro suave; entra **en seco** y se queda hasta el último frame. Dos
  sitios: **arriba** (centros 21%/27%: fresco, ejemplos, ejemplos) o **abajo** sobre la zona
  del subtítulo (58%/66%, palabra más grande: ejemplos, ejemplos, ejemplos), `cta.posicion`
  en el beats.
- **Audio:** música **solo desde el corte que cierra el gancho**, sin fade-out, ~-17 dB
  bajo la voz; cama lo-fi/chill con bajo sostenido y pulso débil (~115 BPM en la
  referencia; en la biblioteca la más parecida es `ALEGRIA/good-night-160166`, sin
  voz). Único SFX del cuerpo: **tick doble** (dos transitorios a 80ms) en cada corte.
  Sin obturador, sin boom, sin whoosh de zoom. Voz a -14 LUFS (normalización de IG).
- **Reparto:** la cara manda (gráficos 7-30% salvo el formato lista).

### Lo que cambió al montar el primer vídeo real (5-sep-2026)

La primera demo fue sobre un vídeo oscuro, y no se parecía en nada: el
estilo hay que juzgarlo sobre material parecido. Un vídeo del mismo set que los
ejemplos (pañuelo coral, sofá) sirvió para la comparación
fotograma a fotograma. Cuatro cosas se corrigieron con esa comparación:

- **Flash de silueta real**: el doble flash pinta al sujeto en blanco con bloom y deja
  el fondo visible. Se recorta al sujeto con `matte.py` en 0.15-0.50s (12 fotogramas,
  `props/silueta.webm`) y la plantilla lo pasa por `brightness(0) invert(1)` +
  `drop-shadow` blanco, más un velo del 28% a pantalla completa. Antes era un lavado
  blanco entero, que no es lo que hace la referencia.
- **Escala del primer plano según la fuente**: `foco.py` mide el ancho de la cara; si ya
  ocupa más de un tercio del ancho (fuente cerrada), abre desde 1.6-1.8× en vez de 2×.
  A 2.4× la cabeza quedaba fuera.
- **Itálica** (ejemplos): prefijo en la línea del subtítulo (63%) y la palabra en Playfair
  Italic de 126px colgando debajo (centro ~69%), subiendo 225px con fade. Se declaran
  en `beats.italicas [{prefijo, palabra}]` y se colocan donde se dicen.
- **CTA abajo** medido en ejemplos: "Comenta" 115px con el borde superior al 56.5%
  y la palabra a 200px (tinta 143-161px), antes quedaba al 74% y pequeño.

Y una regla del troceado: un cue que pisa la ventana de un título o una itálica **se
parte** con los tiempos de palabra (se conserva lo que queda fuera), no se tira. Tirarlo
entero perdía "meta estética" por una itálica que empezaba medio segundo después.

### Reglas del usuario tras ver el primer montaje (5-sep-2026)

- **"No hay motion graphics en este estilo de edición. A lo mucho b-rolls."** Fuera las
  fichas de color (aunque ejemplos las lleve): el estilo es título del gancho + subtítulos
  (con itálicas) + CTA, y **unos pocos b-rolls a sangre** donde el guion nombra algo
  concreto (`{"tipo":"broll","frase":"...","media":"fresco/x.mp4"}`, colocados por la
  frase; dos seguidos que se pisan van contiguos, como la secuencia de ejemplos).
  `ficha_color` queda como capacidad de la plantilla, no del estilo.
- **"Los zooms son solo de acercar y alejar, no tantos ni tan de pronto; el zoom va en
  cada corte, no porque sí; si el clip es muy largo, un zoom in o zoom out muy lento."**
  `bin/zoomcortes.py` decide en un solo sitio (plantilla y tick de sfx comparten la
  lista): el encuadre cambia EN un corte entre base (1.00) y cerrado (1.08), solo si han
  pasado ≥3.5s desde el último cambio (los cortes de en medio quedan como jump cuts
  limpios); un clip de ≥4s deriva MUY despacio (1.5%/s) hacia el otro encuadre; los
  cortos no se mueven. El tick doble suena solo donde cambia el encuadre. En ese vídeo:
  23 cambios en 58 cortes.

### Ajustes por vídeo (10-sep-2026, `hormonas`, selfie en exterior)

- **La altura del subtítulo se decide por vídeo** según dónde queda la cara:
  `beats.subtitulo.y`. Con la cara en la mitad baja del cuadro (selfie), el subtítulo va
  sobre la cabeza (28%) y el CTA arriba, como en fresco/ejemplos; con la cabeza arriba,
  bajo la barbilla (63%). `revisar.py` mira la franja que diga el beats.
- **Sombra del título por vídeo:** `beats.titulo_gancho.sombra`. La referencia va sin
  sombra sobre salones claros, pero sobre un cielo casi blanco el blanco plano no pasa el
  contraste (1.8:1) ni se lee; halo oscuro suave solo en ese vídeo.
- **Ninguna línea del título se sale del cuadro:** si una frase larga no cabe ("comer
  todavía menos" a 112px), la plantilla baja el cuerpo de ESA línea hasta que quepa.
- Un trozo de cue que sobra de una ventana del título puede caer dentro de la siguiente
  (pasó con "y sigues"): el recorte se repite hasta que ningún trozo pise ninguna
  ventana, y `reservar.py` ya no estira un cue por encima del título ni de una itálica
  (`ventanas.json`). Dos itálicas seguidas con el mismo prefijo ("más / ayunos", "más /
  restricciones") no son un cue duplicado.
- Fuentes 4K a 60 fps se bajan a 1080×1920 a 30 fps (lanczos, crf 16) antes de montar.

### Efectos: siempre de la biblioteca (10-sep-2026)

Regla del usuario: *"los sfx que uses los tomes de la carpeta de sfx cinemáticos y en
general de la carpeta edición"*. Nada sintetizado en este formato:

| efecto | archivo | por qué |
|---|---|---|
| cierre del gancho | `CINEMATICOS/Cinematic Whoosh Sounds effects No copyright.mp3` (0,9s antes de su pico, al 28%) | el riser de suspenso sonaba "de más"; un whoosh corto y bajo que aterriza en el corte |
| cortes con cambio de encuadre | `SFX/Camera Shutter Sound Effect.mp3`, uno solo, al 32% | el pop-click de burbuja no quedaba; el obturador se lee como cambio de escena, limpio y suave |

Música: `musica_db -11` y `musica_vol 0.70`, a -17 dB no se oía; tiene que estar
"ligeramente ahí". `audio.tick_cortes.archivo` manda; el click sintético queda solo como
respaldo si falta el archivo.

### Tanda de cinco vídeos (10-sep-2026): lo que hizo falta

- **Gancho auditivo en el frame 0** (regla del usuario): whoosh de la biblioteca
  (`arranque.sfx_archivo`, `SFX/mixkit-cinematic-transition-wind-swoosh-1468.wav`) con el
  pico cayendo donde aterriza el zoom out (0,17s). Los tres ganchos a la vez: visual, de
  texto y auditivo.
- **Canción distinta por vídeo** (`beats.audio.pista`, ruta relativa a `AUDIOS/MUSICA`):
  good-night, once-in-paris, dramatic-life, weeknds, Dramamine; todas verificadas sin voz.
- **`bin/quitar.py <nombre> "a-b,c-d"`**: quita retomas y equivocaciones del vídeo ya
  cortado ("te voy a repetir esa parte", el segundo gancho grabado, la última palabra
  repetida) y deja al día vídeo, transcript por palabra y `cortes.json`. Sin volver a
  transcribir.
- **Listas**: los rótulos se colocan por su texto literal y duran hasta el siguiente
  (`hasta` para el último); con la cara abajo suben al 8% (`beats.rotulo.y`) y el
  subtítulo se queda arriba (`y_con_rotulo`). Caben en dos renglones como mucho.
- **Cielo casi blanco**: `beats.rotulo.fondo` (pastilla oscura suave) y `beats.subtitulo.halo`
  más fuerte, solo en el vídeo que lo necesite; el amarillo daba 1.03:1 de contraste.
- La reserva de b-roll puede ser varias carpetas (`broll.carpetas`: `fresco/` y `dubai/`).

### Reglas del usuario tras la tanda (10-sep-2026, tarde), valen para TODOS los vídeos de Fresco

- **Subtítulos SIEMPRE debajo de la cabeza**, sin tapar boca ni barbilla, dentro del área
  de respeto (nunca arriba). `subtitulo.y: "auto"` → `bin/barbilla.py` detecta la cara con
  OpenCV (uvx, `opencv-python-headless<5`) y el centro va a barbilla + 6% con techo en 80%.
  Medido: 76-78% en los selfies de exterior. `hormonas` fue la excepción aprobada (arriba).
- **Rótulos de lista en la zona del gancho** (15%, nunca más arriba), **Title Case**
  ("2- No Elimines las Grasas"), **sin pastilla**. El número que dice ("Número 5",
  "Tercero", "2.") **no sale en el subtítulo**: `rotulos[].dicho` lo quita y solo cambia
  el rótulo. Los audits lo exceptúan.
- **Gancho y subtítulos no conviven**: el último bloque del título se va en cuanto acaba
  su última palabra, y ahí arrancan los subtítulos.
- **Máximo 3 palabras / 20 caracteres** por subtítulo.
- **La voz salía saturada**: no era el corte (-15,7 LUFS, sin recorte) sino la MEZCLA del
  render (voz 1.0 + música 0.7 + sfx 0.4 sin limitador: pico 1.21, -12.7 LUFS, LRA 2.8).
  Ahora voz 0.75 / música 0.50 / sfx 0.30 en la composición y `bin/entregar.sh`
  masteriza el render con loudnorm a -16 LUFS / -1.5 dBTP antes de revisar y copiar.

### Piezas nuevas de la plantilla (4-sep-2026)

`#gancho` (título apilado con `BEATS.gancho.bloques`), `arranque.modo zoom_out` con
`foco` y `destello_doble`, `stinger.color` (ficha de color con líneas), `#clave.comenta`
(CTA en dos líneas, posición arriba/abajo), `rotulo` con color/caso/fuente/sombra y
`subtitulo.y_con_rotulo`, `estimulos.punch_en_cortes`, `bin/gancho.py` (tiempos del
título por el habla y quita los cues repetidos), `bin/foco.py` (dónde está la cara),
`musica.py` con `MUSICA_DESDE`/`MUSICA_FADE_OUT`, `sfx.py` con `riser` y `tick_cortes`.
Fuentes añadidas: Montserrat variable, Poppins 300-800, Cormorant Garamond itálica.

### Cómo se monta un vídeo de Fresco

```
bin/cortar.sh input/caroX.mp4                  # FORMATO=editorial
input/caroX_beats.json:
  "gancho": {"bloques": [ {"alinear":"escalera","lineas":[{"t":"Si tienes","peso":"negrita"},
                                                          {"t":"Ovario Poliquístico","peso":"fina"}]} ]},
  "primer_frame": {"destello_doble": true},     # opcional
  "stingers": [ {"at": 3.3, "dur": 1.9, "tipo": "color", "lineas": ["tus hormonas","están","en alerta roja"]} ],
  "rotulos":  [ {"at": 15.4, "dur": 5.6, "num": "1", "txt": "Proteína"} ],
  "cta": {"posicion": "arriba"}
FORMATO=editorial bin/montar.sh input/caroX_cut.mp4 output/caroX_cues.json caroX input/caroX_beats.json "" input/caroX.json
```

## 6k. El loop: acercar el formato a la referencia hasta que la rúbrica lo dé por bueno

Cuatro piezas, todas en `bin/`:

**`huella.py video.mp4`**, mide el FORMATO de un vídeo en números comparables: dónde vive
el subtítulo y cuánto mide una línea, si hay titular fijo arriba, el color del acento
(solo dentro de líneas de texto, para no confundirlo con la piel), las barras del
marco, cortes por minuto, fracción de fichas claras, cobertura de texto, si el CTA se
queda al final, y cuánto zoom. Trabaja a 1080×1920 y 4 fotogramas por segundo. Una
"línea" es una banda ancha y baja (ancho/alto ≥ 2,2, de 14 a 220 px) que no llena más
de la mitad de su fila, así una lámina o una foto no cuenta como texto.

**`rubrica.py ref.json nuestro.json`**, puntúa de 0 a 100 propiedad a propiedad, con
pesos: lo que más pesa es dónde está el texto, cuánto mide, y el ritmo. **Lo que el
usuario ha decidido distinto de la referencia** (amarillo en vez de rojo, subtítulos
abajo en Top 10, sin b-roll en reflexivo) se declara en el formato como
`rubrica_fijado` y puntúa como cumplido: no es un defecto y no se persigue.

**`loop.py <nombre> <formato> <ref.json>`**, monta, renderiza en borrador, mide, puntúa,
y si no llega a la meta (98) mueve los parámetros del formato hacia la referencia
, solo los que son formato: posición y cuerpo del texto, palabras por pareja, zoom,
barras del marco, y vuelve a empezar. El **orquestador** es la regla de parada: meta,
estancamiento (dos vueltas sin subir) o tope de vueltas. Lo que no puede ajustar solo
porque es contenido (cuántos cortes, cuántas fichas, el titular) lo deja en el log
como tarea manual con el número al que hay que llegar. Log en `huellas/loop_<nombre>.log`.
La receta del montaje va en `input/<nombre>_receta.json`.

**Cuerpos 83/108, fijados.** El loop los subió a 86/111 persiguiendo a la referencia y
el editor lo vio demasiado grande en el móvil. Es su decisión (`rubrica_fijado`
incluye `texto.alto_px`), así que el loop ya no los toca.

**Lo que la nota mide y lo que no.** Un 98 significa *mismo formato*, no *mismo vídeo*:
distinta persona, distinto guion y distintos planos no se miden ni pueden medirse.

**`buscar_imagen.py buscar "<tema>"`**, cuando la biblioteca no tiene lo que pide una
escena. Tres vías por orden: la API de Pexels (con `PEXELS_API_KEY`: limpia, sin
crédito), el scraper de Pexels con Brave sin ventana (Cloudflare lo para en casi todas
las URL nuevas), y Openverse (sin clave, pero ~1024 px y licencia CC-BY: hay que dar
crédito, y la calidad es Flickr, no stock). Baja candidatas y monta una hoja de
contactos: las imágenes se eligen **mirándolas**. `elegir` normaliza las escogidas a
lámina 3:2, prop, o fotograma vertical.

**B-roll nuevo de Mixkit (14-sep-2026).** La reserva `input/broll/romance` se agotó: los 27
clips ya habían salido. Sin `PEXELS_API_KEY` y con Cloudflare frenando el scraper, la vía
que funciona sin clave es Mixkit: las páginas `mixkit.co/free-stock-video/<tema>/` listan
ids, y el archivo se baja de `assets.mixkit.co/videos/<id>/<id>-2160.mp4` (también
`-1080`/`-720`). Dos gotchas: (1) cada clip lleva licencia **Free** o **Restricted**
(`data-license="videoFree"` en su página): usar SOLO los Free; (2) los ids nuevos (100xxx)
devuelven 403 a la descarga directa. Son horizontales: se recortan a 9:16 SOBRE EL
SUJETO (`crop=ih*9/16:ih:(iw-ih*9/16)*x`, con x mirado en la miniatura) desde el 4K,
6s, h264 bt709, y se guardan como `romance/mk_<escena>.mp4`. Mirar los recortes en hoja
de contactos: al centro ciego salió la espalda de ella en vez de su cara.

**CTA con palabras pegadas detras (15-sep-2026, `divierte`).** Si la pareja del CTA era
"divierte y te", `pares.py` la recortaba a "divierte" y TIRABA "y te" sin marcarlas: la
auditoria las daba por perdidas. Ahora lo que sobra pasa a una pareja propia `tras_cta`
(no se dibuja y se exime). Tambien: fichas por `frase` ignoran `dur`/`hold`; si pisan el
b-roll siguiente, quitarlas o moverlas, no acortarlas.

**Clips duplicados con dos nombres (22-sep-2026, `guion2`).** `dubai/db_cansancio_cama.mp4`
y `fresco/cr_desvelo_cama.mp4` son EL MISMO archivo (mismo md5) en las dos carpetas de
reserva de Fresco. El registro mira nombres, no contenido, asi que dejo pasar el mismo
plano dos veces en un mismo video. Antes de elegir dos clips parecidos de carpetas
distintas: `md5 -q a.mp4 b.mp4`.

**`registro.py`**, el b-roll no se repite: máximo 25% compartido con el vídeo anterior
y dos vídeos de distancia para volver a usar un clip. Y tiene que ser del tema del
formato (`broll.tema`). Es puerta del montaje.

## 7. La banda útil (los 4 sextos centrales)

La pantalla en 6 partes: **16.7%–83.3%** es lo que la gente ve. Arriba está la lupa de
IG/TikTok, abajo el nombre y la descripción del creador. **Ninguna pieza gráfica lleva
su masa fuera de esa banda.** Verificado por medición en cada composición.

---

## 8. Audio

| Medida | Valor | Origen |
|---|---|---|
| Loudness objetivo | -15 LUFS | medido en la referencia |
| Silencios reales | **cero** | medido: nunca hay aire muerto |
| Volumen SFX | 0.55 | - |
| Música | -16 dB, ducking -9 dB bajo la voz | - |

- **Click solo en las palabras de las frases animadas.** Nunca en el subtítulo normal:
  si sonara en cada cue dejaría de marcar lo importante. Verificable por conteo: los
  clicks de la pista == las palabras de las frases animadas.
- **Corte seco** (transitorio de 90ms tipo empalme) al entrar el b-roll **y al volver**.
- Paleta por tipo de gráfico, para que no entren todos con el mismo golpe:
  `pulso/anillos` marea+subdrop · `alerta` glitch+impacto · `cifra/icono` reversa+brillo
  · `flecha/orbe` marea+brillo · `barras/malla` reversa+impacto · `ondas` reversa+subdrop.
- **`marea` sustituye al riser.** Un barrido de ruido subiendo llama la atención sobre
  sí mismo: es lenguaje de tráiler, no de cine. `marea` es un swell de graves (52 y
  78 Hz) que se apoya en la cola de sala, no en el volumen.
- Música: cama sin melodía. Si se puede tararear, compite con lo que dices.

---

## 8b. La triple revisión (obligatoria)

Los subtítulos han fallado de cuatro maneras: **palabras repetidas, cues duplicados,
texto que no aparece cuando se dice, y bloques solapados**. Revisar a ojo no las caza.

`bin/revisar.py` hace tres pasadas en tres niveles distintos, porque cada fallo se ve
en un sitio distinto, el dato puede estar bien y la plantilla no dibujarlo:

| Nivel | Qué mira |
|---|---|
| 1 DATOS | duplicados, solapes, repeticiones cercanas, palabras ausentes |
| 2 COMPOSICIÓN | `hyperframes check`: lo que Chrome monta de verdad |
| 3 RENDER | muestrea frames del mp4 y comprueba que hay texto cuando toca |

Criterio de repetición: **dos palabras de contenido en común dentro de 4 segundos**.
Con menos, marcaba "en la" o "tienes que" como fallo, y contaba como duplicado un
"mismo" que el hablante repite de verdad.

## 9. Cómo se resuelven los conflictos

Cuando dos cosas quieren el mismo espacio o el mismo momento:

1. **Gráfico > frase animada.** Si se solapan, la frase se descarta y el montaje avisa.
2. **Subtítulo en su sitio > frase animada larga.** Si un bloque va a comerse un
   subtítulo, se **acorta el bloque** (nunca por debajo de su última palabra + 0.30s).
   Mover palabras a un cue posterior las saca de sincronía: se leen después de oírse.
3. **La palabra del gráfico no se gasta antes** (`bin/reservar.py`): si un gráfico va a
   mostrarla, se borra de los subtítulos anteriores. Debe aparecer por primera vez ahí.
4. Si al recortar queda algo colgando en preposición o artículo, se recorta más.

**Señal importante:** que el sistema tenga que acortar o rescatar algo suele significar
que **la frase elegida está mal escrita**, no que haya que ajustar tiempos. Las frases
animadas tienen que ser ideas completas ("ni de qué conversar **con ellos**", no "ni de
qué conversar").

---

## 10. Pipeline completo

```bash
cd editor-de-video/referencia

# 1. corte + retomas + transcript por palabra
bash bin/cortar.sh input/video.mp4

# 2. subtítulos
bash bin/py bin/cues.py input/video.json > output/cues.json

# 3. autoría: beats.json (gráficos) y keywords.json (frases animadas)
#    -> citas literales del transcript, ideas completas

# 4. montaje: compone el texto de los gráficos, alinea, encaja, reserva, cuadra,
#    fija la palabra clave, genera SFX y música, y pasa las TRES puertas
bash bin/montar.sh input/video_cut.mp4 output/cues.json <nombre> \
     output/beats.json output/keywords.json input/video.json

# 5. render y revisión final sobre el vídeo ya renderizado
cd output/<nombre> && npx hyperframes render --workers 4 -o final.mp4
cd ../.. && bash bin/py bin/revisar.py output/<nombre> input/video.json output/<nombre>/final.mp4
```

Las **tres puertas** abortan el montaje si algo falla: `hyperframes check` (que la
composición se ejecute), `bin/auditar.py` (contenido) y `bin/revisar.py` (triple
revisión). La tercera se repite tras el render para cubrir su nivel 3.

`FORMATO=talkinghead` es el valor por defecto; otro formato usa `FORMATO=<otro>`.

### Qué hace cada script
| Script | Función |
|---|---|
| `cortar.sh` | silencios fuera, retomas fuera, transcript por palabra |
| `retomas.py` | decide si un fragmento corto es retoma (descartar) o hipo (fusionar) |
| `cues.py` | transcript → cues sin frases a medias, continuos, sin puntos |
| `alinear.py` | mueve cada gráfico al instante en que se dice su frase |
| `encajar.py` | alarga el gráfico hasta el corte de A-roll que tiene detrás |
| `reservar.py` | quita de los subtítulos lo que va a mostrar el gráfico |
| `kw.py` | timing por palabra de las frases animadas |
| `cuadrar.py` | resuelve subtítulos contra bloques (acorta antes que mover) |
| `estimulos.py` | audita la regla de 3s y rellena con zooms |
| `iconos.py` | incrusta solo los iconos usados |
| `sfx.py` / `musica.py` | pistas de audio sintetizadas |
| `estilo.py` | `formatos/<formato>.json` → variables CSS del proyecto |
| `verificar.py` | aborta si hay texto inventado |
| `auditar.py` | aborta si se pierde una palabra o un gráfico va desfasado |
| `densidad.py` | avisa si hay demasiados gráficos por minuto |
| `corregir.py` | arregla palabras mal transcritas SIN mover los tiempos |
| `escena.sh` | trozo de película (o de cualquier fuente) → b-roll vertical a sangre |
| `palabraclave.py` | detecta la palabra del CTA y la fija hasta el final |
| `revisar.py` | triple revisión de subtítulos (datos, composición, render) |
| `cadencia.py` | cierra los silencios que deja el corte, con umbral relativo a su voz |
| `compas.py` | tempo, golpes y dónde arranca la canción |
| `ritmo.py` | empuja los zooms al golpe, solo si queda a un pelo |
| `remapear.py` | traslada b-roll y gráficos de un corte a otro, y resuelve solapes |

---

## 11. Esquemas de autoría

### beats.json
```json
{"stingers": [
  {"at": 3.0, "dur": 1.2, "tipo": "icono", "icono": "brain",
   "icono_pos": "arriba", "icono_comp": "duo", "tono": "negro",
   "titular": "cita literal del transcript",
   "acento": "nucleo", "acomodo": ["izq","izq","der"], "pos": "medio"}
], "listas": []}
```
`at` es una pista (se realinea al habla). `icono_comp`, `acento`, `acomodo` y `pos` son
opcionales: si no están, rotan o se deducen.

### keywords.json
```json
[{"at": 0.0, "dur": 1.3, "text": "cita literal", "acento": "nucleo",
  "bloque": [["cita","chica"],["literal","grande"]], "cuerpo": 130}]
```
`bloque` fuerza el reparto en registros; `cuerpo` fuerza el tamaño.

---

## 11b. Estado del entorno (verificado)

| Pieza | Estado |
|---|---|
| hyperframes CLI | 0.7.110 via `npx hyperframes` (el paquete local del repo no esta buildeado) |
| ffmpeg / ffprobe | 8.1 en `/opt/homebrew/bin`, usar siempre la ruta completa |
| Chrome de render | cacheado, GPU y fast-capture activos |
| Transcriptor | `bin/transcriptor.py` elige el motor: mlx-whisper (chip Apple) o faster-whisper (los demás), los dos dentro de `.venv` |
| Windows | todo corre en Git Bash; `bin/entorno.sh` da rutas `C:/...`, UTF-8 y salida de Python sin `\r` |
| Fuentes | en `plantilla/fuentes/`: Inter variable (100-900) + Playfair Display Italic |
| Iconos | en `plantilla/iconos/`: Lucide 1.31.0, ISC, ~2000 SVG de trazo |
| Docker | no instalado, solo hace falta para renders deterministas entre maquinas |
| whisper-cpp | no instalado, no hace falta: mlx-whisper en chip Apple y faster-whisper en los demas |

---

## 12. Errores ya cometidos (para no repetirlos)

- Un reemplazo de texto que **no encuentra su objetivo falla en silencio** y el cambio
  nunca se aplica. Pasó dos veces (la animación de los subtítulos y los puntos).
  Verificar el resultado, no dar por hecha la edición.
- Una constante usada antes de declararse (zona muerta temporal) **no la detecta una
  comprobación de sintaxis**: el vídeo renderiza sin errores y sale sin subtítulos. Por
  eso `hyperframes check` es obligatorio.
- En CSS, `inset` después de `top/bottom` los anula, y una regla posterior con `inset:0`
  gana. Las piezas se salían de la banda y a ojo no se veía.
- Elegir composición por hash del instante hace que dos elementos coincidan por
  casualidad. Usar contador de orden.
- Un guardián mal medido (porcentaje sobre el número de frases en vez de sobre el texto
  total) dejó el color de acento prácticamente sin usar.
- Fusionar un fragmento corto sin mirar qué dice conserva tomas rotas.
- **Normalizar para comparar quita los acentos**, y "él" (pronombre) se volvía "el"
  (artículo): la regla de palabras colgantes se lo comía. Perdía palabras del guion.
- `grupos[-2] += grupos.pop()` en Python resuelve el índice **después** del pop, así
  que escribe en el elemento equivocado: duplicaba el último cue y perdía el anterior.
- Un umbral **absoluto** de silencio sobre material grabado bajo corta dentro de las
  palabras. Normalizar antes de analizar.
- Un segundo `-af` en ffmpeg **sobreescribe** al primero: el filtro de limpieza borró
  el que cortaba el audio y quedó desincronizado 20 segundos.
- Rescatar palabras hacia un cue posterior las saca de sincronía: se leen después de
  oírse. Mejor acortar el bloque que mover el texto.
- Un tamaño "con tope" sigue siendo proporcional: cuando el cuerpo grande bajaba del
  tope, la palabra pequeña encogía con él y quedaba distinta en cada bloque. Los
  registros chico y serif son **fijos** (56px y 84px).
- Un bloque de código borrado en una reescritura no avisa: el que guardaba las frases
  ya acortadas desapareció y el render siguió usando la duración vieja durante varias
  versiones.
- Elegir material de prueba parecido al original hace indistinguible el acierto del
  fallo. Pasó dos veces con b-rolls del mismo creador.
- **ffmpeg lee de la entrada estándar y se come la lista** cuando se le llama dentro
  de un `while read`. Dos clips salieron de 30.6s y 81.4s en vez de 430.6 y 481.4: se
  había tragado el "4" del principio. Se arregla con `-nostdin`. (`ffprobe` no tiene
  esa opción, ahí no hace falta.)
- Un ejecutable de whisper por fragmento **recarga el modelo entero cada vez**. Con 22
  fragmentos cortos son 44 cargas de large-v3 para transcribir unos segundos de audio:
  más de diez minutos por vídeo. Importando el módulo, el modelo queda en memoria.
- `encajar.py` alargaba un gráfico hasta el corte **sin mirar al gráfico siguiente**:
  creaba él mismo un solape de 0.05s que después rechazaba `hyperframes check`. El
  solape no estaba en el JSON de entrada, lo inventaba el ajuste.
- El informe de estímulos medía huecos sobre tramos **sin fundir**: un zoom dentro de
  una frase animada partía el tramo en dos e inventaba un hueco de 3.42s donde el real
  era 2.80s. No había forma de arreglarlo porque no existía.
- Ajustar un zoom "al cue más cercano" puede empujarlo **más allá del límite** que se
  intenta respetar: quedaba un hueco real de 3.26s con el límite en 3.0.
- Un verbo suelto no basta para detectar el CTA: "pon proteína en todas tus comidas"
  fijaba "proteína" en pantalla desde el minuto 48. Hace falta el patrón completo
  `<verbo> la PALABRA x`, y si no aparece, el último verbo del tramo final.
- Cuando el bloque va DELANTE del subtítulo que dice lo mismo, las palabras se veían
  dos veces seguidas ("tus estrógenos" en el bloque y otra vez 0.2s después). Había que
  quitarlas también en ese sentido, pero **solo esas**: cortar el resto del cue se
  lleva por delante palabras que el bloque no dice.
- Un `for ... else` con `continue` dentro del `else` salta el resto del bucle exterior:
  al reescribir `reservar.py` así, 126 de 259 palabras dejaron de aparecer de golpe.
  Lo cazó la auditoría en el mismo montaje.
- **Medir los silencios por los tiempos de palabra de whisper NO vale**: alarga el
  final de cada palabra hasta bien entrado el silencio, así que un hueco real de 0.9s
  se mide como 0.2s. Por palabras se cerraban 5 huecos; midiendo energía, 46.
- Un umbral **absoluto** de silencio deja pasar 14 segundos de silencio en un vídeo de
  dos minutos y el corte parece limpio. El umbral tiene que ser relativo a la voz.
- Cortar todo lo que baje del umbral **se lleva las palabras dichas por lo bajo**: se
  perdió un "sí" de los 258 de un vídeo. Hay que respetar los repuntes de dentro.
- **Medir el ancho del bloque sobre el contenedor no vale**: lleva `max-width:100%`,
  así que su `scrollWidth` se queda clavado en el ancho de pantalla por larga que sea
  la frase. El bucle que baja el cuerpo creía que siempre cabía y las frases largas se
  salían del cuadro por los dos lados. Hay que medir sobre las FILAS.
- Las líneas chica y serif van a tamaño **fijo** a propósito, pero entonces no encogen
  con el resto: en una frase larga el bucle baja al mínimo, sigue sin caber, y la
  serifa acaba saliéndose. Se les aplica el recorte que haga falta, y solo entonces.
- **Un clip HDR se lleva por delante todo el render.** Dos b-rolls grabados en HLG
  con el iPhone hicieron que HyperFrames tratara el proyecto entero como HDR: el mp4
  salió en HEVC y los subtítulos quedaron POR DEBAJO del b-roll. `check` y `snapshot`
  pasaban; solo fallaba el archivo final. Costó encontrarlo porque de tres vídeos
  idénticos solo fallaba uno, el único con material del iPhone.
- Poner `-color_primaries`/`-color_trc`/`-colorspace` en la salida de ffmpeg **no
  reetiqueta nada**: los hereda del input. Hay que usar el filtro `setparams`.
- Una ventana de b-roll más larga que el propio clip lo deja **congelado en su último
  fotograma**. Pasaba en seis de veintiséis: los ajustes de encaje y de solape alargan
  la ventana sin mirar cuánto material hay.
- El orden del DOM **no decide quién pinta encima**: el b-roll estaba declarado antes
  que `#subs` y aun así los tapaba en los diez tramos del vídeo. Hay que fijar
  `z-index` a mano.
- Elegir dónde va el texto de memoria falla: hay que **medirlo con una regla de
  porcentajes sobre un fotograma real** de cada cliente. El 62% que funcionaba en un
  encuadre le cruzaba la cara en otro.
- Volver a cortar un vídeo mueve todo lo que venía detrás. Las frases animadas se
  recolocan solas (se buscan por su texto), pero **el b-roll no tiene texto** y se
  queda en el sitio viejo. Y al comprimirse la línea de tiempo, dos piezas separadas
  pueden acabar solapadas, que es un error que aborta el render.
- Un efecto colocado más allá del final del vídeo **revienta** el generador de SFX en
  vez de ignorarse (`operands could not be broadcast together`).
- Ajustar los zooms solo al "uno" del compás deja fuera a casi todos: con compases de
  1.5s y una tolerancia de 0.13s, la probabilidad es de una entre seis.
- Elegir la escena de una película por un solo fotograma engaña: la mitad de los clips
  buenos en el primer frame terminaban en un plano borroso o con el sujeto ya fuera de
  cuadro. Hay que mirar tres momentos de cada clip ya cortado.
- Medir el texto **antes de que cargue la fuente** da anchos de la tipografía de
  reserva, que es más estrecha: el ajuste creía que cabía y luego, ya con Inter, el
  renglón se salía por el borde o se partía en dos. El ajuste se hace dos veces, la
  segunda en `document.fonts.ready`.
- `#subs` ya viene metido por el margen de seguridad. Volver a restarlo dentro
  (`max-width: calc(100% - 2 * var(--safe-x))`) achica la caja un 8% más de lo que
  cree el JS: el texto se partía aunque el código midiera que entraba.
- Encoger las dos líneas **a la vez** castiga a la entradilla por lo largo que sea el
  renglón de abajo, y sale mucho más chica que en las referencias. Cada una se ajusta
  por su cuenta, con un techo para no perder la jerarquía.
- Elegir la palabra en rojo **después** de cortar las líneas la deja a merced de dónde
  cayó el corte: la palabra fuerte del vídeo ("mierrrrda") se quedaba en la entradilla,
  en blanco. Se elige antes de cortar y se fuerza su renglón.
- Las dos líneas del subtítulo se leían como dos cosas sueltas porque el hueco entre
  ellas medía **el 120% del alto de la letra**; en las referencias mide el **20%**. El
  interlineado normal no basta: hace falta subir la línea grande con un margen
  negativo.
- Un `width` en `em` se resuelve contra el cuerpo del **propio** elemento, no contra el
  del padre. El avatar de las notificaciones se quedó a un cuarto de fila, colgando
  fuera de la pastilla.
- Las capturas se dibujan con `em`, y `em` cuelga del cuerpo que herede la caja, el
  del documento, 16px. Salían ilegibles (tres puntitos grises donde tenía que leerse un
  mensaje) hasta fijar el cuerpo por JS a partir del alto real de la tarjeta.
- La segmentación sobre **metraje de ambiente** (luces, texturas, planos generales) no
  encuentra qué recortar: devuelve un borrón. Los props salen de material con un sujeto
  claro, no de b-roll atmosférico.
- `getBoundingClientRect()` devuelve el tamaño **en pantalla**, ya escalado por el
  visor; GSAP anima en píxeles de la composición. Calcular un desplazamiento con el
  rect lo deja encogido a una fracción: la palabra del CTA se apartaba de lado pero no
  subía. El tamaño sale de `data-width` / `data-height` del elemento raíz.
- **Dos animaciones a la vez sobre el mismo elemento se pisan.** Cada una escribe la
  transformación entera desde su propio estado de partida, y al renderizar por saltos
  de fotograma una borra a la otra. Un movimiento en arco va en UNA animación con dos
  tramos (`keyframes`), no en dos animaciones simultáneas.
- Un `padding` en **porcentaje se calcula sobre el ancho**, no sobre el alto. Puesto
  como `padding-top: 72%` para colocar la imagen del recurso, acababa al 40% de altura
  y diminuta. Las posiciones verticales van con `top`, que sí va sobre el alto.
- Medir "texto negro" con `max(RGB) < 70` sobre una ficha con emoji **cuenta las
  sombras del emoji** como texto. Los números decían que el texto pisaba al cerebro
  cuando en el fotograma había aire de sobra. Antes de corregir por un número, mirar el
  fotograma.
- El detector de acento con umbral `(mx-mn) > 90` **cuenta la piel** como acento: una
  cara da (206,120,101). El amarillo #FFDE21 da 222 de diferencia, el rojo 217, el
  ámbar 251: 130 separa limpio.
- Medir texto a 540×960 con hueco de 4 px **funde dos líneas en una**: la referencia
  daba "182 px de tinta" cuando eran dos líneas de 52 y 72. Se mide a tamaño real y por
  línea.
- Un módulo que ejecuta `main()` al importarse rompe a quien lo importa: `rubrica.py`
  hizo caer el loop. Siempre `if __name__ == "__main__"`.
- El scraper de Pexels "funcionaba" solo porque la primera URL quedó cacheada en el
  perfil de Brave: cada URL nueva recibe la verificación de Cloudflare, y en modo sin
  ventana no se resuelve ni esperando 25 s.
