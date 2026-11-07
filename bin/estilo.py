#!/usr/bin/env python3
"""estilo/estilo.json -> estilo.js del proyecto.

La plantilla lee de aqui, no al reves: los numeros del HTML son solo respaldo por
si se abre suelto. Cambiar estilo.json cambia todos los videos que se monten
despues, sin tocar la plantilla.

Uso: bin/estilo.py estilo/estilo.json > proyecto/estilo.js
"""
import json, os, sys

c = json.load(open(sys.argv[1]))
b, sub = c["bloque"], c["subtitulo"]

css = {
    "--colchon": f"{c['bloque'].get('colchon', 90)}px",
    "--sub-size": f"{sub.get('cuerpo', 64)}px",
    "--sub-peso": sub.get("peso", 800),
    "--sub-track": sub["interletrado"],
    "--sub-y": ("66%" if str(sub.get("y")) == "auto" else sub["y"]),   # "auto" lo resuelve el montaje (barbilla.py)
    "--safe-x": sub["margen"],
    "--kw-margen": b["margen"],
    "--r-chica": b.get("ratio_chica", 0.42),
    "--r-serif": b.get("ratio_serif", 0.62),
    "--solape": b["solape_serif"],
    "--solape-chica": b["solape_chica"],
    "--interlinea": b["interlinea"],
    "--tinta": c["colores"]["tinta"],
    "--ocre": c["colores"]["ocre"],
    "--glow": c["glow"],
    "--st-blur": f"{c['stingers']['zoom']['blur']}px",
    "--st-grano": c["stingers"]["grano"],
    "--track-serif": c["bloque"].get("interletrado_serif", "-0.055em"),
    "--g-ref": f"{c['bloque'].get('cuerpo_ref', 112)}px",
    "--chica-px": f"{round(c['bloque'].get('cuerpo_ref', 112) * c['bloque']['ratio_chica'])}px",
    "--serif-px": f"{round(c['bloque'].get('cuerpo_ref', 112) * c['bloque']['ratio_serif'])}px",
    "--luz": c["bloque"].get("brillo", "35%"),
    "--banda": c.get("banda_util", "17%"),
    "--luz-radio": c["bloque"].get("brillo_radio", "30px"),
    "--glow-bloque": c["bloque"].get("halo", "0 0 18px rgba(0,0,0,.30), 0 0 7px rgba(0,0,0,.34)"),
    # subtitulos en DOS LINEAS (formato impacto). Los cuerpos vienen medidos
    # sobre las referencias a 1920 de alto, asi que se declaran en px igual que
    # el resto y la plantilla los baja si la frase no cabe.
    "--sub-lead": f"{sub.get('cuerpo_lead', 82)}px",
    "--sub-clave": f"{sub.get('cuerpo_clave', 106)}px",
    "--sub-peso-lead": sub.get("peso_lead", 700),
    "--sub-peso-clave": sub.get("peso_clave", 800),
    "--sub-op-lead": sub.get("opacidad_lead", 0.82),
    "--sub-interlinea": sub.get("interlinea", 1.06),
    "--sub-pegado": sub.get("pegado", 0.20),
    "--cta": c["colores"].get("cta", c["colores"]["ocre"]),
    # marco y titular del formato reflexivo
    "--marco-arriba": c.get("marco", {}).get("arriba", "16%"),
    "--marco-abajo": c.get("marco", {}).get("abajo", "22%"),
    "--marco-fondo": c.get("marco", {}).get("fondo", "#000000"),
    # el plano se mete en la banda solo si el formato lleva marco
    "--camara-arriba": c.get("marco", {}).get("arriba", "0") if c.get("marco") else "0",
    "--camara-abajo": c.get("marco", {}).get("abajo", "0") if c.get("marco") else "0",
    # donde va el plano dentro de la banda: lo mide bin/encuadre.py con la cara (montar.sh)
    "--camara-pos-y": os.environ.get("CAMARA_POS_Y", "50%"),
    "--titular-cuerpo": f"{c.get('titular', {}).get('cuerpo', 62)}px",
    "--titular-cuerpo2": f"{c.get('titular', {}).get('cuerpo_2', 44)}px",
    "--titular-peso": c.get("titular", {}).get("peso", 800),
    "--titular-y": c.get("titular", {}).get("y", "7.5%"),
    # rotulo del TOP 10
    "--rot-y": c.get("rotulo", {}).get("y", "20%"),
    "--rot-img": f"{float(str(c.get('rotulo', {}).get('img', '5.5%')).rstrip('%')) * 19.2:.0f}px",  # en px: el % de alto de un <img> no resuelve sin alto en el padre
    "--rot-num": f"{c.get('rotulo', {}).get('cuerpo_num', 150)}px",
    "--rot-txt": f"{c.get('rotulo', {}).get('cuerpo_txt', 52)}px",
    "--rot-peso-num": c.get("rotulo", {}).get("peso_num", 800),
    "--rot-peso-txt": c.get("rotulo", {}).get("peso_txt", 700),
    "--rot-color": c.get("rotulo", {}).get("color", "var(--tinta)"),
    "--rot-caso": "none" if c.get("rotulo", {}).get("mayusculas", True) is False else "uppercase",
    "--rot-fuente": c.get("rotulo", {}).get("fuente", "Inter"),
    # editorial: titulo apilado del gancho
    "--gan-fuente": c.get("titulo_gancho", {}).get("fuente", "Montserrat"),
    "--gan-y": c.get("titulo_gancho", {}).get("y", "6.5%"),
    "--gan-x": c.get("titulo_gancho", {}).get("margen", "6%"),
    "--gan-negrita": f"{c.get('titulo_gancho', {}).get('cuerpo_negrita', 116)}px",
    "--gan-negrita-grande": f"{c.get('titulo_gancho', {}).get('cuerpo_negrita_grande', 141)}px",
    "--gan-interlinea": c.get("titulo_gancho", {}).get("interlinea", 0.92),
    "--gan-x-izq": c.get("titulo_gancho", {}).get("margen_izq", "9%"),
    "--gan-fina": f"{c.get('titulo_gancho', {}).get('cuerpo_fina', 118)}px",
    "--gan-media": f"{c.get('titulo_gancho', {}).get('cuerpo_media', 110)}px",
    "--gan-peso-negrita": c.get("titulo_gancho", {}).get("peso_negrita", 800),
    "--gan-peso-fina": c.get("titulo_gancho", {}).get("peso_fina", 300),
    "--gan-peso-media": c.get("titulo_gancho", {}).get("peso_media", 600),
    "--gan-color": c.get("titulo_gancho", {}).get("color", "#ffffff"),
    "--gan-track": c.get("titulo_gancho", {}).get("interletrado", "-0.08em"),
    "--gan-sombra": c.get("titulo_gancho", {}).get("sombra", "none"),
    # editorial: ficha de color
    "--fc-fondo": c.get("ficha_color", {}).get("fondo", "#6b7a2b"),
    "--fc-tinta": c.get("ficha_color", {}).get("tinta", "#efe9d6"),
    "--fc-fuente": c.get("ficha_color", {}).get("fuente", "Acento"),
    "--fc-cuerpo": f"{c.get('ficha_color', {}).get('cuerpo', 118)}px",
    "--fc-grande": f"{c.get('ficha_color', {}).get('cuerpo_grande', 170)}px",
    "--fc-peso": c.get("ficha_color", {}).get("peso", 600),
    "--fc-y": c.get("ficha_color", {}).get("y", "52%"),
    # editorial: CTA "Comenta"
    "--cta-comenta": f"{c.get('palabra_clave', {}).get('cuerpo_comenta', 100)}px",
    "--cta-peso-comenta": c.get("palabra_clave", {}).get("peso_comenta", 600),
    "--cta-peso": c.get("palabra_clave", {}).get("peso", 700),
    "--cta-fuente": c.get("palabra_clave", {}).get("fuente_palabra", "Poppins"),
    "--cta-fuente-comenta": c.get("palabra_clave", {}).get("fuente_comenta", "Inter"),
    "--cta-color": c.get("palabra_clave", {}).get("color", "var(--ocre)"),
    "--cta-halo": c.get("palabra_clave", {}).get("halo", "0 0 36px rgba(0,0,0,.55), 0 2px 10px rgba(0,0,0,.45)"),
    "--sub-halo": c.get("subtitulo", {}).get("halo", "0 2px 9px rgba(0,0,0,.66)"),
    "--ita-size": f"{c.get('subtitulo', {}).get('italica', {}).get('cuerpo', 131)}px",
    "--ita-peso": c.get("subtitulo", {}).get("italica", {}).get("peso", 600),
    "--ita-track": c.get("subtitulo", {}).get("italica", {}).get("interletrado", "-0.06em"),
    "--ita-fuente": c.get("subtitulo", {}).get("italica", {}).get("fuente", "Acento"),
    "--rot-sombra": c.get("rotulo", {}).get("sombra", "0 2px 10px rgba(0,0,0,.85), 0 0 22px rgba(0,0,0,.55)"),
    "--fc-track": c.get("ficha_color", {}).get("interletrado", "-0.09em"),
    "--fc-interlinea": c.get("ficha_color", {}).get("interlinea", 0.88),
}

out = [f"window.__ESTILO__ = {json.dumps(c, ensure_ascii=False)};",
       "(function () { var r = document.documentElement;"]
for k, v in css.items():
    out.append(f"  r.style.setProperty({json.dumps(k)}, {json.dumps(str(v))});")
out.append("})();")
print("\n".join(out))
