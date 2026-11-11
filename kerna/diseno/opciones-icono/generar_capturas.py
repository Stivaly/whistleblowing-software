#!/usr/bin/env python3
"""Genera una captura PNG por opción de ícono y estado a partir de maqueta/maqueta.html.

No se ejecuta en el host: lo lanza generar_capturas.sh dentro de la imagen oficial de Playwright.
Salida: <opcion>--<estado>.png (más contingencia con cada variante e icono-tamanos.png) en esta carpeta.
"""
import pathlib
from playwright.sync_api import sync_playwright

AQUI = pathlib.Path(__file__).resolve().parent
MAQUETA = (AQUI / "maqueta" / "maqueta.html").as_uri()
ICONOS = ["robot", "v-veridy", "articulo-marcado", "balanza"]
ESTADOS = ["sin-info", "generando", "lista", "contingencia", "revision-tiempo", "revision-citas",
           "sin-normativa", "cadena-agotada", "nucleo-no-disponible", "conector-inactivo", "sin-conexion", "valorada"]
VARIANTES = ["local", "recuperacion-local"]  # además de "respaldo", que es la contingencia por defecto

with sync_playwright() as p:
    nav = p.chromium.launch()
    # reduced_motion: capturas estables y comprobación de que la maqueta respeta prefers-reduced-motion
    ctx = nav.new_context(viewport={"width": 1112, "height": 900}, reduced_motion="reduce", device_scale_factor=1)
    pag = ctx.new_page()
    n = 0
    for icono in ICONOS:
        for estado in ESTADOS:
            pag.goto(f"{MAQUETA}?icono={icono}&estado={estado}")
            pag.screenshot(path=str(AQUI / f"{icono}--{estado}.png"), full_page=True)
            n += 1
        for v in VARIANTES:
            pag.goto(f"{MAQUETA}?icono={icono}&estado=contingencia&variante={v}")
            pag.screenshot(path=str(AQUI / f"{icono}--contingencia-{v}.png"), full_page=True)
            n += 1
    pag.goto(f"{MAQUETA}?vista=iconos")
    pag.screenshot(path=str(AQUI / "iconos-tamanos.png"), full_page=True)
    nav.close()
print(f"{n + 1} capturas generadas en {AQUI}")
