"""Rediseño del front v2: caché con refresco en segundo plano, cabeceras de rendimiento, íconos de la identidad Núcleo,
informe en pestañas con tablas aparte y decoración como imagen."""
import os
import re
import sys
import time
import xml.dom.minidom
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "front"))
os.environ["FRONT_CLAVE"] = "clave-de-prueba"
os.environ["LOG_ANALYTICS_WORKSPACE_ID"] = "ws-prueba"
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "front" / "herramientas"))
from app import cache, informe, principal, seguridad, vistas  # noqa: E402
import construir_iconos_estado as iconos  # noqa: E402

EST = Path(__file__).resolve().parents[2] / "front" / "app" / "estaticos"
H = {"X-Clave": "clave-de-prueba"}


# ---- caché -------------------------------------------------------------------------------------------------------------
def test_cache_entrega_dato_vencido_y_refresca_aparte():
    n = {"v": 0}

    def calcular():
        n["v"] += 1
        time.sleep(0.05)
        return n["v"]
    assert cache.obtener("k", calcular, ttl=0.01) == 1       # primera vez: espera el cálculo
    time.sleep(0.02)
    t0 = time.time()
    assert cache.obtener("k", calcular, ttl=0.01) == 1       # vencido: responde al instante con lo guardado
    assert time.time() - t0 < 0.04
    time.sleep(0.2)
    assert cache.obtener("k", calcular, ttl=5) == 2          # el refresco en segundo plano ya dejó el dato nuevo
    assert cache.hay("k") and not cache.hay("otra")


def test_paralelo_corre_a_la_vez_y_devuelve_errores():
    t0 = time.time()
    r = cache.paralelo({"a": lambda: time.sleep(0.2) or 1, "b": lambda: time.sleep(0.2) or 2, "c": lambda: 1 / 0})
    assert r["a"] == 1 and r["b"] == 2 and isinstance(r["c"], ZeroDivisionError) and time.time() - t0 < 0.35


# ---- cabeceras de rendimiento -----------------------------------------------------------------------------------------
def test_gzip_y_cache_inmutable_en_estaticos():
    c = TestClient(principal.app, base_url="https://t")
    r = c.get("/estaticos/kerna.css?v=1", headers={"accept-encoding": "gzip"})
    assert r.headers["content-encoding"] == "gzip" and "immutable" in r.headers["cache-control"] and "max-age=31536000" in r.headers["cache-control"]
    assert "max-age=604800" in c.get("/estaticos/img/simbolo.webp").headers["cache-control"]
    p = c.get("/panel/informe", headers={**H, "accept-encoding": "gzip"})
    assert p.headers["content-encoding"] == "gzip" and p.headers["cache-control"] == "no-store"


# ---- íconos de estado (identidad Núcleo) ---------------------------------------------------------------------------------
def test_sprite_de_estados_valido_estatico_y_completo():
    s = (EST / "estados.svg").read_text()
    xml.dom.minidom.parseString(s)
    ids = set(re.findall(r'<symbol id="(e-[a-z-]+)"', s))
    assert ids == {"e-" + n for n in iconos.ICONOS} and len(ids) == 14
    assert "class=" not in s and "animation" not in s and "<style" not in s and len(s) < 20000
    for v in vistas.ICONO.values():
        assert v in ids


def test_colores_de_estado_cumplen_contraste_AA():
    bloque, mal = iconos.css()
    assert mal == []
    css = (EST / "kerna.css").read_text()
    assert "--ok:" in css and "--pro-bar:" in css and all(f'k-st[data-e="{n}"]' in css for n in iconos.ICONOS)


def test_icono_de_estado_usa_baldosa_y_lucide_solo_utilitario():
    c = TestClient(principal.app, base_url="https://t")
    t = c.get("/panel/ajustes", headers=H).text
    assert '<k-st data-e="contingencia-modelo"' in t and "estados.svg#e-" in t
    for viejo in ("circle-check", "triangle-alert", "octagon-alert", "circle-minus"):
        assert viejo not in re.sub(r"<symbol.*", "", t)


# ---- informe v2 --------------------------------------------------------------------------------------------------------
@pytest.fixture
def inf():
    from test_front_informe import EVAL, FIN, INI, falso
    return informe.construir(INI, FIN, ejecutar=falso, evaluacion=EVAL)


def test_informe_v2_kpis_veredicto_y_graficos(inf):
    v = vistas.informe_v2(inf)
    assert len(v["cards"]) == 6 and all(c["e"] in ("ok", "warn", "bad", "na") and c["meta"] for c in v["cards"])
    assert v["veredicto"]["e"] in ("ok", "warn", "bad", "na") and "\n" not in v["veredicto"]["t"] and len(v["veredicto"]["t"]) < 120
    assert [p["id"] for p in v["pestanas"]] == ["resumen", "calidad", "desempeno", "costo", "rentabilidad", "incidentes"]
    kinds = {c["kind"] for cs in v["charts"].values() for c in cs}
    assert kinds <= {"bar", "line", "donut"} and sum(len(cs) for cs in v["charts"].values()) >= 8
    for cs in v["charts"].values():
        assert len(cs) <= 3  # una fila de gráficos por pestaña


def test_tendencia_solo_con_serie_suficiente():
    assert vistas._tendencia([1, 2], None)["tr"] == ""
    t = vistas._tendencia([10, 10, 20, 20], False)
    assert t["tr"].startswith("+") and t["te"] == "ok" and t["ta"] == "trending-up"
    assert vistas._tendencia([20, 20, 10, 10], True)["te"] == "ok"
    assert vistas._tendencia([10, 10, 10, 10], True)["tr"] == "estable"


def test_informe_cuerpo_liviano_y_sin_parrafos(monkeypatch, inf):
    monkeypatch.setattr(principal, "_informe", lambda *a, **k: inf)
    h = TestClient(principal.app, base_url="https://t").get("/panel/informe/cuerpo?dias=30", headers=H).text
    assert len(re.findall(r"<[a-z]", h)) < 650            # el cuerpo no crece con las tablas (van aparte)
    assert "<p" not in h and "<table" not in h
    assert len(re.findall(r'role="tab"', h)) == 7 and "hidden" in h


def test_informe_con_cache_sale_completo(monkeypatch, inf):
    cache.vaciar()
    cache._datos[("informe", 30, None, None)] = (time.time(), inf)
    t = TestClient(principal.app, base_url="https://t").get("/panel/informe?dias=30", headers=H).text
    assert "data-carga" not in t and 'class="kg6"' in t and 'id="inf-charts"' in t


def test_informe_requiere_sesion():
    c = TestClient(principal.app, follow_redirects=False)
    assert c.get("/panel/informe/cuerpo").status_code == 401 and c.get("/panel/informe/datos").status_code == 401


# ---- decoración como imagen --------------------------------------------------------------------------------------------
def test_decoracion_es_imagen_y_no_svg_con_datauri():
    css = (EST / "kerna.css").read_text()
    assert "data:image/svg" not in css and "url(img/guil.webp)" in css
    for f in ("guil", "guil-l", "bg-orbitas", "bg-roseta", "simbolo"):
        assert (EST / "img" / f"{f}.webp").stat().st_size < 90_000
    c = TestClient(principal.app, base_url="https://t")
    t = c.get("/panel/ajustes", headers=H).text
    assert "bg-orbitas.webp" in t and "bg-roseta.webp" in t and 'data-logo="mini"' not in t and "<ellipse" not in t
    assert "echarts" not in t  # Ajustes no carga gráficos
    assert "echarts.custom.min.js" in c.get("/panel/negocio", headers=H).text
    assert (EST / "echarts.custom.min.js").stat().st_size < 700_000 and not (EST / "echarts.min.js").exists()
