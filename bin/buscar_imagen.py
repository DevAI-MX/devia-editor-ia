#!/usr/bin/env python3
"""Consigue imagenes para una escena cuando la biblioteca no las tiene.

Dos pasos, porque las imagenes se ELIGEN MIRANDOLAS, no por el nombre:

  buscar  bin/buscar_imagen.py buscar "<tema>" [n]
          -> baja n candidatas de Pexels (via scripts/buscar-imagen.mjs, Brave sin
             ventana) y monta una hoja de contactos numerada para verlas.

  elegir  bin/buscar_imagen.py elegir <carpeta_busqueda> <ids...> --como lamina|prop|broll --nombre <base>
          -> normaliza las elegidas y las deja en input/props/top10 (lamina 3:2),
             input/props (prop) o input/broll/romance (fotograma vertical).

Pexels es de donde ya sale la biblioteca del usuario, y su licencia permite el uso
comercial. Aun asi: una foto de archivo no es un recorte — para un prop con fondo
transparente hay que pasarla despues por bin/recortar.py.
"""
import json, os, subprocess, sys
from PIL import Image, ImageDraw

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PW = os.environ.get("PLAYWRIGHT_DIR", "")  # opcional: busqueda de imagenes en la web
BUSQ = os.path.join(RAIZ, "input", "busquedas")


def buscar_api(tema, n, out, video):
    """Con PEXELS_API_KEY se usa la API oficial: sin verificaciones de bot, con
    licencia explicita, y con resultados verticales pedidos a proposito."""
    import urllib.request
    key = os.environ["PEXELS_API_KEY"]
    q = urllib.parse.quote(tema)
    url = (f"https://api.pexels.com/videos/search?query={q}&per_page={n}&orientation=portrait" if video
           else f"https://api.pexels.com/v1/search?query={q}&per_page={n}&orientation=portrait")
    req = urllib.request.Request(url, headers={"Authorization": key})
    data = json.load(urllib.request.urlopen(req, timeout=30))
    os.makedirs(out, exist_ok=True)
    res = []
    for it in data.get("videos" if video else "photos", []):
        if video:
            res.append({"id": str(it["id"]), "url": it["url"]}); continue
        src = it["src"].get("large2x") or it["src"]["large"]
        f = os.path.join(out, f"pexels_{it['id']}.jpg")
        urllib.request.urlretrieve(src, f)
        res.append({"id": str(it["id"]), "url": src, "file": f})
    json.dump({"tema": tema, "url": url, "resultados": res}, open(os.path.join(out, "indice.json"), "w"), indent=1)


def buscar_openverse(tema, n, out):
    """Sin clave y sin verificacion de bot, pero con dos peros que hay que saber:
    las fotos llegan a ~1024 px (Flickr) y la licencia es CC-BY, que exige CREDITO.
    Se guarda la atribucion de cada una en indice.json para poder ponerla. Se dejan
    fuera las SA (obligan a compartir igual) y las NC (no comerciales)."""
    import urllib.request, urllib.parse
    q = urllib.parse.quote(tema)
    url = (f"https://api.openverse.org/v1/images/?q={q}&license_type=commercial"
           f"&license=by,cc0,pdm&aspect_ratio=tall&page_size={n * 2}")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    data = json.load(urllib.request.urlopen(req, timeout=30))
    os.makedirs(out, exist_ok=True)
    res = []
    for it in data.get("results", []):
        if len(res) >= n:
            break
        try:
            f = os.path.join(out, f"ov_{it['id'][:8]}.jpg")
            r2 = urllib.request.Request(it["url"], headers={"User-Agent": "Mozilla/5.0"})
            open(f, "wb").write(urllib.request.urlopen(r2, timeout=30).read())
            res.append({"id": it["id"][:8], "url": it["url"], "file": f,
                        "licencia": it.get("license"), "autor": it.get("creator"),
                        "atribucion": it.get("attribution"), "fuente": it.get("foreign_landing_url")})
        except Exception:
            continue
    json.dump({"tema": tema, "url": url, "fuente": "openverse (CC-BY: hay que dar credito)",
               "resultados": res}, open(os.path.join(out, "indice.json"), "w"), indent=1)


def buscar(tema, n=8, video=False):
    import urllib.parse
    slug = "".join(c if c.isalnum() else "_" for c in tema.lower())[:40]
    out = os.path.join(BUSQ, slug)
    if os.environ.get("PEXELS_API_KEY"):
        buscar_api(tema, n, out, video)                 # 1. lo mejor: API oficial
    else:
        cmd = ["node", "scripts/buscar-imagen.mjs", tema, str(n), out] + (["--video"] if video else [])
        r = subprocess.run(cmd, cwd=PW, capture_output=True, text=True)
        if r.returncode != 0:                           # 2. Cloudflare nos para -> 3. Openverse
            print("  pexels bloqueado por verificacion de bot; se usa Openverse (CC-BY)", file=sys.stderr)
            buscar_openverse(tema, n, out)
    idx = json.load(open(os.path.join(out, "indice.json")))
    fs = [x for x in idx["resultados"] if x.get("file")]
    if fs:
        W, Hh, et = 260, 390, 22
        C = min(len(fs), 4)
        R = (len(fs) + C - 1) // C
        hoja = Image.new("RGB", (W * C, (Hh + et) * R), (18, 18, 18))
        d = ImageDraw.Draw(hoja)
        for i, x in enumerate(fs):
            im = Image.open(x["file"]).convert("RGB")
            im.thumbnail((W, Hh))
            cx, cy = W * (i % C), (Hh + et) * (i // C)
            hoja.paste(im, (cx + (W - im.width) // 2, cy + et + (Hh - im.height) // 2))
            d.text((cx + 6, cy + 5), f"{i + 1}  ·  {x['id']}", fill=(235, 235, 235))
        hoja.save(os.path.join(out, "hoja.jpg"), quality=90)
    print(json.dumps({"tema": tema, "carpeta": out, "candidatas": len(fs),
                      "hoja": os.path.join(out, "hoja.jpg") if fs else None,
                      "ids": [x["id"] for x in fs]}, ensure_ascii=False))


def elegir(carpeta, ids, como, nombre):
    idx = json.load(open(os.path.join(carpeta, "indice.json")))
    por_id = {x["id"]: x for x in idx["resultados"] if x.get("file")}
    dest = {"lamina": os.path.join(RAIZ, "input", "props", "top10"),
            "prop": os.path.join(RAIZ, "input", "props"),
            "broll": os.path.join(RAIZ, "input", "broll", "romance")}[como]
    os.makedirs(dest, exist_ok=True)
    hechos = []
    for k, i in enumerate(ids, 1):
        x = por_id.get(i)
        if not x:
            print(f"  no existe la candidata {i}", file=sys.stderr); continue
        im = Image.open(x["file"]).convert("RGB")
        base = f"{nombre}{k if len(ids) > 1 else ''}"
        if como == "lamina":                       # 3:2 apaisada, como las referencias
            w, h = im.size; r = 3 / 2
            if w / h > r: nw = int(h * r); im = im.crop(((w - nw) // 2, 0, (w + nw) // 2, h))
            else: nh = int(w / r); im = im.crop((0, (h - nh) // 2, w, (h + nh) // 2))
            im = im.resize((900, 600), Image.LANCZOS); f = os.path.join(dest, base + ".png"); im.save(f)
        elif como == "broll":                      # fotograma vertical 1080x1920
            w, h = im.size; r = 9 / 16
            if w / h > r: nw = int(h * r); im = im.crop(((w - nw) // 2, 0, (w + nw) // 2, h))
            else: nh = int(w / r); im = im.crop((0, (h - nh) // 2, w, (h + nh) // 2))
            im = im.resize((1080, 1920), Image.LANCZOS); f = os.path.join(dest, base + ".jpg"); im.save(f, quality=94)
        else:
            f = os.path.join(dest, base + ".jpg"); im.save(f, quality=94)
        hechos.append(f)
        print(f"  {os.path.relpath(f, RAIZ)}  <- pexels {i}")
    return hechos


if __name__ == "__main__":
    a = sys.argv[1:]
    if not a:
        print(__doc__); sys.exit(2)
    if a[0] == "buscar":
        buscar(a[1], int(a[2]) if len(a) > 2 and a[2].isdigit() else 8, "--video" in a)
    elif a[0] == "elegir":
        como = a[a.index("--como") + 1]; nombre = a[a.index("--nombre") + 1]
        ids = [x for x in a[2:] if not x.startswith("--") and x not in (como, nombre)]
        elegir(a[1], ids, como, nombre)
