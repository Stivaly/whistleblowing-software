"""Pruebas del reintento manual del panel: resumen, solicitud atómica, CSRF, sesión y doble clic."""
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "front"))
os.environ["FRONT_CLAVE"] = "clave-de-prueba"
os.environ["LOG_ANALYTICS_WORKSPACE_ID"] = "ws-prueba"

from azure.core.exceptions import ResourceExistsError, ResourceModifiedError, ResourceNotFoundError  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import consultas, principal, proveedores, reintentos, seguridad  # noqa: E402


class TablaFalsa:
    """Imita la tabla: create falla si existe; update con etag falla si cambió."""
    def __init__(self):
        self.fila, self.version = None, 0

    def get_entity(self, pk, rk):
        if self.fila is None:
            raise ResourceNotFoundError("no")
        e = dict(self.fila); e = type("E", (dict,), {})(e); e.metadata = {"etag": str(self.version)}
        return e

    def create_entity(self, ent):
        if self.fila is not None:
            raise ResourceExistsError("existe")
        self.fila, self.version = dict(ent), 1

    def update_entity(self, ent, mode="merge", etag=None, match_condition=None):
        if etag != str(self.version):
            raise ResourceModifiedError("cambió")
        self.fila, self.version = dict(ent), self.version + 1


def test_solicitar_es_atomica_y_el_doble_clic_no_dispara_dos_veces():
    t = TablaFalsa()
    assert reintentos.solicitar(t) == "solicitado"
    assert reintentos.solicitar(t) == "ya_solicitado"
    assert reintentos.estado_solicitud(t)["estado"] == "solicitado"
    t.fila["estado"] = "atendido"                        # el conector la atendió
    assert reintentos.solicitar(t) == "solicitado"       # se puede pedir otra vez


def test_solicitar_pierde_la_carrera_si_otro_cambio_la_fila():
    t = TablaFalsa(); reintentos.solicitar(t); t.fila["estado"] = "atendido"
    original = t.update_entity
    def carrera(*a, **k):
        t.version += 1                                   # otro proceso escribió entre la lectura y el reemplazo
        return original(*a, **k)
    t.update_entity = carrera
    assert reintentos.solicitar(t) == "ya_solicitado"


def test_resumen_en_lenguaje_simple_y_sin_identificadores():
    def ej(texto, dias):
        if "conector_reintento" in texto:
            return [{"evento": "conector_reintento", "eventos": 3, "ultimo": "2026-11-12T09:00:00Z"}, {"evento": "conector_reproceso", "eventos": 1, "ultimo": "2026-11-12T10:00:00Z"}]
        return [{"motivo": "cadena_agotada", "casos": 5}, {"motivo": "validacion_fallida", "casos": 2}]
    r = reintentos.resumen(ejecutar=ej, ahora=datetime(2026, 11, 12, 12, tzinfo=timezone.utc))
    assert r["reintentables"] == 4 and r["total"] == 7
    assert r["motivos"][0]["texto"] == "Los modelos de IA no estaban disponibles" and r["motivos"][1]["se_reintenta"] is False
    assert r["proximo_auto"].startswith("2026-11-13T09:00")
    assert not any("ref" in k for m in r["motivos"] for k in m)


@pytest.fixture
def cliente(monkeypatch):
    t = TablaFalsa()
    monkeypatch.setattr(reintentos, "_tabla", lambda: t)
    monkeypatch.setattr(consultas, "filas", lambda x, d: [{"motivo": "cadena_agotada", "casos": 2, "evento": "conector_reintento", "eventos": 1, "ultimo": "2026-11-12T09:00:00Z"}])
    monkeypatch.setattr(proveedores, "_get", lambda u: (_ for _ in ()).throw(TimeoutError()))
    consultas._cache.clear(); proveedores._cache.update(t=0.0, datos=None)
    c = TestClient(principal.app, follow_redirects=False)
    c.tabla = t
    return c


H = {"X-Clave": "clave-de-prueba"}


def token():
    return seguridad.token_csrf({})


def test_post_exige_sesion_csrf_y_mismo_origen(cliente):
    # nunca una página JSON en blanco: sin sesión va al acceso; el resto vuelve al Resumen con un aviso
    r = cliente.post("/panel/reintentar", data={"csrf": token()})
    assert r.status_code == 303 and r.headers["location"] == "/acceso"
    assert cliente.post("/panel/reintentar", headers=H, data={"csrf": "malo"}).headers["location"] == "/panel?reintento=token"
    assert cliente.post("/panel/reintentar", headers=H, data={}).headers["location"] == "/panel?reintento=token"
    assert cliente.post("/panel/reintentar", headers={**H, "Origin": "https://otro.example"}, data={"csrf": token()}).headers["location"] == "/panel?reintento=origen"
    assert cliente.post("/panel/reintentar", headers={**H, "Sec-Fetch-Site": "cross-site"}, data={"csrf": token()}).headers["location"] == "/panel?reintento=origen"
    assert cliente.tabla.fila is None                     # nada se escribió


def test_flujo_confirmar_pedir_y_doble_clic(cliente):
    assert cliente.get("/panel/reintentar").status_code == 303   # sin sesión: al acceso
    c = cliente.get("/panel/reintentar", headers=H)
    assert c.status_code == 200 and "Sí, reintentar" in c.text and token() in c.text
    r = cliente.post("/panel/reintentar", headers=H, data={"csrf": token()})
    assert r.status_code == 303 and r.headers["location"] == "/panel?reintento=solicitado"
    r2 = cliente.post("/panel/reintentar", headers=H, data={"csrf": token()})
    assert r2.headers["location"] == "/panel?reintento=ya_solicitado"
    p = cliente.get("/panel?reintento=ya_solicitado", headers=H)
    assert "Reintentando… espera" in p.text and "Ya había un reintento pedido" in p.text and "disabled" in p.text   # el botón sigue, en gris


def test_panel_muestra_bloque_y_no_se_rompe_si_la_tabla_falla(cliente, monkeypatch):
    p = cliente.get("/panel", headers=H)
    assert "En espera" in p.text and "Reintentar ahora" in p.text and "Los modelos de IA no estaban disponibles" in p.text
    monkeypatch.setattr(reintentos, "_tabla", lambda: (_ for _ in ()).throw(RuntimeError("sin acceso")))
    from app import cache
    cache.vaciar()  # la caché compartida guardó el resumen anterior
    p = cliente.get("/panel", headers=H)
    assert p.status_code == 200 and "En espera" not in p.text
    assert cliente.post("/panel/reintentar", headers=H, data={"csrf": token()}).headers["location"] == "/panel?reintento=error"


def test_origen_https_con_base_http_detras_del_proxy(cliente):
    """App Service entrega http a la app aunque el navegador use https: el Origin https del mismo host debe pasar."""
    sitio = "app-kerna-dev-front-g6mzy.azurewebsites.net"
    proxy = {**H, "Host": sitio, "Origin": f"https://{sitio}", "X-Forwarded-Proto": "https", "X-Forwarded-Host": sitio, "Sec-Fetch-Site": "same-origin"}
    r = cliente.post("/panel/reintentar", headers=proxy, data={"csrf": token()})
    assert r.status_code == 303 and r.headers["location"] == "/panel?reintento=solicitado" and cliente.tabla.fila is not None


def test_el_modal_pide_json_y_recibe_el_resultado_sin_salir_de_la_pagina(cliente):
    r = cliente.post("/panel/reintentar", headers={**H, "Accept": "application/json"}, data={"csrf": token()})
    assert r.status_code == 200 and r.json() == {"estado": "solicitado"}
    r = cliente.post("/panel/reintentar", headers={**H, "Accept": "application/json"}, data={"csrf": "malo"})
    assert r.status_code == 403 and r.json() == {"estado": "token"}   # el modal lo muestra en lenguaje simple


def test_el_modal_y_el_enlace_de_reintentar(cliente):
    p = cliente.get("/panel", headers=H).text
    assert '<dialog id="dlg-rei"' in p and "data-dlg-ok" in p
    assert re.search(r'<a class="btn btn-pri" href="/panel/reintentar" data-reintentar>', p)   # sin JS sigue siendo un enlace a la confirmación


AHORA = datetime(2026, 11, 13, 3, 30, tzinfo=timezone.utc)


def test_boton_normal_nunca_desaparece_y_muestra_el_resultado():
    vm = reintentos.vista_boton({"estado": "ninguna"}, AHORA)
    assert vm["modo"] == "normal" and vm["texto"] == "Reintentar ahora" and "resultado" not in vm
    vm = reintentos.vista_boton({"estado": "atendido", "reintentados": "99", "con_sugerencia": "74", "fin": "2026-11-13T03:00:00Z"}, AHORA)
    assert vm["modo"] == "normal" and vm["resultado"] == "99 reintentados · 74 con sugerencia"
    assert "incompleto" in reintentos.vista_boton({"estado": "atendido", "reintentados": 10, "con_sugerencia": 3, "incompleto": "true"}, AHORA)["resultado"]


def test_boton_en_curso_gris_con_progreso_y_tooltip_con_desde_cuando_y_cuanto_falta():
    s = {"estado": "en_curso", "inicio": "2026-11-13T03:10:00Z", "total": "99", "resueltos": "33", "eta_s": "600", "actualizado_en": "2026-11-13T03:29:50Z"}
    vm = reintentos.vista_boton(s, AHORA)
    assert vm["modo"] == "curso" and vm["texto"] == "Reintentando… espera" and vm["sub"] == "33 de 99" and vm["avance"] == 33
    assert "13 nov 03:10 UTC" in vm["ayuda"] and "Faltan unos 10 min" in vm["ayuda"] and "33 de 99" in vm["ayuda"] and not vm["detenido"]
    assert "Aún sin estimación" in reintentos.vista_boton({**s, "eta_s": "-1"}, AHORA)["ayuda"]
    quieto = reintentos.vista_boton({**s, "actualizado_en": "2026-11-13T03:00:00Z"}, AHORA)
    assert quieto["detenido"] and "puede estar detenido" in quieto["ayuda"]
    sol = reintentos.vista_boton({"estado": "solicitado", "solicitado_en": "2026-11-13T03:25:00Z"}, AHORA)
    assert sol["modo"] == "curso" and "hace 5 min" in sol["ayuda"] and "Veridy" in sol["ayuda"]


def test_endpoint_de_estado_entrega_html_del_boton_y_hora_del_ultimo_dato(cliente):
    assert cliente.get("/panel/reintentar/estado").status_code == 401
    cliente.tabla.fila = {"estado": "en_curso", "inicio": "2026-11-13T03:10:00Z", "total": 10, "resueltos": 4, "actualizado_en": "2026-11-13T03:29:50Z"}
    from app import cache
    cache.vaciar()
    j = cliente.get("/panel/reintentar/estado", headers=H).json()
    assert j["modo"] == "curso" and "btn-off" in j["html"] and "disabled" in j["html"] and "Reintentando… espera" in j["html"] and "rei-sp" in j["html"]
    assert j["fuente"] == "conector" and j["dato"] == "2026-11-13T03:29:50Z"                      # fila del conector: segundos de latencia, sin Log Analytics
    cliente.tabla.fila = {"estado": "atendido", "reintentados": 5, "con_sugerencia": 3}
    cache.vaciar()
    j = cliente.get("/panel/reintentar/estado", headers=H).json()
    assert j["modo"] == "normal" and "data-reintentar" in j["html"] and "5 reintentados · 3 con sugerencia" in j["html"]


def test_en_vivo_lleva_la_hora_del_ultimo_dato_y_el_aviso_de_demora(cliente):
    cliente.tabla.fila = {"estado": "ninguna", "actualizado_en": "2026-11-13T03:29:50Z"}
    from app import cache, glosario
    cache.vaciar()
    p = cliente.get("/panel", headers=H).text
    assert 'data-dato="2026-11-13T03:29:50Z"' in p and 'data-fuente="conector"' in p
    g = glosario.glosario()["envivo"] if hasattr(glosario, "glosario") else None
    from app.principal import _GLOS
    assert "último dato recibido" in _GLOS["envivo"]["q"] and "unos minutos" in _GLOS["envivo"]["c"]
