"""Dibuja recuadros numerados sobre capturas ya guardadas (las del panel de Kerna).
Uso: python3 anotar.py <carpeta origen> <carpeta destino>
Las cajas están en píxeles de la captura (1366 de ancho), medidas sobre la pantalla real.
"""
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROJO = (229, 38, 42)
FUENTE = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 20)

# nombre: (recorte (x0, y0, x1, y1) o None, [(x0, y0, x1, y1, número), ...])
CAJAS = {
    "k01_acceso": (None, []),
    "k02_resumen": ((0, 0, 1366, 845), [
        (20, 100, 240, 170, 1), (20, 185, 240, 650, 2), (280, 20, 625, 66, 3), (936, 18, 1345, 70, 4),
        (290, 85, 690, 330, 5), (715, 160, 1285, 296, 6), (285, 355, 540, 515, 7), (550, 355, 785, 515, 8),
        (795, 355, 1030, 515, 9), (1040, 355, 1340, 515, 10), (285, 540, 915, 720, 11), (935, 540, 1340, 720, 12),
        (20, 765, 240, 825, 13)]),
    "k03_ayuda": ((280, 350, 1040, 525), [(688, 384, 718, 414, 1)]),
    "k04_informe": ((0, 0, 1366, 870), [
        (280, 18, 920, 64, 1), (925, 18, 1070, 64, 2), (278, 65, 580, 110, 3), (290, 120, 790, 212, 4),
        (285, 232, 1340, 508, 5), (280, 525, 740, 565, 6), (1280, 525, 1340, 565, 7)]),
    "k06_negocio": ((0, 0, 1366, 1010), [
        (400, 20, 610, 64, 1), (290, 80, 640, 250, 2), (650, 90, 1290, 295, 3), (285, 325, 1340, 465, 4),
        (285, 490, 1340, 665, 5), (285, 690, 920, 1000, 6), (930, 690, 1340, 1000, 7)]),
    "k07_clientes": ((0, 0, 1366, 570), [
        (280, 20, 1342, 55, 1), (1180, 62, 1345, 106, 2), (280, 165, 1342, 552, 3), (905, 195, 1090, 552, 4),
        (1100, 200, 1340, 540, 5)]),
    "k08_ajustes": ((0, 0, 1366, 760), [
        (280, 20, 1342, 55, 1), (395, 68, 690, 100, 2), (1133, 64, 1345, 104, 3), (565, 118, 1330, 300, 4),
        (565, 315, 1330, 525, 5), (565, 545, 1330, 620, 6), (565, 640, 1330, 740, 7)]),
}


def caja(d, x0, y0, x1, y1, n):
    for g in range(4):
        d.rounded_rectangle((x0 - g, y0 - g, x1 + g, y1 + g), radius=10, outline=ROJO)
    cx, cy, r = x1 + 2, y0 + 2, 18
    d.ellipse((cx - r - 3, cy - r - 3, cx + r + 3, cy + r + 3), fill="white")
    d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=ROJO)
    d.text((cx, cy), str(n), fill="white", font=FUENTE, anchor="mm")


def main(origen, destino):
    o, s = Path(origen), Path(destino)
    s.mkdir(parents=True, exist_ok=True)
    for png in sorted(o.glob("k*.png")):
        im = Image.open(png).convert("RGB")
        recorte, cajas = CAJAS.get(png.stem, (None, []))
        d = ImageDraw.Draw(im)
        for c in cajas:
            caja(d, *c)
        if recorte:
            im = im.crop((recorte[0], recorte[1], recorte[2], min(recorte[3], im.height)))
        im.save(s / png.name, optimize=True)
        print(png.name, len(cajas), "recuadros")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
