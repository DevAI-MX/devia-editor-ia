#!/usr/bin/env python3
"""Saca un RECORTE con fondo transparente de un fotograma del material propio.

Es la fabrica de props. En las referencias las imagenes que acompanan al gancho son
recortes limpios — un grupo de gente, una cara, un objeto — sin fondo y sin halo. Aqui
se sacan del mismo b-roll que ya tiene el video, asi que no se inventa nada: es
material suyo, recortado.

Segmenta con isnet-general-use, que es el que agarra a la persona con lo que sostiene
en vez de recortar solo la silueta. OJO: isnet normaliza con media 0.5 y desviacion
1.0; con la normalizacion de ImageNet devuelve una mascara VACIA y sin dar error.

Uso: bin/recortar.py <video_o_imagen> <segundo> <salida.png> [--alto-min 0.25]
"""
import os, subprocess, sys, tempfile

FFMPEG = "ffmpeg"


def main():
    if len(sys.argv) < 4:
        print(__doc__, file=sys.stderr)
        sys.exit(2)
    orig, t, salida = sys.argv[1], float(sys.argv[2]), sys.argv[3]
    tmp = os.path.join(tempfile.gettempdir(), "_recorte_fuente.png")

    if orig.lower().endswith((".mp4", ".mov", ".m4v", ".webm")):
        subprocess.run([FFMPEG, "-nostdin", "-v", "error", "-ss", str(t), "-i", orig,
                        "-frames:v", "1", tmp, "-y"], check=True)
    else:
        tmp = orig

    bruto = os.path.join(tempfile.gettempdir(), "_recorte_bruto.png")
    r = subprocess.run(["uvx", "--from", "rembg[cli,cpu]", "rembg", "i",
                        "-m", "isnet-general-use", tmp, bruto],
                       capture_output=True, text=True)
    if r.returncode != 0 or not os.path.exists(bruto):
        print("ERROR: no se pudo segmentar:", r.stderr[-400:], file=sys.stderr)
        sys.exit(1)

    from PIL import Image
    import numpy as np
    im = Image.open(bruto).convert("RGBA")

    # La segmentacion deja fantasmas: manchones sueltos de fondo con alfa a medias que
    # en el video se leen como una mancha gris al lado del sujeto. Se queda SOLO la
    # mancha mas grande — el sujeto — y el resto se borra.
    al = np.array(im)[:, :, 3]
    solido = al > 128
    if solido.any():
        etiqueta = np.zeros(solido.shape, np.int32)
        pila, sig = [], 0
        for y0 in range(solido.shape[0]):
            for x0 in range(solido.shape[1]):
                if not solido[y0, x0] or etiqueta[y0, x0]:
                    continue
                sig += 1
                pila = [(y0, x0)]
                etiqueta[y0, x0] = sig
                while pila:
                    y, x = pila.pop()
                    for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                        v, u = y + dy, x + dx
                        if (0 <= v < solido.shape[0] and 0 <= u < solido.shape[1]
                                and solido[v, u] and not etiqueta[v, u]):
                            etiqueta[v, u] = sig
                            pila.append((v, u))
        if sig > 1:
            cuentas = np.bincount(etiqueta.ravel())
            cuentas[0] = 0
            mayor = int(cuentas.argmax())
            rgba = np.array(im)
            rgba[:, :, 3] = np.where(etiqueta == mayor, rgba[:, :, 3], 0)
            im = Image.fromarray(rgba, "RGBA")
            print(f"  fantasmas fuera: {sig - 1} manchas sueltas borradas", file=sys.stderr)

    caja = im.getbbox()          # recorta al contenido: sin esto el PNG lleva
    if not caja:                 # medio cuadro de transparencia y se coloca fatal
        print("ERROR: la mascara salio vacia (fondo sin sujeto reconocible)", file=sys.stderr)
        sys.exit(1)
    im = im.crop(caja)

    # Una mascara vacia no da error: devuelve un PNG entero transparente y el prop
    # sale invisible en el video sin que nadie se entere hasta verlo. Y una mascara
    # que se come el fondo entero (opaca hasta los bordes) no es un recorte, es el
    # fotograma con otro nombre.
    import numpy as np
    al = np.array(im)[:, :, 3]
    opaco = float(np.mean(al > 200))
    borde = float(np.mean(np.concatenate([al[0], al[-1], al[:, 0], al[:, -1]]) > 200))
    if opaco < 0.03:
        print(f"ERROR: la mascara salio vacia ({opaco:.1%} opaco). Prueba otro segundo: "
              f"en ese fotograma no hay un sujeto que recortar.", file=sys.stderr)
        sys.exit(1)
    if borde > 0.15:
        print(f"AVISO: el recorte toca los bordes ({borde:.0%}): mas que un recorte es "
              f"el fotograma entero. Prueba otro segundo.", file=sys.stderr)

    alto_min = 0.25
    if "--alto-min" in sys.argv:
        alto_min = float(sys.argv[sys.argv.index("--alto-min") + 1])
    orig_alto = Image.open(bruto).height
    if im.height < orig_alto * alto_min:
        print(f"AVISO: el recorte ocupa solo el {im.height / orig_alto:.0%} del alto "
              f"original: puede que la segmentacion se haya comido al sujeto",
              file=sys.stderr)

    os.makedirs(os.path.dirname(os.path.abspath(salida)), exist_ok=True)
    im.save(salida)
    print(f"{salida}: {im.width}x{im.height}")


main()
