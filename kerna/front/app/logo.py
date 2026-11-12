"""Símbolo guilloché de Kerna dibujado a mano (PNG con Pillow y vector con reportlab), sin renderizador SVG."""
from __future__ import annotations

import io
import math

AZUL, LIMA = "#1C2A6B", "#CFFF5E"
ROT = range(15, 180, 15)  # 11 elipses punteadas; la elipse sólida va en 0°


def _punteada(cx, cy, rx, ry, rot_deg, paso=2.3):
    """Puntos equiespaciados (aprox.) sobre una elipse rotada, en coordenadas del símbolo (viewBox 0..64)."""
    n = max(8, int(2 * math.pi * (rx + ry) / 2 / paso))
    c, s = math.cos(math.radians(rot_deg)), math.sin(math.radians(rot_deg))
    for i in range(n):
        t = 2 * math.pi * i / n
        x, y = rx * math.cos(t), ry * math.sin(t)
        yield cx + x * c - y * s, cy + x * s + y * c


def png(px: int = 480) -> bytes:
    from PIL import Image, ImageDraw
    k = 4
    S = px * k
    im = Image.new("RGBA", (S, S), (255, 255, 255, 0))
    d = ImageDraw.Draw(im)
    u = S / 66.0

    def P(x, y):
        return (x + 1) * u, (y + 1) * u

    def disco(x, y, r, fill, borde=None, w=0):
        X, Y = P(x, y)
        d.ellipse([X - r * u, Y - r * u, X + r * u, Y + r * u], fill=fill, outline=borde, width=int(w * u))

    for x, y in _punteada(32, 32, 30.5, 30.5, 0, 2.5):
        disco(x, y, .45, AZUL)
    for r in ROT:
        for x, y in _punteada(32, 32, 27, 8, r):
            disco(x, y, .38, AZUL)
    pts = [P(*q) for q in _punteada(32, 32, 27, 8, 0, 0.3)]
    d.line(pts + pts[:1], fill=AZUL, width=int(1.6 * u), joint="curve")
    disco(59, 32, 3.8, LIMA, AZUL, 1.6)
    disco(32, 32, 5.4, AZUL)
    disco(32, 32, 2, LIMA)
    out = io.BytesIO()
    im.resize((px, px), Image.LANCZOS).save(out, "PNG")
    return out.getvalue()


def dibujar(c, x, y, tam):
    """Dibuja el símbolo en un canvas de reportlab con esquina inferior izquierda (x, y) y lado `tam` (puntos)."""
    from reportlab.lib.colors import HexColor
    az, li = HexColor(AZUL), HexColor(LIMA)
    u = tam / 66.0

    def P(px, py):
        return x + (px + 1) * u, y + tam - (py + 1) * u

    def disco(px, py, r, rel, borde=None, w=0):
        X, Y = P(px, py)
        c.setFillColor(rel)
        if borde:
            c.setStrokeColor(borde); c.setLineWidth(w * u)
        c.circle(X, Y, r * u, stroke=1 if borde else 0, fill=1)

    for px, py in _punteada(32, 32, 30.5, 30.5, 0, 2.5):
        disco(px, py, .45, az)
    for r in ROT:
        for px, py in _punteada(32, 32, 27, 8, r):
            disco(px, py, .38, az)
    pts = [P(*q) for q in _punteada(32, 32, 27, 8, 0, 0.3)]
    c.setStrokeColor(az); c.setLineWidth(1.6 * u)
    p = c.beginPath(); p.moveTo(*pts[0])
    for q in pts[1:]:
        p.lineTo(*q)
    p.close(); c.drawPath(p, stroke=1, fill=0)
    disco(59, 32, 3.8, li, az, 1.6)
    disco(32, 32, 5.4, az)
    disco(32, 32, 2, li)
