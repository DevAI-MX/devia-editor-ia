# Créditos y licencias

**Editor de video con IA**: scripts, estilos, plantilla y especificación, hechos por Devia Consulting.

Componentes de terceros incluidos o usados por el editor:

| Componente | Uso | Licencia |
|---|---|---|
| HyperFrames 0.7.110 | Motor de render. No va dentro del editor: se descarga con `npx`. | Apache 2.0 |
| Whisper, mlx-whisper y faster-whisper | Transcripción (mlx-whisper en Mac con chip Apple, faster-whisper en los demás equipos). Los instala `setup.sh`. | MIT |
| DeepFilterNet | Limpieza de voz. Se descarga con `uvx` la primera vez. | MIT o Apache 2.0 |
| uv | Crea el entorno de Python del editor. | MIT o Apache 2.0 |
| FFmpeg | Cortes, audio y video. Lo instala Homebrew en Mac, winget en Windows y el gestor de paquetes en Linux. | LGPL / GPL |
| Inter, Montserrat, Poppins, Playfair Display, DM Serif Text, Cormorant Garamond | Tipografías de la plantilla | SIL Open Font License 1.1 |
| Lucide | Iconos de la plantilla | ISC |

Los textos completos de las licencias de fuentes e iconos están en `plantilla/licencias/`.

Los efectos de sonido no vienen de ninguna librería: se sintetizan en tu equipo al instalar, con `bin/gen-sfx.sh`.

El editor no incluye música. Cada equipo usa la suya, con licencia.
