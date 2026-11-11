#!/usr/bin/env python3
"""Capturas por estado y lámina. Lo lanza generar_capturas.sh dentro de la imagen de Playwright (sin movimiento)."""
import pathlib
from playwright.sync_api import sync_playwright
AQUI = pathlib.Path(__file__).resolve().parent
IDS = ["sin-info","generando","lista","contingencia-modelo","contingencia-busqueda","revision-tiempo","revision-citas","sin-normativa","cadena-agotada","nucleo-no-disponible","conector-sin-nota","conector-en-proceso","sin-conexion","valorada"]
with sync_playwright() as p:
    nav = p.chromium.launch()
    pag = nav.new_context(viewport={"width": 860, "height": 600}, reduced_motion="reduce", device_scale_factor=1).new_page()
    for c, n in (("A", "A-hilo"), ("B", "B-nucleo")):
        pag.goto((AQUI / "maqueta" / f"maqueta-{c}.html").as_uri()); pag.evaluate("document.fonts.ready")
        for i in IDS:
            pag.locator(f"#{i}").screenshot(path=str(AQUI / "capturas" / f"{n}--{i}.png"))
    pag = nav.new_context(viewport={"width": 1872, "height": 900}, reduced_motion="reduce").new_page()
    pag.goto((AQUI / "lamina.html").as_uri()); pag.evaluate("document.fonts.ready")
    pag.screenshot(path=str(AQUI / "lamina-comparativa.png"), full_page=True)
    nav.close()
print("listo")
