"""Resumen v13: ancho máximo, bandas tintadas con contraste AA, proveedores con nombre y estado, sin «(sin nombre)»."""
import re
from pathlib import Path

EST = Path(__file__).resolve().parents[2] / "front" / "app"
CSS = (EST / "estaticos" / "kerna.css").read_text()
PANEL = (EST / "plantillas" / "panel.html").read_text()


def _lum(h):
    h = h.lstrip("#")
    c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    c = [x / 12.92 if x <= .03928 else ((x + .055) / 1.055) ** 2.4 for x in c]
    return .2126 * c[0] + .7152 * c[1] + .0722 * c[2]


def _cr(a, b):
    x, y = sorted([_lum(a), _lum(b)], reverse=True)
    return (x + .05) / (y + .05)


def test_contenido_de_las_vistas_con_ancho_maximo_1440_centrado():
    assert re.search(r"#app \.vw-main\{max-width:1440px;margin-inline:auto\}", CSS)


def test_bandas_tintadas_cumplen_contraste_aa():
    textos = {"ink": "#0F1736", "muted": "#4F5B85", "ok": "#17622E", "warn": "#8F5200", "bad": "#B42318", "brand": "#1C2A6B"}
    zonas = re.findall(r"\.z-(\w+)\{--z1:(#\w+);--z2:(#\w+);", CSS)
    assert {z[0] for z in zonas} == {"pr", "kb", "cm", "ly", "hm", "co"}
    for z, a, b in zonas:
        for nombre, t in textos.items():
            assert _cr(t, a) >= 4.5 and _cr(t, b) >= 4.5, (z, nombre)
    assert "--ok:#17622E" in CSS


def test_proveedores_muestran_nombre_y_estado():
    assert 'class="pg-n"' in PANEL and "data-pt" in PANEL
    assert not re.search(r"\.pg-n\{display:none", CSS.split("/* v13")[-1])
    assert ".pg .pg-n,.pg:hover .pg-n" in CSS


def test_ley_sin_nombre_tiene_etiqueta_comprensible():
    from app import consultas, informe  # noqa: F401
    src = (EST / "consultas.py").read_text() + (EST / "informe.py").read_text()
    assert "(sin nombre)" not in src and "Sin ley registrada" in src
