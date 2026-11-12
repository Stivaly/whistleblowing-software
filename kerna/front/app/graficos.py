"""Gráficos SVG en línea (sin JavaScript) y trazados para los indicadores: velocímetro, tendencia y barras del informe."""
from __future__ import annotations

import math

from markupsafe import Markup, escape


def g_arc(a: float, b: float, r: float = 38, gap: float = .006) -> str:
    """Arco del velocímetro entre las fracciones a y b (0 a 1) de un semicírculo de centro (50,50)."""
    def P(fr):
        t = math.pi * (1 - fr)
        return f"{50 + r * math.cos(t):.2f}", f"{50 - r * math.sin(t):.2f}"
    p0, p1 = P(a + (gap if a > 0 else 0)), P(b - (gap if b < 1 else 0))
    return f"M{p0[0]} {p0[1]}A{r} {r} 0 0 1 {p1[0]} {p1[1]}"


def g_tick(fr: float) -> dict:
    """Marca de la meta en el velocímetro: extremos de la raya y posición de la etiqueta."""
    t = math.pi * (1 - fr)
    c, s = math.cos(t), math.sin(t)
    q = lambda r: (f"{50 + r * c:.2f}", f"{50 - r * s:.2f}")  # noqa: E731
    a, b, l = q(31), q(45), q(48)
    return {"x1": a[0], "y1": a[1], "x2": b[0], "y2": b[1], "tx": l[0], "ty": l[1]}


def spark(a: list[float]) -> str:
    """Trazado de la línea de tendencia en un lienzo de 100 x 30."""
    if not a:
        return ""
    if len(a) == 1:
        a = [a[0], a[0]]
    mx, mn = max(a), min(a)
    r = (mx - mn) or 1
    return " ".join(f"{'L' if i else 'M'}{i / (len(a) - 1) * 100:.1f} {27 - (v - mn) / r * 24:.1f}" for i, v in enumerate(a))


def spark_area(a: list[float]) -> str:
    return spark(a) + " L100 30 L0 30Z" if a else ""


def _num(v) -> str:
    t = f"{v:,.4g}" if v != int(v) else f"{int(v):,}"
    return t.replace(",", "§").replace(".", ",").replace("§", ".")


def barras_h(items: list[tuple[str, float]], ancho: int = 560) -> Markup:
    """items: (etiqueta, valor). Barras con el color de la marca; la mayor en azul intenso."""
    if not items or not any(v for _, v in items):
        return Markup('<p class="muted" style="margin:0;font-size:13px">Sin datos en el rango.</p>')
    mx = max(v for _, v in items) or 1
    alto, fila = len(items) * 30 + 4, 30
    p = [f'<svg class="gf" viewBox="0 0 {ancho} {alto}" role="img" aria-label="Gráfico de barras">']
    for i, (et, v) in enumerate(items):
        y = i * fila + 4
        w = max(2, (ancho - 270) * v / mx) if v else 0
        cl = "gf-b gf-m" if v == mx else "gf-b"
        p.append(f'<text class="gf-t" x="0" y="{y + 15}">{escape(et)}</text><rect class="{cl}" x="200" y="{y + 3}" width="{w:.1f}" height="16" rx="2"/>'
                 f'<text class="gf-v" x="{208 + w:.1f}" y="{y + 15}">{_num(v)}</text>')
    p.append("</svg>")
    return Markup("".join(p))


def barras_v(items: list[tuple[str, float]], ancho: int = 560, alto: int = 180) -> Markup:
    if not items or not any(v for _, v in items):
        return Markup('<p class="muted" style="margin:0;font-size:13px">Sin datos en el rango.</p>')
    mx = max(v for _, v in items) or 1
    n = len(items)
    paso = (ancho - 20) / n
    ba = min(28, paso * 0.7)
    p = [f'<svg class="gf" viewBox="0 0 {ancho} {alto + 28}" role="img" aria-label="Gráfico de barras por día"><line class="gf-l" x1="10" y1="{alto}" x2="{ancho - 10}" y2="{alto}"/>']
    for i, (et, v) in enumerate(items):
        h = (alto - 22) * v / mx
        x = 10 + i * paso + (paso - ba) / 2
        p.append(f'<rect class="gf-b" x="{x:.1f}" y="{alto - h:.1f}" width="{ba:.1f}" height="{h:.1f}" rx="2"/><text class="gf-v" x="{x + ba / 2:.1f}" y="{alto - h - 4:.1f}" text-anchor="middle">{_num(v)}</text>')
        if n <= 12 or i % max(1, n // 8) == 0:
            p.append(f'<text class="gf-t" x="{x + ba / 2:.1f}" y="{alto + 16}" text-anchor="middle">{escape(str(et)[5:] if len(str(et)) > 8 else et)}</text>')
    p.append("</svg>")
    return Markup("".join(p))


def icono(nombre: str, clave: str | None = None) -> Markup:
    """Ícono de Lucide desde el sprite local (estaticos/iconos.svg), dentro de <k-ic>. `clave` lo deja actualizable en vivo (data-i)."""
    di = f' data-i="{escape(clave)}"' if clave else ""
    return Markup(f'<k-ic n="{escape(nombre)}" aria-hidden="true"><svg aria-hidden="true" focusable="false"><use{di} href="/estaticos/iconos.svg#{escape(nombre)}"/></svg></k-ic>')


FUNCIONES = {"barras_h": barras_h, "barras_v": barras_v, "ic": icono, "g_arc": g_arc, "g_tick": g_tick, "spark": spark, "spark_area": spark_area}
