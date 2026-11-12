"""Gráficos SVG en línea (sin JavaScript ni librerías): barras horizontales y verticales con los colores de Núcleo."""
from __future__ import annotations

from markupsafe import Markup, escape

AZUL, LIMA, LINEA, SEC = "#1C2A6B", "#CFFF5E", "#DCE1EC", "#4A5578"


def barras_h(items: list[tuple[str, float]], ancho: int = 560) -> Markup:
    """items: (etiqueta, valor). Barra azul; la mayor lleva relleno lima con borde."""
    if not items or not any(v for _, v in items):
        return Markup('<p class="vacio">Sin datos en el rango.</p>')
    mx = max(v for _, v in items) or 1
    alto, fila = len(items) * 34 + 4, 34
    p = [f'<svg viewBox="0 0 {ancho} {alto}" role="img" aria-label="Gráfico de barras">']
    for i, (et, v) in enumerate(items):
        y = i * fila + 4
        w = max(2, (ancho - 260) * v / mx) if v else 0
        rel = LIMA if v == mx else "#fff"
        p.append(f'<text x="0" y="{y + 17}" font-size="12" fill="{AZUL}">{escape(et)}</text>'
                 f'<rect x="200" y="{y + 4}" width="{w:.1f}" height="18" fill="{rel}" stroke="{AZUL}" stroke-width="1.5"/>'
                 f'<text x="{208 + w:.1f}" y="{y + 18}" font-size="12" fill="{SEC}">{int(v):,}</text>'.replace(",", "."))
    p.append("</svg>")
    return Markup("".join(p))


def barras_v(items: list[tuple[str, float]], ancho: int = 560, alto: int = 180) -> Markup:
    if not items or not any(v for _, v in items):
        return Markup('<p class="vacio">Sin datos en el rango.</p>')
    mx = max(v for _, v in items) or 1
    n = len(items)
    paso = (ancho - 20) / n
    ba = min(28, paso * 0.7)
    p = [f'<svg viewBox="0 0 {ancho} {alto + 28}" role="img" aria-label="Casos por día">'
         f'<line x1="10" y1="{alto}" x2="{ancho - 10}" y2="{alto}" stroke="{LINEA}"/>']
    for i, (et, v) in enumerate(items):
        h = (alto - 22) * v / mx
        x = 10 + i * paso + (paso - ba) / 2
        p.append(f'<rect x="{x:.1f}" y="{alto - h:.1f}" width="{ba:.1f}" height="{h:.1f}" fill="{LIMA}" stroke="{AZUL}" stroke-width="1.5"/>'
                 f'<text x="{x + ba / 2:.1f}" y="{alto - h - 4:.1f}" font-size="10" text-anchor="middle" fill="{SEC}">{int(v)}</text>')
        if n <= 12 or i % max(1, n // 8) == 0:
            p.append(f'<text x="{x + ba / 2:.1f}" y="{alto + 16}" font-size="10" text-anchor="middle" fill="{SEC}">{escape(et[5:])}</text>')
    p.append("</svg>")
    return Markup("".join(p))


FUNCIONES = {"barras_h": barras_h, "barras_v": barras_v}
