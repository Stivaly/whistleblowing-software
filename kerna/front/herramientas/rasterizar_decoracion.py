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


def orbitas() -> str:  # solo referencia: no se usa, bg-orbitas.webp no se regenera
    return ("<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 1200 1200' fill='none'>"
            "<circle cx='600' cy='600' r='560' fill='none' stroke='#1C2A6B' stroke-opacity='.4' stroke-width='3' stroke-dasharray='.1 15' stroke-linecap='round'/>"
                        "<circle cx='600' cy='600' r='430' fill='none' stroke='#1C2A6B' stroke-opacity='.4' stroke-width='3' stroke-dasharray='.1 15' stroke-linecap='round'/></svg>")


def halo() -> str:
    """Halo de los paneles azules de Ajustes: dos órbitas punteadas con un satélite pequeño cada una; gira lento con CSS transform."""
    return ("<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 300 300' fill='none'>"
            "<circle cx='150' cy='150' r='144' stroke='#fff' stroke-opacity='.32' stroke-width='1.6' stroke-dasharray='.1 7' stroke-linecap='round'/>"
            "<circle cx='294' cy='150' r='4.5' fill='#CFFF5E'/>"
            "<circle cx='150' cy='150' r='104' stroke='#fff' stroke-opacity='.26' stroke-width='1.6' stroke-dasharray='.1 7' stroke-linecap='round'/>"
            "<circle cx='46' cy='150' r='3.5' fill='#fff' fill-opacity='.85'/></svg>")


def zona(c: str, sat1: str, sat2: str) -> str:
    """Arcos orbitales para las esquinas derechas de una banda (centro en la esquina: arriba a la derecha se ve el cuadrante inferior izquierdo
    del dibujo, abajo a la derecha el superior izquierdo). Los satélites van pegados al borde de la banda, dentro del margen derecho
    reservado para la decoración, para que nunca queden encima de un texto; estática."""
    arcos = ("<g stroke='#%s' stroke-opacity='.55' stroke-width='1.8' stroke-dasharray='.1 6' stroke-linecap='round'>"
             "<circle cx='90' cy='90' r='40'/><circle cx='90' cy='90' r='62'/><circle cx='90' cy='90' r='84'/></g>" % c)
    sats = ("<g stroke='#%s' stroke-width='2'><circle cx='80' cy='151.4' r='7' fill='#%s'/><circle cx='50.6' cy='99' r='6' fill='#%s'/>"
            "<circle cx='80' cy='28.6' r='7' fill='#%s'/><circle cx='50.6' cy='81' r='6' fill='#%s'/></g>" % (c, sat1, sat2, sat2, sat1))
    return "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 180 180' fill='none'>" + arcos + sats + "</svg>"


ZONAS = {"pr": ("6E9A12", "CFFF5E", "47D985"), "kb": ("3B4FB4", "FFC93C", "8FA8FF"), "cm": ("0E8FAD", "B58CFF", "FFC93C"),
         "ly": ("C77A10", "FF7A59", "FFC93C"), "hm": ("1F9A55", "CFFF5E", "47D985")}


def roseta() -> str:
    el = "".join("<ellipse cx='600' cy='600' rx='330' ry='100' transform='rotate(%d 600 600)' fill='none' stroke='#1C2A6B' stroke-opacity='.3' stroke-width='2.4' stroke-dasharray='.1 13' stroke-linecap='round'/>" % g
                 for g in range(0, 180, 15))
    return "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 1200 1200' fill='none'>%s</svg>" % el


def main():
    # bg-orbitas.webp (fondo de la portada) está retocado a mano (sin el satélite lima): este script NO lo regenera.
    trabajos = [  # nombre, svg, lado en px (2x del mayor tamaño de uso)
        ("guil", fuente("guil"), 288), ("guil-l", fuente("guil-l"), 640),
        ("ap-halo", halo(), 460), ("bg-roseta", roseta(), 1600),
        *[("zona-" + k, zona(*v), 360) for k, v in ZONAS.items()],
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
