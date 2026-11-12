"""Visuales de la identidad Núcleo generadas en el servidor (SVG o HTML ligero, estáticos, sin JavaScript ni animaciones).

- diagrama_orbital: núcleo con el total y un anillo por categoría; cada anillo lleva un arco proporcional y un satélite con la cifra.
- camino: satélites sobre una órbita horizontal; el tamaño de cada uno es proporcional al dato.
- anillos_ley: un múltiplo pequeño por ley (ícono de ley, anillo de acierto con la marca de la meta).
- capacidad: anillo del uso de un plan; lo que pasa de 100 % sale como satélite fuera del anillo.
Los colores salen de la paleta B (variables --c-* de kerna.css, generadas por herramientas/construir_identidad.py).
"""
from __future__ import annotations

import math
import re

from markupsafe import Markup, escape

# Significado fijo de cada color en todo el panel (paleta B).
COLOR_MODO = {"oficial": "verde", "respaldo": "amarillo", "local": "cian", "manual": "coral"}
COLOR_ETAPA = {"anonimizacion": "lima", "clasificacion": "azul", "recuperacion": "cian", "generacion": "violeta", "validacion": "naranja"}
COLOR_LEY = {"karin": "lima", "datos": "azul", "penal": "violeta"}
CICLO = ["azul", "violeta", "cian", "naranja", "lima", "verde", "amarillo", "coral"]
NOMBRE_LEY = {"karin": "Ley Karin", "datos": "Datos personales", "penal": "Responsabilidad penal"}


def ley_tipo(norma: str) -> str | None:
    """Ley Karin (21.643), datos personales (19.628, 21.719) o responsabilidad penal (20.393); None si es otra norma."""
    n = str(norma)
    if re.search(r"21\.?643|karin", n, re.I):
        return "karin"
    if re.search(r"19\.?628|21\.?719|datos", n, re.I):
        return "datos"
    if re.search(r"20\.?393|penal|jur[ií]dic", n, re.I):
        return "penal"
    return None


def ley_icono(norma: str, px: int = 24) -> Markup:
    t = ley_tipo(norma)
    if not t:
        return Markup("")
    return Markup(f'<span class="lx" data-l="{t}" style="--s:{px}px" aria-hidden="true"><svg focusable="false"><use href="/estaticos/identidad.svg#l-{t}"/></svg></span>')


def _p(x: float) -> str:
    return f"{x:.1f}"


def _punto(cx: float, cy: float, r: float, t: float) -> tuple[float, float]:
    """Punto de la circunferencia a `t` radianes de las 12 en punto, en sentido horario."""
    return cx + r * math.sin(t), cy - r * math.cos(t)


def _arco(cx: float, cy: float, r: float, frac: float, fin: float = 0.0) -> str:
    """Arco de `frac` (0 a 1) de la circunferencia que termina a `fin` radianes de las 12 en punto (sentido horario)."""
    if frac <= 0:
        return ""
    if frac >= .999:
        x0, y0 = _punto(cx, cy, r, fin)
        x1, y1 = _punto(cx, cy, r, fin + math.pi)
        return f"M{_p(x0)},{_p(y0)} A{_p(r)},{_p(r)} 0 1 1 {_p(x1)},{_p(y1)} A{_p(r)},{_p(r)} 0 1 1 {_p(x0)},{_p(y0)}"
    x0, y0 = _punto(cx, cy, r, fin - frac * 2 * math.pi)
    x1, y1 = _punto(cx, cy, r, fin)
    return f"M{_p(x0)},{_p(y0)} A{_p(r)},{_p(r)} 0 {1 if frac > .5 else 0} 1 {_p(x1)},{_p(y1)}"


def angulos_satelites(n: int) -> list[float]:
    """Ángulo (radianes desde las 12, sentido horario) donde termina el arco de cada anillo: repartidos en la vuelta para que los satélites no se amontonen."""
    return [math.radians(50 + i * 360 / max(n, 1)) for i in range(n)]


def diagrama_orbital(anillos: list[dict], total: str, unidad: str, etiqueta_total: str = "") -> Markup:
    """anillos: [{n: texto corto, v: valor, txt: cifra del satélite, c: color de categoría}] (el primero es el anillo exterior).
    El arco de cada anillo es su parte del total de los valores y termina en un satélite con la cifra; los satélites
    quedan repartidos a lo largo de sus anillos. Los nombres van en una leyenda directa al lado, sin tocar el dibujo."""
    anillos = [a for a in anillos if a["v"] > 0] or anillos[:1]
    tot = sum(a["v"] for a in anillos) or 1
    cx, cy, w, h = 130.0, 118.0, 260, 236
    paso = 22 if len(anillos) <= 3 else 19
    r0 = 106.0
    rs = [r0 - i * paso for i in range(len(anillos))]
    nuc = max(rs[-1] - 21, 24)
    o = [f'<svg class="orb" viewBox="0 0 {w} {h}" role="img" aria-label="{escape(etiqueta_total or unidad)}: {escape(total)}">']
    lg = []
    for a, r, fin in zip(anillos, rs, angulos_satelites(len(anillos))):
        c = a["c"]
        o.append(f'<circle cx="{cx}" cy="{cy}" r="{_p(r)}" class="orb-b"/>')
        frac = max(a["v"] / tot, .012)
        o.append(f'<path d="{_arco(cx, cy, r, frac, fin)}" class="orb-a" style="stroke:var(--c-{c})"/>')
        sx, sy = _punto(cx, cy, r, fin)
        o.append(f'<circle cx="{_p(sx)}" cy="{_p(sy)}" r="12" class="orb-s" style="fill:var(--c-{c}-bg);stroke:var(--c-{c})"/>'
                 f'<text x="{_p(sx)}" y="{_p(sy + 3.4)}" class="orb-n" text-anchor="middle">{escape(a["txt"])}</text>')
        lg.append(f'<li style="--c:var(--c-{c});--cb:var(--c-{c}-bg)"><i aria-hidden="true">{escape(a["txt"])}</i><span>{escape(a["n"])}</span></li>')
    o.append(f'<circle cx="{cx}" cy="{cy}" r="{_p(nuc)}" class="orb-c"/>')
    grande = len(str(total)) <= 4 and nuc > 34
    o.append(f'<text x="{cx}" y="{_p(cy + (3 if grande else 2))}" class="orb-t" style="font-size:{26 if grande else 17}px" text-anchor="middle">{escape(total)}</text>'
             f'<text x="{cx}" y="{_p(cy + (17 if grande else 14))}" class="orb-u" text-anchor="middle">{escape(unidad)}</text></svg>')
    return Markup(f'<div class="orb-w">{"".join(o)}<ul class="orb-lg">{"".join(lg)}</ul></div>')


def camino(items: list[dict], maximo: float | None = None) -> Markup:
    """items: [{n: etiqueta, v: valor, txt: texto bajo el satélite, c: color de categoría, hot: bool}].
    Satélites sobre una órbita horizontal; el diámetro crece con la raíz del valor."""
    mx = maximo or max((i["v"] for i in items), default=0) or 1
    li = []
    for i in items:
        d = 14 + 34 * math.sqrt(max(i["v"], 0) / mx)
        c = "coral" if i.get("hot") else i["c"]
        li.append(f'<li style="--d:{_p(d)}px;--c:var(--c-{c});--cb:var(--c-{c}-bg)"><i aria-hidden="true"></i><b>{escape(i["txt"])}</b><span>{escape(i["n"])}</span></li>')
    return Markup(f'<ol class="cm">{"".join(li)}</ol>')


def anillo(pct: float | None, estado: str, meta: float | None = None, px: int = 64, texto: str | None = None) -> Markup:
    """Anillo de porcentaje (0 a 100) del color del estado, con una marca en la meta."""
    r, cx = 26.0, 32.0
    v = 0 if pct is None else max(0.0, min(100.0, pct))
    c = 2 * math.pi * r
    o = [f'<svg class="ani" width="{px}" height="{px}" viewBox="0 0 64 64" aria-hidden="true"><circle cx="{cx}" cy="{cx}" r="{r}" class="ani-b"/>'
         f'<circle cx="{cx}" cy="{cx}" r="{r}" class="ani-a" style="stroke:var(--{estado}-bar);stroke-dasharray:{_p(c * v / 100)} {_p(c)}" transform="rotate(-90 {cx} {cx})"/>']
    if meta is not None:
        a = -math.pi / 2 + meta / 100 * 2 * math.pi
        o.append(f'<line x1="{_p(cx + (r - 5) * math.cos(a))}" y1="{_p(cx + (r - 5) * math.sin(a))}" x2="{_p(cx + (r + 5) * math.cos(a))}" y2="{_p(cx + (r + 5) * math.sin(a))}" class="ani-m"/>')
    o.append(f'<text x="{cx}" y="{cx + 4}" class="ani-t" text-anchor="middle" style="fill:var(--{estado})">{escape(texto if texto is not None else "—")}</text></svg>')
    return Markup("".join(o))


def capacidad(uso: float, estado: str, px: int = 44) -> Markup:
    """Anillo de capacidad de un plan: el arco llega hasta 100 %; el exceso es un satélite coral fuera del anillo."""
    r, cx = 15.0, 22.0
    v = max(0.0, min(100.0, uso))
    c = 2 * math.pi * r
    o = [f'<svg class="ani" width="{px}" height="{px}" viewBox="0 0 44 44" aria-hidden="true"><circle cx="{cx}" cy="{cx}" r="{r}" class="ani-b" style="stroke-width:5"/>'
         f'<circle cx="{cx}" cy="{cx}" r="{r}" class="ani-a" style="stroke-width:5;stroke:var(--{estado}-bar);stroke-dasharray:{_p(c * v / 100)} {_p(c)}" transform="rotate(-90 {cx} {cx})"/>']
    if uso > 100:
        a = -math.pi / 4
        o.append(f'<circle cx="{_p(cx + 19 * math.cos(a))}" cy="{_p(cx + 19 * math.sin(a))}" r="3.6" style="fill:var(--c-coral);stroke:#0B1020;stroke-width:1.2"/>')
    o.append("</svg>")
    return Markup("".join(o))


FUNCIONES = {"diagrama_orbital": diagrama_orbital, "camino": camino, "anillo": anillo, "capacidad": capacidad, "ley_icono": ley_icono, "ley_tipo": ley_tipo}
