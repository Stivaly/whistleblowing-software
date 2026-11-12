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
from app import cache, informe, negocio, principal, seguridad, vistas  # noqa: E402
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
    ids = set(re.findall(r'<g id="(e-[a-z-]+)"', s))
    assert ids == {"e-" + n for n in iconos.ICONOS} and len(ids) == 14
    assert set(re.findall(r'<g id="(s-[a-z-]+)"', s)) == {"s-" + n for n in iconos.ICONOS}  # variante pequeña (16 a 32 px) de cada ícono
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
    assert '<k-st data-e="contingencia-modelo"' in t and "estados.svg#s-" in t
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


# ---- correcciones de la revisión (prod4) ------------------------------------------------------------------------------
def test_estados_pequenos_se_distinguen_por_color_y_forma():
    css = (EST / "kerna.css").read_text()
    fondo = {n: re.search(r'k-st\[data-e="%s"\]\{[^}]*--sb:(#[0-9A-F]{6})' % n, css).group(1) for n in ("lista", "contingencia-modelo", "cadena-agotada", "sin-info")}
    assert len(set(fondo.values())) == 4  # verde, ámbar, rojo y gris: baldosas de colores distintos
    for a in ("lista", "contingencia-modelo", "cadena-agotada"):  # el glifo oscuro sobre la baldosa de acento tiene contraste de sobra
        sb = fondo[a]; sg = iconos.PAL[iconos.ICONOS[a]][0]
        assert iconos.razon(sb, sg) >= 4.5
    g = iconos.GLIFOS
    assert len({g["lista"], g["contingencia-modelo"], g["cadena-agotada"]}) == 3  # y la forma del glifo también difiere (visto, signo de alerta, cruz)


def test_leyes_con_etiqueta_corta_y_nombre_completo_en_tooltip():
    from test_front_vistas import EV, M
    v = vistas.resumen(M, EV, None, None, None, None, None, 7)
    assert v["aciertos"]
    for a in v["aciertos"]:
        assert not re.fullmatch(r"[\d.]+", a["n"]) and a["full"]
    assert inf_ley("20.393") == "Ley 20.393 · personas jurídicas" and inf_ley("21.643") == "Ley 21.643 · Ley Karin" and inf_ley("19.628").startswith("Ley 19.628 · datos")


def inf_ley(x):
    return informe.ley_corta(x)


def test_costo_muestra_el_modelo_real_y_la_referencia_va_en_el_tooltip():
    c = vistas.costo_modelos([{"modelo": "gpt-5-nano", "solicitudes": 10, "tokens_entrada_total": 1000, "tokens_salida_total": 100}])
    assert c["modelos"][0]["modelo"] == "gpt-5-nano" and c["modelos"][0]["ref"] == "Claude Haiku 5.5"
    from test_front_vistas import EV, M
    v = vistas.resumen(M, EV, None, None, c, [], None, 7)
    k = next(x for x in v["kpis"] if x["k"] == "costo_k")
    assert k["et"] == "" and "Precio de referencia: Claude Haiku 5.5" in k["x"]  # sin chip: no hay meta de costo
    assert v["costo"]["modelos"][0]["n"] == "gpt-5-nano" and v["costo"]["ref"] == "Claude Haiku 5.5"


def test_menu_lateral_de_alto_completo_y_vacios_cortos(monkeypatch):
    c = TestClient(principal.app, base_url="https://t")
    t = c.get("/panel/ajustes", headers=H).text
    assert 'class="hidden lg:block w-64 shrink-0 bg-white border-r"' in t and "sticky top-0" in t
    assert ".lg\\:block" in (EST / "kerna.css").read_text()


def test_negocio_usa_log_analytics_para_veridy_y_no_inventa_el_resto():
    from datetime import date
    hoy = date(2026, 11, 12)
    cl = [{"PartitionKey": "veridy-dev", "nombre": "Veridy", "plan_denuncias_mes": 200, "plan_tipo": "plataforma", "estado": "activo"},
          {"PartitionKey": "otro", "nombre": "Otro SpA", "plan_denuncias_mes": 100, "plan_tipo": "basico", "estado": "activo"}]
    uso = [{"PartitionKey": "veridy-dev", "RowKey": "2026-11-12", "denuncias": 999, "con_sugerencia": 999, "nano_in": 1000},
           {"PartitionKey": "otro", "RowKey": "2026-11-12", "denuncias": 1325, "con_sugerencia": 900, "valoradas": 50, "utiles": 40}]
    real = {"dias": {"2026-11-11": (25, 15), "2026-11-12": (278, 17)}, "valoradas": 0, "utiles": 0}
    c2, u2 = negocio.con_uso_real(cl, uso, real, 30, hoy)
    n = negocio.construir(c2, u2, hoy=hoy)
    o, v = n["clientes"]
    assert v["tot"] == 303 and v["con_sugerencia"] == 32 and o["tot"] is None and o["sin_uso"] and o["riesgo"] == "na" and o["uso_plan"] is None
    assert n["totales"]["denuncias"] == 303 and n["adopcion"]["con_sugerencia_pct"] == round(100 * 32 / 303, 1) == 10.6 and n["adopcion"]["valoradas"] == 0
    assert v["ingreso"] > 0 and o["ingreso"] > 0  # el plan y la tarifa de los clientes sembrados se conservan
    V = vistas.negocio(n)
    assert next(c for c in V["clientes"] if c["sin_uso"])["ult"] == "sin datos" and len(V["graficos"]["clientes"]["series"]) == 1
    # sin respuesta de Log Analytics, nadie muestra cifras de uso
    c3, u3 = negocio.con_uso_real(cl, uso, None, 30, hoy)
    assert negocio.construir(c3, u3, hoy=hoy)["totales"]["denuncias"] == 0


def test_rapidez_con_pocos_dias_usa_barras(inf):
    v = vistas.informe_charts(inf)
    lat = next((c for c in v["desempeno"] if c["id"] == "g-lat"), None)
    assert lat is None or (lat["kind"] == ("line" if len(lat["cats"]) >= 4 else "bar"))


def test_sin_lineas_con_menos_de_4_dias_y_costo_sin_estado(inf):
    v = vistas.informe_v2(inf)
    for c in v["cards"]:
        assert "d_l" not in c or len(c["d_l"]) > 0
    costo = next(c for c in v["cards"] if c["k"] == "costo_k")
    assert costo["e"] == "na" and costo["et"] == ""
    assert "en meta" in v["veredicto"]["n"]
    from test_front_vistas import EV, M
    r = vistas.resumen(M, EV, None, None, None, None, None, 7)
    for k in r["kpis"]:
        assert k["form"] != "spark" or len(k["s"]) >= 4
