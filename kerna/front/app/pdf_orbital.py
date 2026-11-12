"""Las visuales orbitales de la vista (orbital.py) dibujadas como vector en el PDF con reportlab: diagrama del período, camino de una denuncia,
anillos por ley, cascada y proyección. La geometría del diagrama sale de `orbital.geometria_orbital`, la misma que arma el SVG de la pantalla,
y los colores son los de la paleta B (kerna.css). Se dibujan al generar el PDF porque los datos cambian en cada informe."""
from __future__ import annotations

import math

from reportlab.lib.colors import HexColor
from reportlab.platypus import Flowable

from . import orbital

CAT = {"lima": "#6D883F", "verde": "#328960", "azul": "#4E65A1", "amarillo": "#997B30", "naranja": "#99603A", "coral": "#994544", "cian": "#328494", "violeta": "#6E58A1"}
CAT_BG = {"lima": "#F8FFE7", "verde": "#E4FAEE", "azul": "#ECF1FF", "amarillo": "#FFF7E2", "naranja": "#FFF0E4", "coral": "#FFE9E7", "cian": "#E5F9FC", "violeta": "#F4EEFF"}
ESTADO = {"ok": "#2E8D5C", "warn": "#9F7C22", "bad": "#A4403A", "na": "#8E9AD0"}
TINTA, SEC, BASE, PUNTOS = HexColor("#1C2A6B"), HexColor("#4A5578"), HexColor("#E3E7F2"), HexColor("#B9C1DA")


def _c(h: str):
    return HexColor(h)


class _Base(Flowable):
    """Visual dibujada con medidas lógicas (`self.lw` de ancho) y ampliada `k` veces para llenar la página."""

    def __init__(self, ancho: float, alto: float, k: float = 1.0):
        super().__init__()
        self.k, self.lw = k, ancho / k
        self.width, self.height = ancho, alto * k

    def wrap(self, aw, ah):
        return self.width, self.height

    def draw(self):
        self.canv.saveState()
        self.canv.scale(self.k, self.k)
        self._dibujar()
        self.canv.restoreState()


def _centrado(c, x, y, texto, fuente, tam, color):
    c.setFont(fuente, tam)
    c.setFillColor(color)
    c.drawCentredString(x, y, texto)


def _lineas(texto: str, n: int = 14) -> list[str]:
    """Parte una etiqueta en hasta dos líneas por palabras."""
    pal, a, b = str(texto).split(), "", ""
    for p in pal:
        if len(a) + len(p) + (1 if a else 0) <= n or not a:
            a = (a + " " + p).strip()
        else:
            b = (b + " " + p).strip()
    return [x for x in (a, b) if x]


class Orbital(_Base):
    """Diagrama orbital: núcleo con el total, un anillo por categoría con su arco y su satélite; a la derecha, la leyenda con las cifras."""

    def __init__(self, anillos: list[dict], total: str, unidad: str, ancho: float, k: float = 1.0):
        self.g, self.k, self.total, self.unidad = orbital.geometria_orbital(anillos, total), k, total, unidad
        super().__init__(ancho, self.g["h"] * k)
        self.k = k

    def draw(self):
        c, g, k = self.canv, self.g, self.k
        X, Y = (lambda x: x * k), (lambda y: (g["h"] - y) * k)
        cx, cy = X(g["cx"]), Y(g["cy"])
        for a in g["anillos"]:
            r, col = a["r"] * k, _c(CAT[a["c"]])
            c.saveState()
            c.setStrokeColor(PUNTOS); c.setLineWidth(.9); c.setLineCap(1); c.setDash(.1, 3.4)
            c.circle(cx, cy, r, stroke=1, fill=0)
            c.restoreState()
            c.saveState()
            c.setStrokeColor(col); c.setLineWidth(7 * k); c.setLineCap(1)
            c.arc(cx - r, cy - r, cx + r, cy + r, 90 - math.degrees(a["fin"]), min(a["frac"], .9999) * 360)
            c.restoreState()
            c.setFillColor(_c(CAT_BG[a["c"]])); c.setStrokeColor(col); c.setLineWidth(2 * k)
            c.circle(X(a["sx"]), Y(a["sy"]), a["rs"] * k, stroke=1, fill=1)
            _centrado(c, X(a["sx"]), Y(a["sy"] + 3.4), a["txt"], "Mono", (8.6 if len(a["txt"]) <= 3 else 6.6 if len(a["txt"]) <= 5 else 5.4) * k, _c("#0B1020"))
        c.setFillColor(_c("#FFFFFF")); c.setStrokeColor(PUNTOS); c.setLineWidth(.8)
        c.circle(cx, cy, g["nuc"] * k, stroke=1, fill=1)
        grande = g["grande"]
        _centrado(c, cx, Y(g["cy"] + (3 if grande else 2)), self.total, "Unbounded", g["fs"] * k, TINTA)
        _centrado(c, cx, Y(g["cy"] + (17 if grande else 14)), self.unidad.upper(), "Mono", 6.4 * k, SEC)
        # leyenda directa a la derecha del diagrama
        x0, y = g["w"] * k + 22, self.height / 2 + len(g["anillos"]) * 13
        for a in g["anillos"]:
            col = _c(CAT[a["c"]])
            c.setFillColor(_c(CAT_BG[a["c"]])); c.setStrokeColor(col); c.setLineWidth(1.6)
            c.circle(x0 + 11, y, 11, stroke=1, fill=1)
            _centrado(c, x0 + 11, y - 3, a["txt"], "Mono", 7.4 if len(a["txt"]) <= 3 else 6 if len(a["txt"]) <= 5 else 4.9, _c("#0B1020"))
            c.setFont("Unbounded-M", 8.5); c.setFillColor(TINTA); c.drawString(x0 + 28, y + 1, a["n"])
            if a.get("sub"):
                c.setFont("Mono", 7); c.setFillColor(SEC); c.drawString(x0 + 28, y - 9, a["sub"])
            y -= 30


class Camino(_Base):
    """El camino de una denuncia: satélites sobre una órbita horizontal; el tamaño crece con la raíz del valor y el más lento va en coral."""

    def __init__(self, items: list[dict], ancho: float, k: float = 1.0):
        super().__init__(ancho, 74, k)
        self.alto, self.items = 74, items

    def _dibujar(self):
        c, it = self.canv, self.items
        n = len(it) or 1
        mx = max((i["v"] for i in it), default=0) or 1
        yc = 46
        c.saveState(); c.setStrokeColor(PUNTOS); c.setLineWidth(1.1); c.setLineCap(1); c.setDash(.1, 3.2); c.line(0, yc, self.lw, yc); c.restoreState()
        for j, i in enumerate(it):
            x = (j + .5) * self.lw / n
            d = (14 + 34 * math.sqrt(max(i["v"], 0) / mx)) * .62
            col = i.get("hot") and "coral" or i["c"]
            c.setFillColor(_c("#FFFFFF")); c.circle(x, yc, d / 2 + 3, stroke=0, fill=1)
            c.setFillColor(_c(CAT_BG[col])); c.setStrokeColor(_c(CAT[col])); c.setLineWidth(1.8)
            c.circle(x, yc, d / 2, stroke=1, fill=1)
            c.setFillColor(_c(CAT[col])); c.circle(x, yc, d * .16, stroke=0, fill=1)
            _centrado(c, x, 21, i["txt"], "Unbounded", 8.2, TINTA)
            for m, ln in enumerate(_lineas(i["n"], 12)[:2]):
                _centrado(c, x, 11 - m * 7.5, ln, "Mono", 6.4, SEC)


class AnillosLey(_Base):
    """Un anillo de acierto por ley, con la marca de la meta y el porcentaje al centro con el color de su estado."""

    def __init__(self, items: list[dict], meta: float, ancho: float, k: float = 1.0):
        super().__init__(ancho, 86, k)
        self.alto, self.items, self.meta = 86, items, meta

    def _dibujar(self):
        c = self.canv
        n = len(self.items) or 1
        paso = min(self.lw / n, 120)
        for j, i in enumerate(self.items):
            cx, cy, r = paso * (j + .5), 54, 24
            col = _c(ESTADO[i["e"]])
            c.setStrokeColor(BASE); c.setLineWidth(6); c.circle(cx, cy, r, stroke=1, fill=0)
            f = max(0.0, min(100.0, i["pct"])) / 100
            if f > 0:
                c.saveState(); c.setStrokeColor(col); c.setLineWidth(6); c.setLineCap(1)
                c.arc(cx - r, cy - r, cx + r, cy + r, 90 - f * 360, min(f, .9999) * 360)
                c.restoreState()
            t = self.meta / 100 * 2 * math.pi
            c.setStrokeColor(_c("#0B1020")); c.setLineWidth(2)
            c.line(cx + (r - 6) * math.sin(t), cy + (r - 6) * math.cos(t), cx + (r + 6) * math.sin(t), cy + (r + 6) * math.cos(t))
            _centrado(c, cx, cy - 3, i["txt"], "Unbounded", 7.6, col)
            _centrado(c, cx, 14, i["n"].split(" · ")[0], "Unbounded-M", 6.8, TINTA)
            segundo = i["n"].split(" · ")[1] if " · " in i["n"] else ""
            if segundo:
                _centrado(c, cx, 5, segundo, "Mono", 6.4, SEC)


class Cascada(_Base):
    """Del ingreso a la utilidad: ingreso en verde, descuentos en coral, resultado con el color de su estado; conectores punteados entre pasos."""

    def __init__(self, d: dict, ancho: float, alto: float = 128, k: float = 1.0):
        super().__init__(ancho, alto, k)
        self.alto, self.d = alto, d

    def _dibujar(self):
        c, d = self.canv, self.d
        n = len(d["labels"])
        base_y = 28                                  # reserva de las etiquetas del eje
        top = max(b + s for b, s in zip(d["bp"], d["sp"])) or 1
        bot = min(b + s for b, s in zip(d["bn"], d["sn"]))
        esc = (self.alto - base_y - 14 - 11) / max(top - min(bot, 0), 1e-9)
        y0 = base_y + 11 + (-min(bot, 0)) * esc      # nivel del cero
        paso, bw = self.lw / n, min(self.lw / n * .62, 46)
        col = {"ok": "#328960", "coral": "#994544", "bad": "#A4403A"}
        for i in range(n):
            x = paso * (i + .5)
            for lo, hi in ((d["bp"][i], d["bp"][i] + d["sp"][i]), (d["bn"][i] + d["sn"][i], d["bn"][i])):
                if hi - lo > 1e-9:
                    c.setFillColor(_c(col[d["cols"][i]])); c.rect(x - bw / 2, y0 + lo * esc, bw, max((hi - lo) * esc, 1.6), stroke=0, fill=1)
            alto_v = d["bp"][i] + d["sp"][i]
            abajo = d["bn"][i] + d["sn"][i] < -1e-9 and d["sp"][i] <= 1e-9
            _centrado(c, x, (y0 + (d["bn"][i] + d["sn"][i]) * esc - 9) if abajo else (y0 + alto_v * esc + 3), d["vals"][i], "Unbounded-M", 6.8, TINTA)
            for m, ln in enumerate(_lineas(d["labels"][i], 11)[:3]):
                _centrado(c, x, base_y - 9 - m * 7.2, ln, "Mono", 6, SEC)
        c.saveState(); c.setStrokeColor(PUNTOS); c.setLineWidth(.6); c.line(0, y0, self.lw, y0)
        c.setDash(1.5, 2.5)
        for i, nv in enumerate(d["niv"][:-1]):
            c.line(paso * (i + .5) + bw / 2, y0 + nv * esc, paso * (i + 1.5) - bw / 2, y0 + nv * esc)
        c.restoreState()


class Proyeccion(_Base):
    """Ingresos, costos y utilidad de cada año de la proyección, con el número de clientes sobre cada año."""

    def __init__(self, anios: list[dict], ancho: float, alto: float = 130, k: float = 1.0):
        super().__init__(ancho, alto, k)
        self.alto, self.a = alto, anios

    def _dibujar(self):
        c, a = self.canv, self.a
        n = len(a)
        top = max(max(x["ventas"], x["costos"], x["utilidad"]) for x in a) or 1
        bot = min(0, min(x["utilidad"] for x in a))
        base_y, tope = 14, 26
        esc = (self.alto - base_y - tope) / max(top - bot, 1e-9)
        y0 = base_y + (-bot) * esc
        paso = self.lw / n
        bw = min(paso / 4.2, 16)
        cols = ("#328960", "#994544", "#4E65A1")
        x_leg = 0
        for nom, col in zip(("Ingresos (UF)", "Costos", "Utilidad"), cols):
            c.setFillColor(_c(col)); c.rect(x_leg, self.alto - 7, 8, 5, stroke=0, fill=1)
            c.setFont("Mono", 6.6); c.setFillColor(TINTA); c.drawString(x_leg + 11, self.alto - 7, nom)
            x_leg += 78
        c.setStrokeColor(PUNTOS); c.setLineWidth(.6); c.line(0, y0, self.lw, y0)
        for i, x in enumerate(a):
            cx = paso * (i + .5)
            for j, (v, col) in enumerate(zip((x["ventas"], x["costos"], x["utilidad"]), cols)):
                bx = cx + (j - 1.5) * bw
                c.setFillColor(_c(col)); c.rect(bx, y0 + min(v, 0) * esc, bw, max(abs(v) * esc, .8), stroke=0, fill=1)
            _centrado(c, cx, y0 + max(x["ventas"], x["costos"], x["utilidad"]) * esc + 3, f"{x['cl']} clientes", "Mono", 6.3, SEC)
            _centrado(c, cx, 3, x["a"], "Mono", 6.8, TINTA)
