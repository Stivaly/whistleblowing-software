"""Front v15: ajustes en caliente sin leer la tabla y sin datos viejos tras guardar, banda de KPI sin choques, decoración fuera del texto, escalonado por banda."""
import json
import re
import sys
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "front"))
from test_front_ajustes import H, TablaFalsa  # noqa: E402,F401
from app import ajustes, cache, principal, seguridad  # noqa: E402

EST = Path(__file__).resolve().parents[2] / "front" / "app"
CSS = (EST / "estaticos" / "kerna.css").read_text()
V15 = CSS[CSS.index("/* v15"):]


@pytest.fixture
def cli(monkeypatch):
    t = TablaFalsa()
    monkeypatch.setattr(ajustes, "_tabla", lambda: t)
    cache.vaciar()
    cache._version.clear()
    yield TestClient(principal.app, base_url="https://t")
    cache.vaciar()


def test_ajustes_en_caliente_no_leen_la_tabla(cli, monkeypatch):
    assert cli.get("/panel/ajustes", headers=H).status_code == 200            # primera lectura (frío)
    monkeypatch.setattr(ajustes, "cargar", lambda *a, **k: (_ for _ in ()).throw(AssertionError("leyó la tabla")))
    t0 = time.perf_counter()
    for _ in range(5):
        assert cli.get("/panel/ajustes", headers=H).status_code == 200
    assert (time.perf_counter() - t0) / 5 < 0.1


def test_tras_guardar_no_se_sirve_el_valor_anterior(cli):
    cli.get("/panel/ajustes", headers=H)
    hj = {**H, "Accept": "application/json", "Origin": "https://t"}
    r = cli.post("/panel/ajustes", headers=hj, data={"csrf": seguridad.token_csrf({}), "valores": json.dumps({**ajustes.RECOMENDADO, "envios": 9})})
    assert r.json()["estado"] == "ok"
    assert cache.obtener(("ajustes",), lambda: pytest.fail("recalculó"), 15)["valores"]["envios"] == 9
    assert '"envios": 9' in cli.get("/panel/ajustes", headers=H).text or '"envios":9' in cli.get("/panel/ajustes", headers=H).text


def test_un_calculo_viejo_en_curso_no_pisa_lo_guardado():
    cache.vaciar(); cache._version.clear()
    cache.obtener(("k",), lambda: "viejo", ttl=0)
    def lento():
        cache.poner(("k",), "nuevo")                                         # se guarda mientras el refresco corre
        return "viejo2"
    cache._enproceso.add(("k",)); cache._calcular(("k",), lento)
    assert cache._datos[("k",)][1] == "nuevo"
    cache.vaciar()


def test_ajustes_se_precalientan_al_arrancar():
    src = (EST / "principal.py").read_text()
    assert '(("ajustes",), aj.cargar, 15)' in src


def test_banda_de_kpi_de_seis_en_tres_columnas_hasta_1799():
    assert "@media(min-width:900px){.kbs{grid-template-columns:repeat(4,minmax(0,1fr))}.kbs6{grid-template-columns:repeat(3,minmax(0,1fr))}}" in CSS
    assert "@media(min-width:1800px){.kbs6{grid-template-columns:repeat(6,minmax(0,1fr))}}" in CSS


def test_etiqueta_de_kpi_pega_el_interrogante_a_la_ultima_palabra():
    from jinja2 import Environment, FileSystemLoader
    env = Environment(loader=FileSystemLoader(str(EST / "plantillas")))
    env.globals.update(ic=lambda *a, **k: "", ICONO={"ok": "x"}, glos={})
    m = env.get_template("_macros.html").module
    k = {"k": "util", "l": "Sugerencias útiles", "e": "ok", "ic": "x", "v": "—", "x": "q"}
    html = str(m.kb(k))
    assert re.search(r'<span class="kb-l">Sugerencias <span class="nw">útiles<k-tip', html), html


def test_decoracion_solo_en_el_margen_derecho_y_ninguna_a_la_izquierda():
    assert "--dec:56px" in V15 and "padding-right:calc(var(--dec) + 6px)" in V15
    assert "left -90px bottom -90px" not in V15 and "right calc(var(--dec)*-1) bottom calc(var(--dec)*-1)" in V15


def test_escalonado_por_banda_solo_transform_y_opacity_y_con_reduced_motion():
    assert "@keyframes bnIn{from{opacity:0;transform:translate3d(0,14px,0)}to{opacity:1;transform:none}}" in V15
    assert "@media(prefers-reduced-motion:no-preference){" in V15 and "steps(" not in V15
    assert "animation-delay:calc(var(--i,0)*70ms)" in V15
