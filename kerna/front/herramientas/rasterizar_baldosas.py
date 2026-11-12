#!/usr/bin/env python3
"""Exporta a PNG las baldosas de estado del veredicto del informe (símbolos t-* de identidad.svg con los colores de kerna.css), para el PDF.
Se ejecuta en la imagen oficial de Playwright (ver rasterizar_baldosas.sh). Salida: app/estaticos/img/baldosa-<estado>.png (288 x 216)."""
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

RAIZ = Path(sys.argv[1] if len(sys.argv) > 1 else "/front")
EST = RAIZ / "app/estaticos"
ESTADOS = ["lista", "contingencia-modelo", "cadena-agotada", "sin-info"]


def main():
    sprite = (EST / "identidad.svg").read_text()
    css = (EST / "kerna.css").read_text()
    with sync_playwright() as p:
        nav = p.chromium.launch()
        pag = nav.new_page(viewport={"width": 400, "height": 300}, device_scale_factor=1)
        for e in ESTADOS:
            html = (f"<style>{css}html,body{{margin:0;background:transparent}}</style>{sprite}"
                    f'<span class="ti" data-e="{e}" style="width:288px"><svg viewBox="0 0 160 120"><use href="#t-{e}"/></svg></span>')
            pag.set_content(html)
            destino = EST / "img" / f"baldosa-{e}.png"
            pag.locator(".ti").screenshot(path=str(destino), omit_background=True)
            print(e, destino.stat().st_size, "bytes")
        nav.close()


if __name__ == "__main__":
    main()
