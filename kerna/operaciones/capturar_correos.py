"""Captura las vistas previas de los correos (salida/correos/*.html) a 600 y 375 px. Corre dentro del contenedor Playwright (ver capturar_correos.sh)."""
from pathlib import Path
from playwright.sync_api import sync_playwright

D = Path("/out/correos")
with sync_playwright() as p:
    b = p.chromium.launch()
    for ancho in (600, 375):
        pag = b.new_page(viewport={"width": ancho, "height": 900}, device_scale_factor=2)
        for f in sorted(D.glob("*.html")):
            pag.goto(f"file://{f}")
            hscroll = pag.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")
            pag.screenshot(path=str(D / f"{f.stem}-{ancho}.png"), full_page=True)
            print(f.stem, ancho, "scroll horizontal:", hscroll)
    b.close()
