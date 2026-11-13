"""Ajustes persistidos, vistas sin los bloques retirados, consultas KQL de tokens y etapas, rótulos de ingresos, informe compacto y logo continuo."""
import os
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "front"))
os.environ["FRONT_CLAVE"] = "clave-de-prueba"
os.environ["LOG_ANALYTICS_WORKSPACE_ID"] = "ws-prueba"

from fastapi.testclient import TestClient  # noqa: E402

from app import ajustes, exportar, informe, principal, seguridad, vistas  # noqa: E402
from test_front_vistas import H, M  # noqa: E402


class TablaFalsa:
    def __init__(self):
        self.fila = None

    def get_entity(self, pk, rk):
        from azure.core.exceptions import ResourceNotFoundError
        if self.fila is None:
            raise ResourceNotFoundError("no existe")
        return self.fila

    def upsert_entity(self, e, mode="replace"):
        self.fila = e


def test_ajustes_validan_y_se_guardan():
    t = TablaFalsa()
    assert ajustes.cargar(t)["guardado_en"] is None and ajustes.cargar(t)["valores"] == ajustes.RECOMENDADO
    v = {**ajustes.RECOMENDADO, "envios": 7, "compartir": ["legal"]}
    ajustes.guardar(v, t)
    assert ajustes.cargar(t)["valores"]["envios"] == 7 and ajustes.cargar(t)["guardado_en"]
    for malo in ({"envios": 99}, {"envios": True}, {"espera": 5}, {"compartir": ["x"]}, {"reprocesar": 1}, {"cadena": [{"v": "azure", "on": True}]}, {"maxresp": 7}):
        with pytest.raises(ValueError):
            ajustes.validar({**ajustes.RECOMENDADO, **malo})


@pytest.fixture
def cli(monkeypatch):
    t = TablaFalsa()
    monkeypatch.setattr(ajustes, "_tabla", lambda: t)
    c = TestClient(principal.app, base_url="https://t")
    c.tabla = t
    return c


def test_ajustes_vista_y_menu(cli):
    assert cli.get("/panel/ajustes", follow_redirects=False).status_code == 303
    r = cli.get("/panel/ajustes", headers=H)
    assert r.status_code == 200 and "Valores recomendados" in r.text and "Casos por ronda" in r.text
    assert "Así queda" not in r.text and "Cada ronda envía" not in r.text and "orb-svg" not in r.text  # sin franjas narrativas ni órbitas decorativas
    assert "Valores recomendados" in r.text and "ejemplo" not in r.text.lower()
    assert 'href="/panel/ajustes"' in cli.get("/panel", headers=H).text


def test_ajustes_guardar_exige_sesion_origen_y_csrf(cli):
    cuerpo = '{"envios": 3}'
    assert cli.post("/panel/ajustes", data={"valores": cuerpo, "csrf": "x"}, follow_redirects=False).headers["location"] == "/acceso"
    assert cli.post("/panel/ajustes", data={"valores": cuerpo, "csrf": "mal"}, headers=H, follow_redirects=False).headers["location"].endswith("guardado=token")
    assert cli.post("/panel/ajustes", data={"valores": cuerpo, "csrf": "x"}, headers={**H, "Origin": "https://otro.example"}, follow_redirects=False).headers["location"].endswith("guardado=origen")
    assert cli.tabla.fila is None
    csrf = seguridad.token_csrf({})
    import json
    r = cli.post("/panel/ajustes", data={"valores": json.dumps({**ajustes.RECOMENDADO, "envios": 3}), "csrf": csrf}, headers=H, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"].endswith("guardado=ok") and json.loads(cli.tabla.fila["valores"])["envios"] == 3
    r = cli.post("/panel/ajustes", data={"valores": '{"envios": 50}', "csrf": csrf}, headers=H, follow_redirects=False)
    assert r.headers["location"].endswith("guardado=invalido")


def test_resumen_sin_bloque_de_estado_y_con_proveedores_arriba(cli, monkeypatch):
    from app import proveedores
    monkeypatch.setattr(proveedores, "estado_proveedores", lambda: {"general": {"estado": "operativo", "texto": "ok", "detalle": ""}, "proveedores": [
        {"id": "azure", "nombre": "Azure OpenAI", "modelo": "gpt-5-nano", "estado": "operativo", "mensaje": "m", "enlace": "https://a.example"}]})
    monkeypatch.setattr(principal.consultas, "metricas", lambda d: M)
    monkeypatch.setattr(principal, "_reintentos_ctx", lambda: {"r": {"reintentables": 2, "motivos": [], "proximo_auto": None}, "s": {"estado": "ninguna"}})
    t = cli.get("/panel", headers=H).text
    assert 'class="eg ' not in t and 'data-s="eg"' not in t and 'data-s="sal.' not in t and 'class="pv-k"' not in t
    assert t.count('id="pv-azure"') == 1 and t.index('id="pv-azure"') < t.index('id="rei"')


def test_negocio_sin_bloque_ni_ventas(monkeypatch):
    from app import negocio
    cli_ = [{"PartitionKey": "a", "nombre": "Cliente A", "plan_tipo": "basico", "plan_denuncias_mes": 150, "estado": "activo"}]
    n = negocio.construir(cli_, [], dias=30)
    t = TestClient(principal.app, base_url="https://t")
    monkeypatch.setattr(principal.negocio, "cargar", lambda **k: n)
    h = t.get("/panel/negocio", headers=H).text
    assert "¿Cómo va el negocio?" not in h and "Ventas" not in h and "Ingresos (UF)" in h
    assert [a["clientes"] for a in n["proyeccion"]["anios"]] == [5, 7, 9, 11, 13] or n["proyeccion"]["anios"][0]["clientes"] == 5
    assert n["proyeccion"]["anios"][-1]["clientes"] == 17 and n["proyeccion"]["anios"][0]["ventas"] == pytest.approx(638, abs=1)
    from app import glosario
    q = glosario.glosario()["ingresos_uf"]
    assert "capítulo" not in q["q"].lower() and "Tabla" not in q["q"] and len(q["q"]) <= 80


def test_kql_tokens_y_etapas_usan_los_eventos_reales():
    base = RAIZ / "docs" / "observabilidad" / "consultas"
    tok = (base / "front_tokens_por_modelo.kql").read_text()
    assert 'Properties.clase) == "etapa"' in tok and "solicitud_terminada" not in tok.split("\n", 2)[2]
    et = (base / "latencia_por_etapa.kql").read_text()
    assert "duracion_ms > 0" in et and '"recuperacion"' in et
    assert (RAIZ / "front" / "app" / "kql" / "latencia_por_etapa.kql").read_text() == et


def test_logo_sin_steps_en_el_front():
    css = (RAIZ / "front" / "app" / "estaticos" / "kerna.css").read_text()
    assert "steps(" not in css.replace("sin steps()", "")
    assert ".kl .camino{animation:rot 15s linear infinite reverse}" in css and ".kl .roseta{animation:rot 50s linear infinite}" in css
    assert "steps(" not in (RAIZ / "front" / "diseno-v2" / "maqueta.html").read_text().replace("sin steps()", "")


def test_estado_kpi_y_etiquetas_cortas():
    ctx = {"casos": 100}
    assert informe.estado_kpi("% con sugerencia", 10.6, ctx) == "bad"
    assert informe.estado_kpi("Revisión manual", 271, {"casos": 303}) == "bad"
    assert informe.estado_kpi("Recall@5 por artículo (global)", 0.492, ctx) == "bad"
    assert informe.estado_kpi("Recall@5 por artículo (global)", 0.85, ctx) == "ok"
    assert informe.estado_kpi("Modo respaldo", 3, ctx) == "warn" and informe.estado_kpi("Latencia P95 (máximo diario)", None, ctx) == "na"
    assert informe.estado_kpi("Tokens de entrada", 5, ctx) is None
    assert informe.ley_corta("Ley 21643") == "Ley 21.643 · Ley Karin" and informe.ley_corta(informe.NOMBRE_19628) == "Ley 19.628 · datos personales"
    assert informe.ley_corta("Ley 20393") == "Ley 20.393 · personas jurídicas"


def test_informe_compacto_html_y_pdf(monkeypatch):
    from test_front_informe import EVAL, FIN, INI, falso
    inf = informe.construir(INI, FIN, ejecutar=falso, evaluacion=EVAL)
    monkeypatch.setattr(principal, "_informe", lambda *a, **k: inf)
    c = TestClient(principal.app, base_url="https://t")
    # sin datos calculados la página sale como esqueleto y el cuerpo llega por /panel/informe/cuerpo
    shell = c.get("/panel/informe?dias=30", headers=H).text
    assert 'data-carga="/panel/informe/cuerpo?dias=30"' in shell and 'class="sk bn"' in shell
    h = c.get("/panel/informe/cuerpo?dias=30", headers=H).text
    assert "Contenido" not in h and "Responde en una página" not in h and "Es la evidencia central" not in h
    assert 'class="bn vdh s-' in h and h.count('class="kb s-') == 6 and 'role="tablist"' in h and "capítulo" not in h.lower()
    assert "<table" not in h and 'id="p-datos"' in h  # las tablas no van en el cuerpo
    d = c.get("/panel/informe/datos?dias=30", headers=H).text
    assert d.count("<details") >= 8 and "<table" in d and "<details open" not in d.split("<summary")[0]  # plegadas por defecto
    sec = vistas.informe(inf)
    cal = next(s for s in sec if s["id"] == "calidad")
    assert next(k for k in cal["kpis"] if k["etiqueta"].startswith("Recall@5 por artículo"))["e"] == "bad"
    pdf = exportar.a_pdf(inf)
    assert pdf.startswith(b"%PDF") and len(pdf) > 5000


def test_ajustes_guardan_con_origen_https_y_base_http_detras_del_proxy(cli):
    import json
    sitio = "app-kerna-dev-front-g6mzy.azurewebsites.net"
    proxy = {**H, "Host": sitio, "Origin": f"https://{sitio}", "X-Forwarded-Proto": "https", "X-Forwarded-Host": sitio, "Sec-Fetch-Site": "same-origin"}
    r = cli.post("/panel/ajustes", data={"valores": json.dumps({**ajustes.RECOMENDADO, "envios": 4}), "csrf": seguridad.token_csrf({})}, headers=proxy, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"].endswith("guardado=ok")


def test_ajustes_dicen_cuales_se_aplican_ya_y_el_panel_tiene_capas_vivas(cli):
    r = cli.get("/panel/ajustes", headers=H)
    assert r.text.count("class=\"ap-b ya\"") == 1 and r.text.count("class=\"ap-b no\"") == 3          # Procesamiento lo lee el conector; el resto no
    assert 'class="ap-st"' in r.text and "data-cap" in r.text and 'role="status"' in r.text and 'class="aj"' in r.text
    assert all(it["ya"] == (it["k"] in ajustes.APLICA_YA) for g in ajustes.GRUPOS for it in g["items"])


def test_guardar_por_fetch_devuelve_json_y_los_errores_no_son_redirecciones(cli):
    import json as _json
    from app import seguridad
    tok = seguridad.token_csrf({}); hj = {**H, "Accept": "application/json", "Origin": "https://t"}
    ok = cli.post("/panel/ajustes", headers=hj, data={"csrf": tok, "valores": _json.dumps({**ajustes.RECOMENDADO, "envios": 4})}, follow_redirects=False)
    assert ok.status_code == 200 and ok.json()["estado"] == "ok" and ok.json()["guardado_en"] and ajustes.cargar(cli.tabla)["valores"]["envios"] == 4
    assert cli.post("/panel/ajustes", headers=hj, data={"csrf": "malo", "valores": "{}"}, follow_redirects=False).json()["estado"] == "token"
    inv = cli.post("/panel/ajustes", headers=hj, data={"csrf": tok, "valores": _json.dumps({**ajustes.RECOMENDADO, "envios": 99})}, follow_redirects=False)
    assert inv.status_code == 400 and inv.json()["estado"] == "invalido"
    sin = cli.post("/panel/ajustes", headers={**H, "Origin": "https://t"}, data={"csrf": tok, "valores": _json.dumps(ajustes.RECOMENDADO)}, follow_redirects=False)
    assert sin.status_code == 303                                                                  # sin JavaScript sigue la redirección con aviso


def test_el_javascript_de_ajustes_solo_anima_transform_y_opacity_en_los_satelites():
    from pathlib import Path
    css = (Path(__file__).resolve().parents[2] / "front/app/estaticos/kerna.css").read_text()
    js = (Path(__file__).resolve().parents[2] / "front/app/estaticos/ajustes.js").read_text()
    assert ".sg{transition:transform" in css and "prefers-reduced-motion:reduce){.ap::before" in css and "steps(" not in css[css.index("v12 · Ajustes"):]
    assert "innerHTML = ORB" not in js and "ESC[g](h)" in js                                       # las escenas se crean una vez, no se redibujan
