---
name: editor-ia
description: >
  Edicion completa de videos hablados a camara, verticales 1080x1920 para Reels y TikTok,
  de Devia Consulting. Corta silencios y retomas, transcribe palabra por palabra,
  pone subtitulos sincronizados, frases animadas, motion graphics, efectos de sonido
  sintetizados y musica, y renderiza el video final. Tiene tres estilos (limpio,
  dinamico, reflexivo) y tres controles que abortan el montaje si se pierde, se repite o
  se solapa una palabra. Tambien arma videos a partir de clips generados con IA (Google
  Flow): los une, les quita el silencio, corrige el ritmo y los edita. Usalo cuando el
  usuario pida editar, montar, subtitular o renderizar un video de la carpeta input/,
  cambiar de estilo, o ajustar subtitulos, zooms, musica o efectos de un reel.
---

# Editor de video con IA · Devia Consulting

Hecho por Devia Consulting.

Todo pasa dentro de la carpeta del editor y funciona igual en Mac, Windows (Git Bash) y Linux.
Los scripts de Python se corren con `bash bin/py`, que usa el Python del editor en cualquier
equipo. No uses `python3` ni `source .venv/bin/activate`: en Windows no existen.

1. **Lee `docs/ESPECIFICACION.md`.** Tiene cada medida y cada regla con su porque. No
   improvises valores.
2. **El estilo manda.** Cada estilo es un archivo en `formatos/<estilo>.json` y los
   scripts lo leen con `bin/cfg.py`. Se elige con `FORMATO=<estilo>`. Si el usuario no
   dice cual, pregunta una vez y recomienda segun el contenido (tabla abajo).
3. **Musica solo de `musica/`.** Es opcional: sin cancion, `bin/musica.py` sintetiza una
   base propia con ducking bajo la voz. Pregunta una vez si quieren una cancion suya.

## Los estilos

| Estilo | Qué lleva | Uso |
|---|---|---|
| `limpio` | Cortes, subtitulos y efectos de sonido. Nada mas: sin frases animadas, sin graficos, sin b-roll y sin zooms; los cortes quedan como saltos. Si piden disimularlos, activa `estimulos.punch_en_cortes` (`activo: true`, `entra: 0.04`). | Cuando el mensaje se sostiene solo. |
| `dinamico` | Todo lo de limpio, mas b-roll, frases animadas y motion graphics. Un estimulo cada 3 s. | Anuncios y contenido de descubrimiento. Es el estilo por defecto. |
| `reflexivo` | Musica tranquila, cortes solo donde hacen falta, pausas cortas respetadas, subtitulo discreto. Sin zoom ni b-roll. | Historias, testimonios y mensajes personales. |

Lo que cada estilo permite colocar esta en `contenido` dentro de su archivo. Respetalo:
en `limpio` y `reflexivo`, `beats.json` va sin stingers, props ni b-roll, y
`keywords.json` vacio.

## Reglas que no se negocian

1. **Nada inventado.** Todo texto en pantalla es cita literal de lo que se dice.
2. **Todo lo que se dice, se ve, y a tiempo.** Ni una palabra fuera de su momento.
3. **Nada se da por hecho: se mide.** Tres controles abortan el montaje:
   `hyperframes check`, `bin/auditar.py` y `bin/revisar.py`. Si abortan, se corrige la
   causa, no se saltan.
4. **Que no pare de hablar.** Ningun silencio por encima de `cortes.pausa_max` del estilo.
   El corte por silencio no basta: lo cierra `bin/cadencia.py`.
5. **Los subtitulos son la capa mas alta.** Un solo clip HDR del iPhone manda el render
   por la rama HDR y los tapa. `bin/escena.sh` normaliza a bt709 y el render va con
   `--sdr`. Si el mp4 sale en HEVC, hay un clip HDR colado.
6. **El texto no tapa la cara.** La altura del subtitulo se mide sobre un fotograma real.

## Orden de trabajo

1) Limpiar la voz. 2) Elegir la musica. 3) Lo demas.

## Proceso

```bash
bash bin/cortar.sh input/<video>.mp4
bash bin/py bin/cues.py input/<video>.json > output/cues.json
# escribe output/beats.json y output/keywords.json: citas literales e ideas completas.
# la cancion va en beats.json como {"audio": {"pista": "<archivo de musica/>"}}
FORMATO=<estilo> bash bin/montar.sh input/<video>_cut.mp4 output/cues.json <nombre> \
    output/beats.json output/keywords.json input/<video>.json
FORMATO=<estilo> bash bin/entregar.sh <nombre> input/<video>.json salida/<nombre>.mp4
```

`entregar.sh` renderiza, masteriza el audio a volumen de plataforma y pasa la revision
final de subtitulos. El video queda en `salida/`.

## Al trabajar

- **Verifica en el render, no en el codigo.** Saca fotogramas con ffmpeg y miralos.
- **Si el montaje avisa de que acorto o rescato algo**, la frase escrita esta mal:
  arregla la frase, no los tiempos.
- **Los motion graphics se colocan a mano** y no pasan de 8 por minuto.
- **Las frases animadas terminan donde termina un subtitulo.** Si una frase acaba a mitad
  de un bloque, el resto se queda corto y se pierde una palabra.
- **Whisper se equivoca con terminos del sector.** Re-transcribe el tramo con un
  `initial_prompt` del tema (`bash bin/transcribir.sh <tramo> --initial-prompt "..."`) y
  corrige con `bin/corregir.py`, que no mueve los tiempos.
- **Al volver a cortar un video**, pasa el b-roll por `bin/remapear.py`.
- **B-roll solo propio o con licencia.** Nunca escenas de peliculas ni videos ajenos.
- **La musica, sin voz cantada.** Comprobarlo transcribiendo 45 s de la cancion: si
  salen palabras, tiene voz.
- **Nombres propios**: `subtitulo.propios` del estilo guarda las palabras que conservan
  su mayuscula (marca, institucion, carreras). Llenala por proyecto.

## Videos hechos con clips de IA (Google Flow)

Cuando el usuario trae varios clips generados (por ejemplo `input/enfermeria/clip-01.mp4`
a `clip-10.mp4`), antes del proceso normal:

1. **Unirlos en orden** en un solo video vertical 1080x1920, normalizado a bt709 con
   `bin/escena.sh` si alguno viene en HDR.
2. **Quitar el silencio del principio y del final de cada clip.** Los modelos dejan aire
   al final de cada frase. Entre clip y clip, nada de pausas de mas de `cortes.pausa_max`.
3. **Ritmo:** subir la velocidad a lo que pida el usuario (1.12 a 1.20) sin cambiar el
   tono: `setpts` para el video y `atempo` para el audio.
4. **Podcast (dos personas en clips alternos):** montaje con solape. Cada clip entra unos
   0.3 s antes de que termine el anterior: la imagen ya muestra al que va a contestar y la
   ultima palabra del otro se sigue oyendo encima. Sin transiciones.
5. **Rotulo fijo** arriba durante todo el video si el usuario lo pide: es el gancho de
   texto. No lo tapan los subtitulos ni la cabeza.
6. **Capa de realismo** si la piden: un poco menos de saturacion, un poco mas de
   contraste y grano fino (filtros `eq` y `noise` de ffmpeg), aplicada al video unido.
7. Despues, el proceso normal (`cortar.sh` con el video unido, cues, montaje y entrega).
   La transcripcion manda: si el clip dice algo distinto al guion, el subtitulo dice lo
   que se oye.

## Al cambiar un estilo

Cambia `formatos/<estilo>.json` y anota en `docs/ESPECIFICACION.md` el valor nuevo y el
porque. Ningun valor vive escrito a mano en el codigo.
