#!/usr/bin/env python3
"""Capturas por dirección y estado + lámina comparativa. Lo lanza generar_capturas.sh dentro de la imagen de Playwright."""
import pathlib
from playwright.sync_api import sync_playwright
AQUI = pathlib.Path(__file__).resolve().parent
M = (AQUI / "maqueta" / "maqueta.html").as_uri()
DIRS = {"A": "A-codice", "B": "B-meridiano", "C": "C-sello"}
ESTADOS = ["lista", "generando", "sin-normativa", "valorada", "sin-conexion"]
with sync_playwright() as p:
    nav = p.chromium.launch()
    pag = nav.new_context(viewport={"width": 790, "height": 100}, reduced_motion="reduce").new_page()
    for d, n in DIRS.items():
        for e in ESTADOS:
            pag.goto(f"{M}?dir={d}&estado={e}"); pag.evaluate("document.fonts.ready")
            pag.screenshot(path=str(AQUI / "capturas" / f"{n}--{e}.png"), full_page=True)
    pag = nav.new_context(viewport={"width": 1800, "height": 900}, reduced_motion="reduce").new_page()
    pag.goto((AQUI / "lamina.html").as_uri()); pag.evaluate("document.fonts.ready")
    pag.screenshot(path=str(AQUI / "lamina-comparativa.png"), full_page=True)
    nav.close()
print("listo")
