"""Tanda 2026-11-13: íconos dentro de la página (Firefox), barra de Ajustes con su espacio, Acierto por ley compacta y menos texto."""
import os
import re
import sys
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "front"))
os.environ["FRONT_CLAVE"] = "clave-de-prueba"
os.environ["LOG_ANALYTICS_WORKSPACE_ID"] = "ws-prueba"
from app import principal  # noqa: E402

EST = Path(__file__).resolve().parents[2] / "front" / "app" / "estaticos"
from sesion_prueba import H  # noqa: E402  (cookie de la sesión de Dirección)


def test_los_iconos_van_dentro_de_cada_pagina_y_sin_sprites_externos():
    c = TestClient(principal.app, base_url="https://t")
    for r in ("/", "/panel", "/panel/negocio", "/panel/ajustes", "/panel/informe"):
        t = c.get(r, headers=H).text
        assert t.count('<svg id="sprites"') == 1 and '<symbol id="n-acierto"' in t and '<symbol id="e-lista"' in t and '<symbol id="arrow-right"' in t, r
        assert not re.search(r'href="/estaticos/[^"]*\.svg#', t), r
        ids = re.findall(r'\sid="([^"]+)"', t)
        assert len(ids) == len(set(ids)), [i for i in set(ids) if ids.count(i) > 1]
    for js in ("kerna.js", "ajustes.js"):
        assert not re.search(r"/estaticos/(identidad|iconos)\.svg#", (EST / js).read_text())


def test_la_barra_de_ajustes_reserva_espacio_abajo_y_centra_sus_botones():
    t = TestClient(principal.app, base_url="https://t").get("/panel/ajustes", headers=H).text
    assert 'data-barra hidden>' in t and t.index("data-barra") < t.index('class="ajs-esp"')
    css = (EST / "kerna.css").read_text()
    assert ".ajs-barra:not([hidden])+.ajs-esp{height:" in css and ".ajs-barra .btn{justify-content:center" in css


def test_acierto_por_ley_comparte_fila_y_no_trae_la_linea_suelta():
    p = (EST.parent / "plantillas" / "panel.html").read_text()
    assert 'class="fila-2"' in p and "sin ley identificada" not in p
    assert ".fila-2{display:grid" in (EST / "kerna.css").read_text()


def test_la_pestana_calidad_oculta_sigue_oculta():
    css = (EST / "kerna.css").read_text()
    assert "#p-calidad:not([hidden]){display:flex" in css and "#p-calidad{display:flex" not in css
