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
    assert "identidad.svg#e-contingencia-modelo" in t or "identidad.svg#n-" in t
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
    assert [p["id"] for p in v["pestanas"]] == ["calidad", "desempeno", "costo", "rentabilidad", "incidentes"]
    kinds = {c["kind"] for cs in v["charts"].values() for c in cs}
    assert kinds <= {"bar", "line", "donut"} and set(v["charts"]) <= {"rentabilidad"}   # el resto de pestañas usa visuales orbitales del servidor
    assert all(p["vis"] for p in v["pestanas"] if p["id"] != "rentabilidad") and all(len(p["stats"]) <= 3 for p in v["pestanas"])
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
    assert "<table" not in h and len(re.findall(r"<p[ >]", h)) <= 16
    assert len(re.findall(r'role="tab"', h)) == 6 and "hidden" in h


def test_informe_con_cache_sale_completo(monkeypatch, inf):
    cache.vaciar()
    cache._datos[("informe", 30, None, None)] = (time.time(), inf)
    t = TestClient(principal.app, base_url="https://t").get("/panel/informe?dias=30", headers=H).text
    assert "data-carga" not in t and 'class="bn kbs kbs6"' in t and 'id="inf-charts"' in t


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
    assert "metas cumplidas" in v["veredicto"]["t"]
    from test_front_vistas import EV, M
    r = vistas.resumen(M, EV, None, None, None, None, None, 7)
    for k in r["kpis"]:
        assert k["form"] != "spark" or len(k["s"]) >= 4


def test_negocio_compacto_sin_ruido_de_clientes_sin_uso():
    from datetime import date
    hoy = date(2026, 11, 12)
    cl = [{"PartitionKey": "veridy-dev", "nombre": "Veridy", "plan_denuncias_mes": 200, "plan_tipo": "plataforma", "estado": "activo"},
          {"PartitionKey": "otro", "nombre": "Otro SpA", "plan_denuncias_mes": 100, "plan_tipo": "basico", "estado": "activo"}]
    real = {"dias": {"2026-11-12": (5, 4)}, "valoradas": 0, "utiles": 0}
    c2, u2 = negocio.con_uso_real(cl, [], real, 30, hoy)
    V = vistas.negocio(negocio.construir(c2, u2, hoy=hoy))
    assert [c["nombre"] for c in V["con_uso"]] == ["Veridy"] and [c["nombre"] for c in V["sin_uso"]] == ["Otro SpA"] and V["n_uso"] == 1
    ing = next(k for k in V["kpis"] if k["k"] == "neg_ingreso")
    assert "Incluye las tarifas de los 2 clientes con contrato" in ing["x"]
    assert next(k for k in V["kpis"] if k["k"] == "neg_clientes_k")["form"] == "none"
    assert vistas.negocio(negocio.construir(c2, u2, hoy=hoy))["graficos"]["clientes"]["series"][0]["n"] == "Veridy"


def test_costo_en_la_tarjeta_y_sin_tarjeta_duplicada():
    from test_front_vistas import EV, M
    c = vistas.costo_modelos([{"modelo": "gpt-5-nano", "solicitudes": 10, "tokens_entrada_total": 1000, "tokens_salida_total": 100}])
    v = vistas.resumen(M, EV, None, None, c, [], None, 7)
    k = next(x for x in v["kpis"] if x["k"] == "costo_k")
    assert k["form"] == "costo" and k["stack"][0]["n"] == "gpt-5-nano" and k["por_caso"]
    t = TestClient(principal.app, base_url="https://t")
    assert t.get("/panel", headers=H).status_code == 200


# ---- íconos: todo <use> apunta a un id que existe -------------------------------------------------------------------------
def _ids(archivo: str) -> set:
    return set(re.findall(r'<(?:symbol|g|svg)[^>]*\sid="([^"]+)"', (EST / archivo).read_text()))


@pytest.mark.parametrize("archivo", ["identidad.svg", "iconos.svg", "estados.svg"])
def test_sprites_son_xml_valido(archivo):
    """Un atributo duplicado corta el sprite en ese símbolo y los siguientes se ven vacíos."""
    import xml.etree.ElementTree as ET
    ET.parse(EST / archivo)


def test_todo_use_apunta_a_un_id_que_existe(monkeypatch):
    ids = {"identidad.svg": _ids("identidad.svg"), "iconos.svg": _ids("iconos.svg")}
    c = TestClient(principal.app, base_url="https://t")
    paginas = [c.get(r, headers=H).text for r in ("/", "/panel", "/panel/negocio", "/panel/ajustes", "/panel/reintentar")]
    usados = set()
    for t in paginas:
        usados |= set(re.findall(r'href="/estaticos/(identidad\.svg|iconos\.svg)(?:\?[^"#]*)?#([^"]+)"', t))
    assert len(usados) > 15
    faltan = sorted(f"{a}#{i}" for a, i in usados if i not in ids[a])
    assert faltan == []
    # los íconos que genera el servidor y los que arma el JS también existen
    for n in ("e-lista", "e-contingencia-modelo", "e-cadena-agotada", "e-sin-info", "l-karin", "l-datos", "l-penal", "t-lista"):
        assert n in ids["identidad.svg"], n


def test_portada_sin_use_roto():
    t = (EST.parent / "plantillas" / "portada.html").read_text()
    ids = _ids("identidad.svg") | _ids("iconos.svg")
    internos = set(re.findall(r'<use[^>]*href="#([^"]+)"', t)) - set(re.findall(r'\sid="([^"]+)"', t))
    assert not (internos - ids), internos - ids


# ---- porcentajes: nada de razones (0,492) junto a «%» ---------------------------------------------------------------
def test_acierto_y_metas_en_porcentaje_en_el_informe(inf):
    v = vistas.informe_v2(inf)
    ac = next(c for c in v["cards"] if c["k"] == "calidad")
    assert ac["u"] == "%" and "," in ac["v"] or ac["v"].isdigit()
    assert float(ac["v"].replace(",", ".")) > 1                       # 49,2 y no 0,492
    assert "meta 80 %" in ac["meta"] and "0,8" not in ac["meta"]
    kb = next(k for k in v["kb"] if k["k"] == "calidad")
    assert kb["bar"]["t"] == "meta 80 %"
    veri = v["veredicto"]
    assert re.fullmatch(r"\d+ de \d+ metas cumplidas|Sin datos en el período", veri["t"]) and ":" not in veri["t"]
    for s in vistas.informe(inf):
        for k in s["kpis"]:
            if k["etiqueta"].lower().startswith(("recall", "meta de recall")):
                assert k["u"] == "%" and float(k["v"].replace(",", ".")) > 1, k
        for t in s["tablas"]:
            for fila in t["filas"]:
                for c in fila:
                    assert not re.search(r"\b0,\d+ %", c["t"]), c


def test_exportaciones_visibles_en_porcentaje(inf):
    p = informe.para_mostrar(inf)
    cal = next(s for s in p["secciones"] if s["id"] == "calidad")
    rec = next(k for k in cal["kpis"] if k["etiqueta"].startswith("Meta de recall"))
    assert rec["valor"] == 80.0 and rec["unidad"] == "%"
    assert all(k["valor"] is None or k["valor"] > 1 for k in cal["kpis"] if k["etiqueta"].lower().startswith("recall"))
    g = next(g for g in cal["graficos"] if g["titulo"].startswith("Recall@5"))
    assert "meta 80 %" in g["titulo"] and g["meta"] == 80.0
    orig = next(s for s in inf["secciones"] if s["id"] == "calidad")
    assert next(k for k in orig["kpis"] if k["etiqueta"].startswith("Meta de recall"))["valor"] == 0.8   # el original no se toca
    import csv, io
    from app import exportar
    filas = list(csv.reader(io.StringIO(exportar.a_csv(inf).decode("utf-8-sig")), delimiter=";"))
    meta = next(f for f in filas if f[1].startswith("Meta de recall"))
    assert meta[2] == "80" and meta[3] == "%"
    assert exportar.a_xlsx(inf)[:2] == b"PK" and exportar.a_pdf(inf)[:4] == b"%PDF"


# ---- diagrama orbital: satélites y leyenda sin superposición --------------------------------------------------------------
def _satelites(html):
    return [(float(x), float(y)) for x, y, _ in re.findall(r'<circle cx="([\d.]+)" cy="([\d.]+)" r="([\d.]+)" class="orb-s"', html)]


@pytest.mark.parametrize("n", [1, 2, 3, 4])
def test_satelites_del_diagrama_no_se_cruzan(n):
    from app import orbital
    datos = [{"n": f"Modo {i}", "v": v, "txt": str(v), "c": c} for i, (v, c) in enumerate(zip((17, 15, 271, 5), ("verde", "amarillo", "coral", "cian")))][:n]
    html = str(orbital.diagrama_orbital(datos, "303", "denuncias"))
    pos = _satelites(html)
    assert len(pos) == n
    for i in range(n):
        for j in range(i + 1, n):
            d = ((pos[i][0] - pos[j][0]) ** 2 + (pos[i][1] - pos[j][1]) ** 2) ** .5
            assert d >= 26, (pos, d)                 # radio 12 + 12 + margen
    for x, y in pos:
        assert 12 <= x <= 248 and 12 <= y <= 224     # dentro del lienzo
    assert 'class="orb-l"' not in html and html.count("<li ") == n   # los nombres van en la leyenda, no encima de los anillos


def test_satelites_repartidos_en_la_vuelta():
    from app import orbital
    ang = [a % 6.2832 for a in orbital.angulos_satelites(3)]
    ang.sort()
    assert min(b - a for a, b in zip(ang, ang[1:] + [ang[0] + 6.2832])) > 1.5   # ≥ 85° entre satélites vecinos


def test_sprite_tiene_candado_oculto_y_cita():
    s = (EST / "identidad.svg").read_text()
    for n in ("candado", "oculto", "cita"):
        assert f'id="n-{n}"' in s
    assert 'r="28"' in re.search(r'<symbol id="m-sin-info".*?</symbol>', s, re.S).group(0)   # el mini «sin información» no es un punto suelto


def test_cascada_con_altura_minima_y_conectores():
    t = {"ingreso": 31.87, "costo_servir": 4.78, "participacion_veridy": 8.13, "costos_fijos": 8.87, "depreciacion": 5.0, "interes": 5.44, "impuesto": 0.0, "utilidad": -0.34}
    c = vistas.cascada_negocio(t)
    assert len(c["labels"]) == len(c["vals"]) == len(c["sp"]) == len(c["niv"]) + 1
    altura = [abs(a) + abs(b) for a, b in zip(c["sp"], c["sn"])]
    piso = max(c["sp"]) * 0.015
    assert all(h >= piso * 0.99 for h in altura), altura          # Impuesto (0) y Utilidad (−0,34) siguen visibles
    assert c["vals"][-2] == "0,00" and c["vals"][-1] == "−0,34"
    assert all("\n" not in x for x in c["labels"])               # el valor va como etiqueta sobre la barra, no en el eje


def test_pdf_primera_pagina_con_veredicto_y_una_pagina_por_pestana(inf):
    import io
    from app import exportar
    from pypdf import PdfReader
    r = PdfReader(io.BytesIO(exportar.a_pdf(inf)))
    p1 = r.pages[0].extract_text()
    assert "metas cumplidas" in p1 and "Acierto" in p1 and "Informe de gestión" in p1      # cabecera, veredicto y KPI en la página 1
    assert "meta 0,8" not in "".join(p.extract_text() for p in r.pages)
    assert len(r.pages) >= 3 and "Calidad" in r.pages[1].extract_text()
    assert (EST / "img" / "baldosa-lista.png").exists()


def test_pdf_fusiona_rapidez_e_incidentes_en_una_pagina(inf):
    import io
    from app import exportar
    from pypdf import PdfReader
    pag = [p.extract_text() for p in PdfReader(io.BytesIO(exportar.a_pdf(inf))).pages]
    una = [t for t in pag if "Rapidez e incidentes" in t]
    assert len(una) == 1 and "Incidentes" in una[0]
    assert not any(t.lstrip().startswith("Incidentes") for t in pag)


def test_datos_agrupa_las_tablas_por_seccion(monkeypatch, inf):
    monkeypatch.setattr(principal, "_informe", lambda *a, **k: inf)
    html = TestClient(principal.app, base_url="https://t").get("/panel/informe/datos?dias=30", headers=H).text
    secs = re.findall(r'<details class="dat-s">', html)
    assert 3 <= len(secs) <= 7 and html.count('class="dat-d"') >= len(secs)
    assert "dat-h" not in html
    assert all(re.search(rf'class="dat-s"><summary><span>{t}</span>', html) for t in ("Calidad", "Rapidez", "Costos", "Incidentes"))


def test_global_lleva_icono_como_las_leyes(inf):
    html = str(vistas.informe_vis(inf, {})["calidad"])
    assert 'data-l="global"' in html and html.count('class="lx"') == html.count('<li class="ly')


def test_pdf_usa_las_visuales_orbitales_de_la_vista(inf):
    import io
    from app import exportar, orbital, pdf_orbital
    from pypdf import PdfReader
    v = vistas.visuales_pdf(inf)
    assert {"periodo", "leyes", "etapas", "tokens"} <= set(v) and v["periodo"]["total"] == "9"
    r = PdfReader(io.BytesIO(exportar.a_pdf(inf)))
    texto = [p.extract_text() for p in r.pages]
    assert "Cómo se resolvieron las denuncias" in texto[0] and "El camino de una denuncia" in texto[0] and "metas cumplidas" in texto[0]   # página 1 compuesta
    assert any("Acierto por ley" in t for t in texto) and any("Costo por modelo" in t for t in texto)
    # el dibujo vectorial del período usa la misma geometría que el SVG de la pantalla
    g = orbital.geometria_orbital(v["periodo"]["anillos"], v["periodo"]["total"])
    assert len(g["anillos"]) == len(v["periodo"]["anillos"]) and pdf_orbital.Orbital(v["periodo"]["anillos"], "9", "denuncias", 500).height > 200


def test_pdf_con_rentabilidad_dibuja_cascada_y_proyeccion(inf):
    import io
    from app import exportar, negocio
    from pypdf import PdfReader
    cl = [{"PartitionKey": "a", "nombre": "Veridy", "plan_tipo": "profesional", "plan_denuncias_mes": 300, "estado": "activo"}]
    n = negocio.construir(cl, [], dias=30)
    from app import informe
    from test_front_informe import EVAL, FIN, INI, falso
    inf2 = informe.construir(INI, FIN, ejecutar=falso, evaluacion=EVAL, negocio=n)
    v = vistas.visuales_pdf(inf2)
    assert len(v["cascada"]["labels"]) == 7 and len(v["proyeccion"]) == 5
    texto = " ".join(p.extract_text() for p in PdfReader(io.BytesIO(exportar.a_pdf(inf2))).pages)
    assert "Del ingreso a la utilidad" in texto and "Proyección a cinco años" in texto


def test_satelite_con_cifra_larga_crece_y_el_total_largo_se_achica():
    from app import orbital
    g = orbital.geometria_orbital([{"n": "a", "v": 3, "txt": "144 mil", "c": "azul"}, {"n": "b", "v": 1, "txt": "9", "c": "verde"}], "US$ 0,0347")
    assert g["anillos"][0]["rs"] > 12 and g["anillos"][1]["rs"] == 12 and g["fs"] < 17
