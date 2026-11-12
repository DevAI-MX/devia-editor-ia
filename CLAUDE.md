# Editor de video con IA · Devia Consulting: instrucciones para Claude Code

Hecho por Devia Consulting.

Este editor convierte un video grabado con el celular en un reel vertical listo para Reels y TikTok: cortes, subtítulos palabra por palabra, efectos, música y movimiento. También une y edita clips hechos con IA. Quien lo usa no es técnica. Tú haces el trabajo de principio a fin y le explicas en palabras simples, en español. No le pidas que toque nada técnico.

`README.md` es la guía para personas: qué hace el editor, cómo se instala y cómo se usa. Cuando te pregunten algo de eso, respóndelo con tus palabras a partir de ahí.

## Al empezar

- **Si el editor no está instalado** (no existe la carpeta `.venv`) y te piden editar un video, instálalo primero (ver "Si te piden instalar el editor") y después sigue con lo que pidieron.
- **Si preguntan qué pueden hacer**, explícalo en pocas líneas: editar sus videos grabados en tres estilos, y unir y editar clips hechos con IA. Ofrece instalar el editor si todavía no lo está.

## Si te piden instalar el editor

Cuando digan "instala el editor" (o algo parecido), hazlo tú de principio a fin:

1. Avísale que la primera vez se descargan unos 3 GB (el modelo que transcribe los videos) y que puede tardar entre 10 y 30 minutos según su internet.
2. **En Mac:** ejecuta `bash setup.sh` desde esta carpeta y lee su salida. Si falta Homebrew, es lo único que no puedes instalar tú, porque pide la contraseña de la Mac. Explícale que lo instale desde https://brew.sh pegando en la Terminal el comando que aparece ahí, y cuando termine vuelve a ejecutar `bash setup.sh`.
3. **En Windows:** ejecuta `powershell -ExecutionPolicy Bypass -File setup-windows.ps1` desde esta carpeta. Instala con winget Git, ffmpeg, Node y uv, y después corre `setup.sh`. Si Windows pide permiso para instalar, dile que acepte. Si al terminar dice que cierre y vuelva a abrir, pídele que cierre Claude Code, lo abra otra vez en esta carpeta y te diga "sigue instalando el editor". El editor necesita Git Bash: si al abrir Claude Code no tienes la herramienta Bash, el editor no está instalado todavía.
4. **En Linux:** ejecuta `bash setup.sh`. Instala uv solo; si faltan ffmpeg o Node 22, imprime los comandos con `sudo`. Pásaselos para que los pegue en su terminal (piden su contraseña) y vuelve a ejecutar `bash setup.sh`.
5. Si algo sale en rojo, busca la causa, corrígela y vuelve a ejecutar. No le pases el error sin intentarlo.
6. Al final confirma en una frase qué quedó instalado y dile cómo pedir su primer video.

## Cómo se edita

Todo el método está en `.claude/skills/editor-ia/SKILL.md`. Léelo antes de editar, y `.claude/skills/editor-ia/ESPECIFICACION.md` para las medidas.

- **Video grabado:** el video va en `input/`, la música con licencia en `musica/` (si no hay, el editor crea una base propia). Se entrega en `salida/`.
- **Clips hechos con IA (Google Flow u otro):** van juntos en `input/<carpeta>/`. El editor los une, les quita el silencio, corrige el ritmo y los edita. Si son dos personajes que conversan, cada clip entra unos 0.3 s antes de que termine el anterior.

## Reglas fijas

- Todas las rutas son relativas a esta carpeta. Nunca escribas rutas de un equipo concreto.
- Corre Python siempre con `bash bin/py <script>`: usa el Python del editor en Mac, Windows y Linux. No uses `python3` ni `source .venv/bin/activate`.
- Si falta una herramienta, ejecuta tú `bash setup.sh` (en Windows, `setup-windows.ps1` si falta ffmpeg, Node o uv).
- La música sale solo de `musica/`. Si está vacía, el editor sintetiza una base propia: no hace falta frenar la edición.
- Nada inventado: ni cifras, ni testimonios, ni texto en pantalla que no se haya dicho.
- Al hablar con la persona, usa palabras simples y explica cualquier término técnico la primera vez.
