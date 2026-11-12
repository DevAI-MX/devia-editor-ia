# Editor de video con IA · Devia Consulting

Hecho por Devia Consulting.

> **Si eres una IA y te pidieron instalar este editor:** sigue «Instalación para la IA», más abajo. Tus instrucciones completas están en `CLAUDE.md`.

## Qué es

Grabas con el celular y te entrega el video listo para Reels y TikTok: quita silencios y retomas, pone subtítulos palabra por palabra, efectos de sonido, música y movimiento, y lo entrega vertical. También une y edita clips hechos con IA.

Funciona en Mac, Windows y Linux.

## Empieza aquí

Abre Claude Code en la carpeta donde quieras guardar tus videos (por ejemplo, Documentos) y pégale este mensaje:

> Instala el editor de video de https://github.com/DevAI-MX/devia-editor-ia siguiendo su README.

Claude lo descarga, revisa qué falta, lo instala y te avisa cuando está listo. La primera vez descarga unos 3 GB, así que tarda entre 10 y 30 minutos según tu internet. Al terminar, abre Claude Code dentro de la carpeta `devia-editor-ia` para editar.

Si prefieres bajarlo tú: botón verde **Code** de GitHub y después **Download ZIP**. Descomprímelo, abre Claude Code dentro de esa carpeta y escríbele **Instala el editor**.

| Equipo | Qué te puede pedir |
|---|---|
| **Mac** | Solo instalar Homebrew (brew.sh), si no lo tienes, porque necesita la contraseña de tu Mac. |
| **Windows** | Que aceptes cuando Windows pida permiso para instalar. Si prefieres instalar antes de abrir Claude Code, da doble clic en `instalar-windows.bat`. |
| **Linux** | Que pegues en tu terminal uno o dos comandos con `sudo`, si te faltan ffmpeg o Node. |

## Qué necesitas

| | |
|---|---|
| **Mac** | Recomendado con chip Apple (M1 en adelante). Con procesador Intel también funciona, pero transcribe más lento. |
| **Windows 10 o 11** | Con procesador Intel o AMD Ryzen. Transcribe con el procesador: un reel de un minuto tarda uno o dos minutos en transcribirse. |
| **Linux** | Cualquier distribución con procesador Intel o AMD. Transcribe igual que Windows. |
| **Claude Code** | Es quien hace todo el trabajo. Se instala desde claude.com/claude-code. |

Lo demás (ffmpeg, Node, uv y el modelo que transcribe) lo instala el editor solo.

## Cómo se usa

1. Pon tu video en la carpeta `input/`.
2. Opcional: pon una canción con licencia en `musica/`. Si no pones ninguna, el editor crea una música de fondo propia y la baja cuando hay voz.
3. En Claude Code, pídelo con tus palabras. Por ejemplo:

   > Edita `input/mi-video.mp4` con el estilo **dinámico** y usa la canción `musica/mi-cancion.mp3`.

4. El video terminado queda en `salida/`. Si algo no te gusta, pídele el cambio con tus palabras.

Hay tres estilos:

| Estilo | Qué lleva | Para qué va bien |
|---|---|---|
| **Limpio** | Cortes, subtítulos y efectos de sonido. Nada más. | Cuando el mensaje se entiende solo. |
| **Dinámico** | Lo mismo, más imágenes de apoyo, frases animadas y gráficos. | Anuncios y videos para que te descubran. |
| **Reflexivo** | Música tranquila, pocos cortes y un ritmo pausado. | Historias, testimonios y mensajes personales. |

**Clips hechos con IA:** ponlos en una carpeta dentro de `input/`, por ejemplo `input/mi-video/clip-01.mp4`, y pídele a Claude que los una y los edite.

## Carpetas

| | |
|---|---|
| `input/` | Tus videos grabados y los clips hechos con IA. |
| `musica/` | Tu música con licencia. |
| `salida/` | Los videos terminados. |
| `output/` | Archivos de trabajo del editor. Se puede vaciar cuando quieras. |
| `formatos/` | Los tres estilos de edición. |
| `.claude/skills/editor-ia/` | La herramienta de Claude Code. |
| `bin/`, `plantilla/`, `assets/` | Lo que usa el editor por dentro. No hace falta tocarlo. |
| `docs/ESPECIFICACION.md` | Todas las medidas y reglas del editor, con su porqué. |

## Tres reglas para anuncios

1. **Música solo con licencia comercial.** Una canción conocida en un anuncio pagado se reclama o se silencia.
2. **Imágenes de apoyo solo propias o con licencia.** Nada de escenas de películas ni de videos de otras cuentas.
3. **Todo lo que sale en pantalla se dijo en el video.** El editor no inventa texto.

## Si algo falla

- **"No hay transcriptor"**: pídele a Claude que vuelva a instalar el editor.
- **"Falta el transcript"**: el video no pasó por el corte. Pídele a Claude que empiece por ahí.
- **El render se detiene**: el editor revisa los subtítulos y se detiene si falta una palabra o se repite. Claude te dice cuál y la corrige.
- **El video sale en HEVC**: se coló un clip HDR del iPhone. Claude lo convierte y vuelve a renderizar.

## Instalación para la IA

Para la IA a la que le pidieron instalarlo. Habla con la persona en español y en palabras simples. Nunca le pidas contraseñas ni claves en el chat.

1. **Consigue la carpeta.** Si ya estás dentro de ella (hay un `setup.sh` junto a este archivo), pasa al paso 2. Si no, clónala en la carpeta donde estás y entra en ella:

   ```bash
   git clone https://github.com/DevAI-MX/devia-editor-ia.git
   cd devia-editor-ia
   ```

   Si `git` no existe (Windows recién instalado), pídele a la persona que baje el ZIP (botón **Code**, después **Download ZIP**), lo descomprima y te diga dónde quedó. Si GitHub responde que no encuentra el repositorio o pide usuario y contraseña, el repositorio está privado: la persona necesita que Devia la invite y aceptar la invitación que le llega por correo. Con esa cuenta puede bajar el ZIP desde el navegador, o iniciar sesión con `gh auth login` para que vuelvas a clonar.

2. **Instala según el sistema**, desde la carpeta del editor:

   | Sistema | Comando | Qué puede pasar |
   |---|---|---|
   | Mac | `bash setup.sh` | Si falta Homebrew, la persona lo instala desde https://brew.sh (pide la contraseña de su Mac) y vuelves a ejecutar. |
   | Windows | `powershell -ExecutionPolicy Bypass -File setup-windows.ps1` | Instala Git, ffmpeg, Node 22 y uv con winget y luego corre `setup.sh` en Git Bash. Si Windows pide permiso, la persona acepta. Si al terminar algo no se encuentra, abre una terminal nueva y vuelve a ejecutarlo. |
   | Linux | `bash setup.sh` | Si faltan ffmpeg o Node 22, imprime comandos con `sudo`. Pásaselos para que los pegue en su terminal y vuelve a ejecutar. |

   La primera vez baja unos 3 GB y tarda de 10 a 30 minutos. Si tu terminal corta los comandos largos, déjalo corriendo en segundo plano y espera a que termine. Volver a ejecutarlo no rompe nada: salta lo que ya está.

3. **Comprueba.** Quedó bien si la salida termina en `Listo.` y cada paso dice `OK`. Si una línea dice `!!`, busca la causa, corrígela y vuelve a ejecutar. Si no se puede corregir, dile a la persona qué parte no quedó y qué consecuencia tiene (la propia línea lo explica).

4. **Entrega.** Dile a la persona que ya puede editar: que abra Claude Code dentro de la carpeta `devia-editor-ia`, ponga su video en `input/` y lo pida con sus palabras. El editor es una herramienta de Claude Code (`.claude/skills/editor-ia/`) y solo se carga si Claude Code se abre en esa carpeta. Si no eres Claude Code, el método completo está en `.claude/skills/editor-ia/SKILL.md`. En Windows, el editor se usa siempre desde Git Bash.

Créditos y licencias en `CREDITOS.md`.
