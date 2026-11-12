#!/usr/bin/env python3
"""Exporta la decoración del front (tramas guilloché, órbitas de fondo, símbolo del menú) de SVG a WebP con transparencia.

Por qué no GIF: solo tiene 256 colores y transparencia de 1 bit (bordes serruchados sobre fondos de color) y pesa más que WebP.
WebP con alfa conserva el degradado del trazo punteado y pesa una fracción; solo la capa gira con CSS transform (compositor, sin repintar).

Se ejecuta en la imagen oficial de Playwright (nada se instala en el host), ver rasterizar_decoracion.sh.
Entrada: herramientas/fuentes-decoracion/*.svg (guilloché), app/estaticos/img/simbolo.svg. Salida: app/estaticos/img/*.webp"""
import io
import re
import sys
import urllib.parse
from pathlib import Path

from PIL import Image
from playwright.sync_api import sync_playwright

RAIZ = Path(sys.argv[1] if len(sys.argv) > 1 else "/front")
EST = RAIZ / "app/estaticos"
IMG = EST / "img"


def fuente(nombre: str) -> str:
    return (RAIZ / "herramientas/fuentes-decoracion" / (nombre + ".svg")).read_text()


def orbitas() -> str:
    return ("<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 1200 1200' fill='none'>"
            "<circle cx='600' cy='600' r='560' fill='none' stroke='#1C2A6B' stroke-opacity='.4' stroke-width='3' stroke-dasharray='.1 15' stroke-linecap='round'/>"
            "<circle cx='1160' cy='600' r='12' fill='#CFFF5E' stroke='#1C2A6B' stroke-width='4'/>"
            "<circle cx='600' cy='600' r='430' fill='none' stroke='#1C2A6B' stroke-opacity='.4' stroke-width='3' stroke-dasharray='.1 15' stroke-linecap='round'/></svg>")


def roseta() -> str:
    el = "".join("<ellipse cx='600' cy='600' rx='330' ry='100' transform='rotate(%d 600 600)' fill='none' stroke='#1C2A6B' stroke-opacity='.3' stroke-width='2.4' stroke-dasharray='.1 13' stroke-linecap='round'/>" % g
                 for g in range(0, 180, 15))
    return "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 1200 1200' fill='none'>%s</svg>" % el


def main():
    trabajos = [  # nombre, svg, lado en px (2x del mayor tamaño de uso)
        ("guil", fuente("guil"), 288), ("guil-l", fuente("guil-l"), 640),
        ("bg-orbitas", orbitas(), 1600), ("bg-roseta", roseta(), 1600),
        ("simbolo", (IMG / "simbolo.svg").read_text(), 192),
    ]
    with sync_playwright() as p:
        nav = p.chromium.launch()
        for nombre, svg, lado in trabajos:
            pag = nav.new_page(viewport={"width": lado, "height": lado}, device_scale_factor=1)
            pag.set_content("<style>html,body{margin:0;background:transparent}svg{display:block;width:%dpx;height:%dpx}</style>%s" % (lado, lado, svg))
            png = pag.screenshot(omit_background=True)
            im = Image.open(io.BytesIO(png)).convert("RGBA")
            destino = IMG / (nombre + ".webp")
            im.save(destino, "WEBP", quality=80, method=6, alpha_quality=100)
            print(nombre, im.size, destino.stat().st_size, "bytes")
            pag.close()
        nav.close()


if __name__ == "__main__":
    main()
