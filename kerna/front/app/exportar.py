"""Exportaciones del informe de gestión: XLSX (openpyxl), CSV largo (csv) y PDF (reportlab, solo Python)."""
from __future__ import annotations

import csv
import io
from pathlib import Path

from . import informe, logo

FUENTES = Path(__file__).parent / "estaticos" / "fuentes" / "ttf"
AZUL, LIMA, LINEA, PAPEL, SEC = "1C2A6B", "CFFF5E", "DCE1EC", "F5F7FB", "4A5578"
ENCABEZADO_CSV = ["seccion", "metrica", "valor", "unidad", "fuente", "fecha_corte"]


def _fmt(v):
    if v is None:
        return "sin datos"
    if isinstance(v, float):
        return f"{v:,.3f}".rstrip("0").rstrip(".").replace(",", "X").replace(".", ",").replace("X", ".")
    if isinstance(v, int) and not isinstance(v, bool):
        return f"{v:,}".replace(",", ".")
    return str(v)


# ---- CSV: un único archivo largo (seccion, metrica, valor, unidad, fuente, fecha_corte) ---------------------------
def a_csv(inf: dict) -> bytes:
    inf = informe.para_mostrar(inf)
    s = io.StringIO()
    w = csv.writer(s, delimiter=";", lineterminator="\r\n")  # ';' y BOM: Excel en español lo abre sin asistente
    w.writerow(ENCABEZADO_CSV)
    for fila in informe.filas_largas(inf):
        w.writerow(fila)
    return ("﻿" + s.getvalue()).encode("utf-8")


# ---- XLSX ---------------------------------------------------------------------------------------------------------
def a_xlsx(inf: dict) -> bytes:
    inf = informe.para_mostrar(inf)
    from openpyxl import Workbook
    from openpyxl.drawing.image import Image as XImage
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    wb = Workbook()
    ws = wb.active
    ws.title = "Resumen"
    borde = Border(bottom=Side(style="thin", color=LINEA))
    titulo = Font(name="Arial", bold=True, size=16, color=AZUL)
    cab = Font(name="Arial", bold=True, color=AZUL)
    relleno = PatternFill("solid", fgColor=LIMA)
    lado = Side(style="thin", color=AZUL)

    def encabezado(hoja, fila, cols):
        for i, c in enumerate(cols, 1):
            x = hoja.cell(row=fila, column=i, value=c)
            x.font, x.fill, x.border = cab, relleno, Border(top=lado, bottom=lado, left=lado, right=lado)
            x.alignment = Alignment(wrap_text=True, vertical="center")

    img = XImage(io.BytesIO(logo.png(160)))
    img.width = img.height = 72
    ws.add_image(img, "A1")
    ws["C1"], ws["C1"].font = inf["meta"]["titulo"], titulo
    ws["C2"] = f"Período: {inf['meta']['periodo']}  ·  Fecha de corte: {inf['meta']['corte']}"
    ws["C2"].font = Font(name="Arial", color=SEC)
    ws["C3"] = "Solo cifras agregadas; sin texto de denuncias ni identificadores."
    ws["C3"].font = Font(name="Arial", italic=True, color=SEC)
    fila = 6
    encabezado(ws, fila, ["Sección", "Métrica", "Valor", "Unidad", "Fuente"])
    for s in inf["secciones"]:
        for k in s["kpis"]:
            fila += 1
            for i, v in enumerate([s["titulo"], k["etiqueta"], "sin datos" if k["valor"] is None else k["valor"], k["unidad"], k["fuente"]], 1):
                c = ws.cell(row=fila, column=i, value=v)
                c.font, c.border = Font(name="Arial"), borde
                c.alignment = Alignment(wrap_text=True, vertical="top", horizontal="right" if i == 3 else "left")
    for col, an in zip("ABCDE", (22, 52, 16, 14, 70)):
        ws.column_dimensions[col].width = an
    ws.freeze_panes = "A7"
    usados = {"Resumen"}
    for s in inf["secciones"]:
        if s["id"] == "resumen":
            hoja = wb.create_sheet("Casos por día")  # el resumen ya está en la primera hoja; se añade su tabla
        else:
            hoja = wb.create_sheet(s["titulo"][:31])
        usados.add(hoja.title)
        hoja["A1"], hoja["A1"].font = s["titulo"], titulo
        hoja["A2"] = s["justificacion"]
        hoja["A2"].font = Font(name="Arial", italic=True, color=SEC)
        f = 4
        if s["kpis"] and s["id"] != "resumen":
            encabezado(hoja, f, ["Métrica", "Valor", "Unidad", "Fuente"])
            for k in s["kpis"]:
                f += 1
                for i, v in enumerate([k["etiqueta"], "sin datos" if k["valor"] is None else k["valor"], k["unidad"], k["fuente"]], 1):
                    hoja.cell(row=f, column=i, value=v).font = Font(name="Arial")
            f += 2
        for t in s["tablas"]:
            hoja.cell(row=f, column=1, value=t["titulo"]).font = Font(name="Arial", bold=True, color=AZUL)
            f += 1
            encabezado(hoja, f, t["cols"])
            for fila_t in t["filas"] or [["sin datos en el período"] + [None] * (len(t["cols"]) - 1)]:
                f += 1
                for i, v in enumerate(fila_t, 1):
                    c = hoja.cell(row=f, column=i, value=v)
                    c.font, c.border = Font(name="Arial"), borde
                    c.alignment = Alignment(wrap_text=True, vertical="top")
            hoja.cell(row=f + 1, column=1, value="Fuente: " + t["fuente"]).font = Font(name="Arial", italic=True, size=9, color=SEC)
            f += 3
        for n in s["notas"]:
            hoja.cell(row=f, column=1, value="Nota: " + n).font = Font(name="Arial", italic=True, color=SEC)
            f += 1
        for j in range(1, 10):
            hoja.column_dimensions[chr(64 + j)].width = 34 if j <= 2 else 18
        hoja.column_dimensions["B"].width = 44
    out = io.BytesIO()
    wb.save(out)
    return out.getvalue()


# ---- PDF ----------------------------------------------------------------------------------------------------------
def a_pdf(inf: dict) -> bytes:
    from reportlab.lib.colors import HexColor
    from reportlab.lib.enums import TA_LEFT
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.platypus import BaseDocTemplate, Flowable, Frame, PageBreak, PageTemplate, Paragraph, Spacer, Table, TableStyle
    from xml.sax.saxutils import escape

    for nombre, arch in (("Unbounded", "unbounded-latin-700-normal.ttf"), ("Unbounded-M", "unbounded-latin-500-normal.ttf"), ("Mono", "jetbrains-mono-latin-500-normal.ttf")):
        if nombre not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont(nombre, str(FUENTES / arch)))
    az, li, ln, sec = HexColor("#" + AZUL), HexColor("#" + LIMA), HexColor("#" + LINEA), HexColor("#" + SEC)
    est = {
        "h1": ParagraphStyle("h1", fontName="Unbounded", fontSize=15, leading=20, textColor=az, spaceBefore=4, spaceAfter=6),
        "h2": ParagraphStyle("h2", fontName="Unbounded-M", fontSize=9.5, leading=13, textColor=az, spaceBefore=10, spaceAfter=3),
        "p": ParagraphStyle("p", fontName="Mono", fontSize=8, leading=11.5, textColor=az, alignment=TA_LEFT),
        "n": ParagraphStyle("n", fontName="Mono", fontSize=7, leading=10, textColor=sec),
        "c": ParagraphStyle("c", fontName="Mono", fontSize=6.8, leading=9, textColor=az),
        "ch": ParagraphStyle("ch", fontName="Unbounded-M", fontSize=6.5, leading=8.5, textColor=az),
    }
    P = lambda t, e="p": Paragraph(escape(str(t)), est[e])  # noqa: E731
    ancho = A4[0] - 36 * mm

    COL = {"neutro": az, "ok": HexColor("#236F4A"), "warn": HexColor("#7C6119"), "bad": HexColor("#84312C"), "na": sec}  # paleta Núcleo (identidad v3), ver kerna.css
    BAR = {"neutro": HexColor("#8E9AD0"), "ok": HexColor("#2E8D5C"), "warn": HexColor("#9F7C22"), "bad": HexColor("#A4403A"), "na": HexColor("#8E9AD0")}
    FON = {"neutro": HexColor("#FFFFFF"), "ok": HexColor("#E6FBEF"), "warn": HexColor("#FFF7E4"), "bad": HexColor("#FFEAE8"), "na": HexColor("#F5F7FB")}
    TXT = {"ok": "Bien", "warn": "Atención", "bad": "Mal", "na": "Sin dato"}

    def marca(c, e, x, y, r=3.2):
        """Ícono de estado: círculo (bien), triángulo (atención), cuadrado (mal), guion (sin dato)."""
        c.setFillColor(COL[e]); c.setStrokeColor(COL[e])
        if e == "neutro":
            return
        if e == "ok":
            c.circle(x, y, r, stroke=0, fill=1)
        elif e == "warn":
            p = c.beginPath(); p.moveTo(x - r, y - r * .8); p.lineTo(x + r, y - r * .8); p.lineTo(x, y + r); p.close(); c.drawPath(p, stroke=0, fill=1)
        elif e == "bad":
            c.rect(x - r, y - r, 2 * r, 2 * r, stroke=0, fill=1)
        else:
            c.setLineWidth(1); c.line(x - r, y, x + r, y)

    class Tarjetas(Flowable):
        """Cuadrícula de cifras con color de estado: etiqueta, valor y estado (semáforo)."""
        def __init__(self, filas, cols=3, alto=26):
            super().__init__()
            self.filas, self.cols, self.alto = filas, cols, alto
            self.nf = -(-len(filas) // cols)
            self.width, self.height = ancho, self.nf * (alto + 3)

        def wrap(self, aw, ah):
            return ancho, self.height

        def draw(self):
            c, w = self.canv, (ancho - (self.cols - 1) * 4) / self.cols
            for i, (et, v, u, e) in enumerate(self.filas):
                x, y = (i % self.cols) * (w + 4), self.height - (i // self.cols + 1) * (self.alto + 3) + 3
                c.setFillColor(FON[e]); c.setStrokeColor(ln); c.setLineWidth(.4); c.rect(x, y, w, self.alto, stroke=1, fill=1)
                c.setFillColor(BAR[e]); c.rect(x, y, 2.4, self.alto, stroke=0, fill=1)
                c.setFont("Mono", 6.3); c.setFillColor(sec); c.drawString(x + 6, y + self.alto - 8.5, et[:int((w - 12) / 3.7)])
                c.setFont("Unbounded", 9.5 if e != "na" else 8); c.setFillColor(COL[e]); c.drawString(x + 6, y + 5, ("—" if e == "na" else v) + (f" {u}" if u and e != "na" else ""))
                if e not in ("na", "neutro"):
                    marca(c, e, x + w - 8, y + 8)

    class Modos(Flowable):
        """Los cuatro modos en una sola barra apilada, con leyenda."""
        def __init__(self, ej):
            super().__init__()
            self.ej = ej
            self.width, self.height = ancho, 44

        def wrap(self, aw, ah):
            return ancho, 44

        def draw(self):
            c, ej = self.canv, self.ej
            c.setFont("Unbounded-M", 7); c.setFillColor(az); c.drawString(0, 35, "Cómo se resolvieron")
            tot = ej["n_modos"]
            if not tot:
                c.setFont("Mono", 7); c.setFillColor(sec); c.drawString(0, 20, "—"); return
            x = 0
            for m in ej["modos"]:
                w = ancho * m["n"] / tot
                if w:
                    c.setFillColor(BAR[m["est"]]); c.rect(x, 20, w, 9, stroke=0, fill=1)
                x += w
            x = 0
            for m in ej["modos"]:
                marca(c, m["est"], x + 3, 9, 2.6)
                c.setFont("Mono", 6.6); c.setFillColor(az)
                c.drawString(x + 9, 6.5, f"{m['t']}: {_fmt(m['n'])} ({m['p']} %)")
                x += ancho / 4

    class Barras(Flowable):
        """Barras horizontales delgadas, etiquetas cortas completas, estado por barra y meta marcada."""
        def __init__(self, g):
            super().__init__()
            self.g, self.b = g, g["barras"]
            self.h = 14 + max(1, len(self.b)) * 11
            self.width, self.height = ancho, self.h

        def wrap(self, aw, ah):
            return ancho, self.h

        def draw(self):
            c, g = self.canv, self.g
            c.setFont("Unbounded-M", 7); c.setFillColor(az); c.drawString(0, self.h - 8, g["titulo"])
            if not self.b:
                c.setFont("Mono", 7); c.setFillColor(sec); c.drawString(0, self.h - 21, "—"); return
            x0, maxw = 150, ancho - 215
            for i, b in enumerate(self.b):
                y = self.h - 21 - i * 11
                c.setFont("Mono", 6.8); c.setFillColor(az); c.drawString(0, y, b["n"][:38])
                c.setFillColor(BAR[b["e"]]); c.rect(x0, y, max(1.2, maxw * b["w"] / 100), 5, stroke=0, fill=1)
                c.setFillColor(COL[b["e"]]); c.drawString(x0 + max(1.2, maxw * b["w"] / 100) + 4, y - .5, b["v"])
            if g.get("meta_pos") is not None:
                xm = x0 + maxw * g["meta_pos"] / 100
                c.setStrokeColor(az); c.setLineWidth(.8); c.line(xm, self.h - 20 - (len(self.b) - 1) * 11 - 2, xm, self.h - 14)

    def pie(c, d):
        c.saveState(); c.setFont("Mono", 6.5); c.setFillColor(sec)
        c.drawString(18 * mm, 10 * mm, f"Kerna AI · Informe de gestión · {inf['meta']['periodo']} · corte {inf['meta']['corte']}")
        c.drawRightString(A4[0] - 18 * mm, 10 * mm, f"Página {d.page}")
        c.setStrokeColor(az); c.setLineWidth(.6); c.line(18 * mm, 14 * mm, A4[0] - 18 * mm, 14 * mm); c.restoreState()

    def cabecera(c, d):
        """Página 1: logo, nombre, título y período arriba; el veredicto y los indicadores van debajo, en el mismo folio."""
        pie(c, d)
        c.saveState()
        logo.dibujar(c, 18 * mm, A4[1] - 38 * mm, 26 * mm)
        c.setFillColor(az); c.setFont("Unbounded", 20); c.drawString(48 * mm, A4[1] - 24 * mm, "KERNA")
        c.setFillColor(li); c.setStrokeColor(az); c.setLineWidth(.8)
        c.rect(88 * mm, A4[1] - 26 * mm, 10 * mm, 6 * mm, stroke=1, fill=1)
        c.setFillColor(az); c.setFont("Unbounded", 6.5); c.drawString(90.4 * mm, A4[1] - 24.2 * mm, "AI")
        c.setFont("Unbounded", 13); c.drawString(48 * mm, A4[1] - 33 * mm, "Informe de gestión")
        c.setFont("Mono", 8); c.setFillColor(sec)
        c.drawString(48 * mm, A4[1] - 39 * mm, f"Período: {inf['meta']['periodo']}  ·  corte {inf['meta']['corte']}")
        c.setStrokeColor(az); c.setLineWidth(.6); c.line(18 * mm, A4[1] - 43 * mm, A4[0] - 18 * mm, A4[1] - 43 * mm)
        c.restoreState()

    out = io.BytesIO()
    doc = BaseDocTemplate(out, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=16 * mm, bottomMargin=20 * mm,
                          title=inf["meta"]["titulo"], author="Kerna AI", subject=f"Período {inf['meta']['periodo']}")
    fr = Frame(18 * mm, 20 * mm, ancho, A4[1] - 36 * mm, id="f", leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
    f1 = Frame(18 * mm, 20 * mm, ancho, A4[1] - 68 * mm, id="f1", leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
    doc.addPageTemplates([PageTemplate(id="primera", frames=[f1], onPage=cabecera, autoNextPageTemplate="normal"),
                          PageTemplate(id="normal", frames=[fr], onPage=pie)])
    from reportlab.platypus import CondPageBreak
    from . import vistas
    secs, ej = vistas.informe(inf), vistas.informe_ejecutivo(inf)
    estilo = TableStyle([("BACKGROUND", (0, 0), (-1, 0), li), ("BOX", (0, 0), (-1, -1), .6, az), ("LINEBELOW", (0, 0), (-1, 0), .6, az), ("LINEBELOW", (0, 1), (-1, -1), .3, ln),
                         ("VALIGN", (0, 0), (-1, -1), "TOP"), ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2), ("LEFTPADDING", (0, 0), (-1, -1), 3), ("RIGHTPADDING", (0, 0), (-1, -1), 3)])
    from reportlab.lib.styles import ParagraphStyle as PS

    def PN(t, e="c", der=False, color=None):
        base = est[e] if not der else PS("r" + e, parent=est[e], alignment=2)
        if color is not None:
            base = PS("k" + e + str(color), parent=base, textColor=color)
        return Paragraph(escape(str(t)), base)

    def tabla(t, filas, ancho_t):
        nc = len(t["cols"])
        cab = [PN(c, "ch", t["nums"][i]) for i, c in enumerate(t["cols"])]
        rows = [[PN(c["t"], "c", c["n"], COL.get(c.get("chip") or "", None) if c.get("chip") else None) for c in r] for r in filas] or [[PN("—")] + [PN("")] * (nc - 1)]
        tb = Table([cab] + rows, colWidths=[ancho_t / nc] * nc, repeatRows=1)
        tb.setStyle(estilo)
        return tb

    # Orden del documento (pirámide invertida): veredicto y KPI con color, luego gráficos por sección y, al final, el anexo con todas las tablas.
    v2 = vistas.informe_v2(inf)
    ver = v2["veredicto"]
    from reportlab.platypus import Image as RImage
    baldosa = Path(__file__).parent / "estaticos" / "img" / f"baldosa-{ver['ico']}.png"
    textos = [P(ver["t"], "h1"), P(ver["n"], "p") if ver["n"] else Spacer(1, 1)]
    fila_v = Table([[RImage(str(baldosa), width=30 * mm, height=22.5 * mm) if baldosa.exists() else "", textos]], colWidths=[36 * mm, ancho - 36 * mm])
    fila_v.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), FON[ver["e"]]), ("LINEBEFORE", (0, 0), (0, -1), 3, BAR[ver["e"]]), ("BOX", (0, 0), (-1, -1), .4, ln),
                                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5), ("LEFTPADDING", (0, 0), (-1, -1), 8)]))
    from . import pdf_orbital as po
    vis = vistas.visuales_pdf(inf)
    h = [fila_v, Spacer(1, 8), Tarjetas([(c["l"], str(c["v"]), (c["u"] or ""), c["e"]) for c in v2["cards"]], cols=3), Spacer(1, 6)]
    if "periodo" in vis:
        pe = vis["periodo"]
        h += [P("Cómo se resolvieron las denuncias", "h2"), po.Orbital(pe["anillos"], pe["total"], pe["unidad"], ancho, k=1.25)]
    else:
        h.append(Modos(ej))
    if "etapas" in vis:
        h += [P("El camino de una denuncia", "h2"), po.Camino(vis["etapas"], ancho, k=1.5)]

    def visual_de(id_):
        """Visual orbital protagonista de la página de cada pestaña (las mismas de la pantalla); devuelve (flowables, títulos de gráficos que reemplaza)."""
        if id_ == "calidad" and "leyes" in vis:
            return [P("Acierto por ley (la marca negra es la meta)", "h2"), po.AnillosLey(vis["leyes"]["items"], vis["leyes"]["meta"], ancho, k=1.7)], ("Recall@5",)
        if id_ == "desempeno" and "etapas" in vis:
            return [P("El camino de una denuncia: 9 de cada 10 casos", "h2"), po.Camino(vis["etapas"], ancho, k=1.7)], ("P95 por etapa",)
        if id_ == "costo" and "tokens" in vis:
            t = vis["tokens"]
            return [P("Costo por modelo (el arco es la parte de los tokens de cada uno)", "h2"), po.Orbital(t["anillos"], t["total"], t["unidad"], ancho, k=1.2)], ("Tokens totales",)
        if id_ == "rentabilidad":
            r = []
            if "cascada" in vis:
                r += [P("Del ingreso a la utilidad (UF)", "h2"), po.Cascada(vis["cascada"], ancho, 150, k=1.25)]
            if "proyeccion" in vis:
                r += [P("Proyección a cinco años (UF)", "h2"), po.Proyeccion(vis["proyeccion"], ancho, 140, k=1.25)]
            return r, ("Utilidad después",)
        if id_ == "incidentes" and ("fallas" in vis or "motivos" in vis):
            r = []
            if "fallas" in vis:
                r += [P("Fallas por proveedor (el tamaño es la cantidad de eventos)", "h2"), po.Camino(vis["fallas"], ancho, k=1.7)]
            if "motivos" in vis:
                r += [P("Revisión manual por motivo", "h2")] + [P(f"{m}: {n}") for m, n in vis["motivos"]]
            return r, ("Revisión manual por motivo",)
        return [], ()

    # una página por pestaña: sus indicadores y su visual orbital protagonista
    ids = [x["id"] for x in secs]
    vivas = {x["id"] for x in secs if x["kpis"] or x["graficos"]}
    fusion = {"desempeno", "incidentes"} <= vivas      # Rapidez e Incidentes comparten página (cada una llenaba media hoja)

    def orden(x):
        if x["id"] == "cobertura" and "calidad" in ids:
            return ids.index("calidad") + .5
        if x["id"] == "incidentes" and fusion:
            return ids.index("desempeno") + .5
        return ids.index(x["id"])

    for s_ in sorted(secs, key=orden):
        if s_["id"] == "resumen" or (not s_["kpis"] and not s_["graficos"]):
            continue
        junto = s_["id"] in ("cobertura", "incidentes") and (s_["id"] == "cobertura" or fusion)
        titulo = "Rapidez e incidentes" if fusion and s_["id"] == "desempeno" else s_["titulo"]
        h += ([Spacer(1, 14)] if junto else [PageBreak()]) + [P(titulo, "h2" if (junto and s_["id"] == "incidentes") else "h1")]
        if s_["kpis"]:
            h.append(Tarjetas([(k["etiqueta"], k["v"], k["u"], k["e"] if k["e"] in COL and k["e"] != "na" else ("na" if k["e"] == "na" else "neutro")) for k in s_["kpis"]], cols=3))
        v_, reemplaza = visual_de(s_["id"])
        if v_:
            h += [Spacer(1, 6)] + v_
        for g in s_["graficos"]:
            if any(g["titulo"].startswith(t) for t in reemplaza):
                continue
            h += [Spacer(1, 8), Barras(g)]
        for n in s_["notas"]:
            h += [Spacer(1, 4), P("Nota: " + n, "n")]
    h += [PageBreak(), P("Anexo: tablas", "h1")]
    if ej["dias"]:
        n = -(-len(ej["dias"]) // 3)
        trozos = [ej["dias"][j:j + n] for j in range(0, len(ej["dias"]), n)]
        tablas = []
        for tz in trozos:
            tb = Table([[PN("Día", "ch"), PN("Casos", "ch", True), PN("Con sug.", "ch", True)]] + [[PN(r["d"]), PN(r["c"], "c", True), PN(r["s"], "c", True)] for r in tz], colWidths=[(ancho / 3 - 6) * .38, (ancho / 3 - 6) * .31, (ancho / 3 - 6) * .31])
            tb.setStyle(estilo); tablas.append(tb)
        h += [P("Resumen · Casos por día", "h2"), Table([tablas], colWidths=[ancho / 3] * len(tablas), style=[("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 6)])]
    for s_ in secs:
        for tb in s_["tablas"]:
            h.append(P(f"{s_['titulo']} · {tb['titulo']}", "h2"))
            if tb["trozos"]:
                w = ancho / 3
                h.append(Table([[tabla(tb, ch, w - 6) for ch in tb["trozos"]]], colWidths=[w] * len(tb["trozos"]), style=[("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 6)]))
            else:
                h.append(tabla(tb, tb["filas"], ancho))
    h.append(Spacer(1, 8))
    h.append(P("Verde: dentro de la meta. Ámbar: atención. Rojo: bajo la meta. Un guion (—) es una cifra sin dato. La fuente de cada cifra está en el XLSX y el CSV.", "n"))
    doc.build(h)
    return out.getvalue()
