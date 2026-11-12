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
    s = io.StringIO()
    w = csv.writer(s, delimiter=";", lineterminator="\r\n")  # ';' y BOM: Excel en español lo abre sin asistente
    w.writerow(ENCABEZADO_CSV)
    for fila in informe.filas_largas(inf):
        w.writerow(fila)
    return ("﻿" + s.getvalue()).encode("utf-8")


# ---- XLSX ---------------------------------------------------------------------------------------------------------
def a_xlsx(inf: dict) -> bytes:
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

    class Barras(Flowable):
        def __init__(self, g):
            super().__init__()
            self.g, self.items = g, [(str(a), float(b)) for a, b in g["items"]]
            self.h = 14 + (len(self.items) * 13 if g["tipo"] == "h" else 90)
            self.width, self.height = ancho, self.h

        def wrap(self, aw, ah):
            return ancho, self.h

        def draw(self):
            c, it, g = self.canv, self.items, self.g
            c.setFont("Unbounded-M", 7); c.setFillColor(az)
            c.drawString(0, self.h - 8, g["titulo"])
            if not it or not any(v for _, v in it):
                c.setFont("Mono", 7); c.setFillColor(sec); c.drawString(0, self.h - 22, "Sin datos en el período."); return
            mx = max(max(v for _, v in it), g.get("meta") or 0) or 1
            c.setLineWidth(.8); c.setStrokeColor(az)
            if g["tipo"] == "h":
                x0, maxw = 120, ancho - 190
                for i, (et, v) in enumerate(it):
                    y = self.h - 22 - i * 13
                    c.setFillColor(az); c.setFont("Mono", 6.8); c.drawString(0, y, et[:24])
                    c.setFillColor(li if v == max(x for _, x in it) else HexColor("#FFFFFF"))
                    c.rect(x0, y - 2, max(1.5, maxw * v / mx), 9, stroke=1, fill=1)
                    c.setFillColor(sec); c.drawString(x0 + max(1.5, maxw * v / mx) + 4, y, _fmt(round(v, 3) if g.get("fmt") == "ratio" else (round(v, 4) if g.get("fmt") == "usd" else int(v))))
                if g.get("meta"):
                    xm = x0 + maxw * g["meta"] / mx
                    c.setStrokeColor(sec); c.setDash(2, 2); c.line(xm, 2, xm, self.h - 14); c.setDash()
            else:
                n, paso = len(it), (ancho - 10) / len(it)
                ba = min(22, paso * .7)
                c.setStrokeColor(ln); c.line(0, 14, ancho, 14); c.setStrokeColor(az)
                for i, (et, v) in enumerate(it):
                    h = (self.h - 40) * v / mx
                    x = 5 + i * paso + (paso - ba) / 2
                    c.setFillColor(li); c.rect(x, 14, ba, h, stroke=1, fill=1)
                    c.setFillColor(sec); c.setFont("Mono", 6)
                    c.drawCentredString(x + ba / 2, 16 + h, str(int(v)))
                    if n <= 14 or i % max(1, n // 10) == 0:
                        c.drawCentredString(x + ba / 2, 5, et)

    def pie(c, d):
        c.saveState(); c.setFont("Mono", 6.5); c.setFillColor(sec)
        c.drawString(18 * mm, 10 * mm, f"Kerna AI · Informe de gestión · {inf['meta']['periodo']} · corte {inf['meta']['corte']}")
        c.drawRightString(A4[0] - 18 * mm, 10 * mm, f"Página {d.page}")
        c.setStrokeColor(az); c.setLineWidth(.6); c.line(18 * mm, 14 * mm, A4[0] - 18 * mm, 14 * mm); c.restoreState()

    def portada(c, d):
        c.saveState()
        c.setFillColor(HexColor("#" + PAPEL)); c.rect(0, 0, *A4, stroke=0, fill=1)
        logo.dibujar(c, 18 * mm, A4[1] - 100 * mm, 62 * mm)
        c.setFillColor(az); c.setFont("Unbounded", 30); c.drawString(86 * mm, A4[1] - 62 * mm, "KERNA")
        c.setFillColor(li); c.setStrokeColor(az); c.setLineWidth(1)
        c.rect(150 * mm, A4[1] - 58 * mm, 14 * mm, 8 * mm, stroke=1, fill=1)
        c.setFillColor(az); c.setFont("Unbounded", 8); c.drawString(153 * mm, A4[1] - 55.5 * mm, "AI")
        c.setFont("Unbounded", 20); c.drawString(18 * mm, A4[1] - 135 * mm, "Informe de gestión")
        c.setFont("Mono", 10)
        c.drawString(18 * mm, A4[1] - 148 * mm, f"Período: {inf['meta']['periodo']}")
        c.drawString(18 * mm, A4[1] - 155 * mm, f"Fecha de corte: {inf['meta']['corte']}")
        c.setFillColor(sec); c.setFont("Mono", 8)
        c.drawString(18 * mm, 24 * mm, "Sugerencia normativa para denuncias en Veridy. Solo cifras agregadas: sin texto de denuncias ni identificadores.")
        c.restoreState()

    out = io.BytesIO()
    doc = BaseDocTemplate(out, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=16 * mm, bottomMargin=20 * mm,
                          title=inf["meta"]["titulo"], author="Kerna AI", subject=f"Período {inf['meta']['periodo']}")
    fr = Frame(18 * mm, 20 * mm, ancho, A4[1] - 36 * mm, id="f", leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
    doc.addPageTemplates([PageTemplate(id="portada", frames=[Frame(18 * mm, 20 * mm, ancho, 20 * mm)], onPage=portada, autoNextPageTemplate="normal"),
                          PageTemplate(id="normal", frames=[fr], onPage=pie)])
    h = [Spacer(1, 1), PageBreak(), P("Índice", "h1")]
    h += [P(f"{i}. {s['titulo']}") for i, s in enumerate(inf["secciones"], 1)]
    h += [Spacer(1, 8), P("Cada cifra indica su fuente. Donde no hay datos se escribe «sin datos»; no se estima ni se inventa.", "n"), PageBreak()]
    for i, s in enumerate(inf["secciones"], 1):
        h.append(P(f"{i}. {s['titulo']}", "h1"))
        h.append(P(s["justificacion"], "n"))
        if s["kpis"]:
            filas = [[P("Métrica", "ch"), P("Valor", "ch"), P("Fuente", "ch")]] + [[P(k["etiqueta"], "c"), P(_fmt(k["valor"]) + (f" {k['unidad']}" if k["unidad"] and k["valor"] is not None else ""), "c"), P(k["fuente"], "c")] for k in s["kpis"]]
            t = Table(filas, colWidths=[ancho * .36, ancho * .2, ancho * .44], repeatRows=1)
            t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), li), ("BOX", (0, 0), (-1, -1), .8, az), ("LINEBELOW", (0, 0), (-1, 0), .8, az), ("LINEBELOW", (0, 1), (-1, -1), .4, ln), ("VALIGN", (0, 0), (-1, -1), "TOP")]))
            h += [Spacer(1, 6), t]
        for g in s["graficos"]:
            h += [Spacer(1, 8), Barras(g)]
        for tb in s["tablas"]:
            h.append(P(tb["titulo"], "h2"))
            rows = tb["filas"] or [["sin datos en el período"] + [""] * (len(tb["cols"]) - 1)]
            nc = len(tb["cols"])
            anchos = [ancho / nc] * nc
            t = Table([[P(c, "ch") for c in tb["cols"]]] + [[P(_fmt(v), "c") for v in r] for r in rows], colWidths=anchos, repeatRows=1)
            t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), li), ("BOX", (0, 0), (-1, -1), .8, az), ("LINEBELOW", (0, 0), (-1, 0), .8, az), ("LINEBELOW", (0, 1), (-1, -1), .4, ln), ("VALIGN", (0, 0), (-1, -1), "TOP")]))
            h += [t, P("Fuente: " + tb["fuente"], "n")]
        for n in s["notas"]:
            h += [Spacer(1, 3), P("Nota: " + n, "n")]
        if i < len(inf["secciones"]):
            h.append(PageBreak())
    doc.build(h)
    return out.getvalue()
