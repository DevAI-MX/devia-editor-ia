#!/usr/bin/env python3
"""Recorta al que habla para poder meterle cosas DETRAS.

Es lo que hace que un elemento no le tape: en vez de colocarlo en un hueco libre, se
pone detras de el. Se saca una copia del A-roll con el fondo transparente — solo el
sujeto — y esa copia se pinta ENCIMA del elemento. El resultado es que su cuerpo y sus
manos pasan por delante, como en las referencias.

Solo se hace de la ventana que hace falta, no del video entero: son ~1s por fotograma.

Uso: bin/matte.py <aroll.mp4> <desde> <dur> <salida.webm> [ancho]
"""
import os, shutil, subprocess, sys, tempfile

FFMPEG = "ffmpeg"
FPS = 30


def main():
    if len(sys.argv) < 5:
        print(__doc__, file=sys.stderr)
        sys.exit(2)
    aroll, desde, dur, salida = sys.argv[1], float(sys.argv[2]), float(sys.argv[3]), sys.argv[4]
    ancho = int(sys.argv[5]) if len(sys.argv) > 5 else 1080

    tmp = tempfile.mkdtemp(prefix="matte_")
    dentro, fuera = os.path.join(tmp, "in"), os.path.join(tmp, "out")
    os.makedirs(dentro); os.makedirs(fuera)
    try:
        subprocess.run([FFMPEG, "-nostdin", "-v", "error", "-ss", str(desde), "-t", str(dur),
                        "-i", aroll, "-vf", f"fps={FPS},scale={ancho}:-2",
                        os.path.join(dentro, "f_%04d.png"), "-y"], check=True)
        n = len(os.listdir(dentro))
        if not n:
            print("ERROR: no salio ni un fotograma de esa ventana", file=sys.stderr)
            sys.exit(1)
        print(f"  recortando al sujeto en {n} fotogramas (~{n}s)...", file=sys.stderr)
        r = subprocess.run(["uvx", "--from", "rembg[cli,cpu]", "rembg", "p",
                            "-m", "isnet-general-use", dentro, fuera],
                           capture_output=True, text=True)
        if r.returncode != 0 or not os.listdir(fuera):
            print("ERROR: la segmentacion fallo:", r.stderr[-400:], file=sys.stderr)
            sys.exit(1)

        # El alfa se pone DURO: todo lo que pase de la mitad queda opaco del todo y el
        # resto transparente del todo. Con el alfa suave que devuelve la segmentacion,
        # el elemento de detras se transparenta a traves de su cuerpo y se ve un doble
        # fantasma sobre la camisa. Se deja un pelin de pluma en el filo para que el
        # recorte no quede de tijera.
        from PIL import Image, ImageFilter
        import numpy as np
        for f in sorted(os.listdir(fuera)):
            ruta = os.path.join(fuera, f)
            im = Image.open(ruta).convert("RGBA")
            a = np.array(im)
            dura = (a[:, :, 3] > 128).astype("uint8") * 255
            a[:, :, 3] = dura
            im = Image.fromarray(a, "RGBA")
            alfa = im.getchannel("A").filter(ImageFilter.GaussianBlur(1.2))
            im.putalpha(alfa)
            im.save(ruta)

        # VP9 con alfa: es el unico contenedor con transparencia que Chrome reproduce,
        # y HyperFrames renderiza en Chrome. Un MP4 no guarda el canal alfa.
        os.makedirs(os.path.dirname(os.path.abspath(salida)), exist_ok=True)
        subprocess.run([FFMPEG, "-nostdin", "-v", "error", "-framerate", str(FPS),
                        "-i", os.path.join(fuera, "f_%04d.png"),
                        "-c:v", "libvpx-vp9", "-pix_fmt", "yuva420p",
                        "-b:v", "0", "-crf", "28", "-row-mt", "1",
                        salida, "-y"], check=True)
        mb = os.path.getsize(salida) / 1e6
        # TODO por stderr. La salida estandar de este script la recoge props.py, que
        # a su vez alimenta el HTML del proyecto: una sola linea de mas aqui se cuela
        # como texto suelto dentro de la composicion. Paso — la ruta del .webm acabo
        # escrita en el video y el revisor de contraste la marcaba como texto ilegible.
        print(f"{salida}: {n} fotogramas, {mb:.1f} MB", file=sys.stderr)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


main()
