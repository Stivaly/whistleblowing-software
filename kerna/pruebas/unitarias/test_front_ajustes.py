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
    assert r.status_code == 200 and "Todavía no se aplican" not in r.text and "todavía no se aplican" in r.text
    assert "Valores recomendados" in r.text and "ejemplo" not in r.text.lower()
    assert 'href="/panel/ajustes"' in cli.get("/panel", headers=H).text


def test_ajustes_guardar_exige_sesion_origen_y_csrf(cli):
    cuerpo = '{"envios": 3}'
    assert cli.post("/panel/ajustes", data={"valores": cuerpo, "csrf": "x"}).status_code == 401
    assert cli.post("/panel/ajustes", data={"valores": cuerpo, "csrf": "mal"}, headers=H).status_code == 403
    assert cli.post("/panel/ajustes", data={"valores": cuerpo, "csrf": "x"}, headers={**H, "Origin": "https://otro.example"}).status_code == 403
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
    assert "capítulo 25" in q["q"] and "2026" in q["c"] and "40.000" in q["c"]


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
    h = TestClient(principal.app, base_url="https://t").get("/panel/informe?dias=30", headers=H).text
    assert "Contenido" not in h and "Responde en una página" not in h and "Es la evidencia central" not in h
    assert "¿Cómo se resolvieron?" in h and h.count("<h4 class=\"inf-s\">Casos por día") == 1 and "10 nov" in h and "Modo oficial" not in h
    assert "s-bad" in h and "Ley 21.643 · Ley Karin" in h and "…" not in h.split('id="cobertura"')[1].split("</section>")[0]
    sec = vistas.informe(inf)
    cal = next(s for s in sec if s["id"] == "calidad")
    assert next(k for k in cal["kpis"] if k["etiqueta"].startswith("Recall@5 por artículo"))["e"] == "bad"
    pdf = exportar.a_pdf(inf)
    assert pdf.startswith(b"%PDF") and len(pdf) > 5000
