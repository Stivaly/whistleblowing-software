"""Pruebas de los clientes HTTP (Veridy y núcleo) con respx, de la lectura del caso y del estado."""
import base64

import httpx
import pytest
import respx
from conector_apoyo import AUDITOR, CUENTA, caso_json
from nacl.pwhash import argon2id

from kerna_conector import lector_casos, nucleo as nuc, veridy as ver
from kerna_conector.config import Config, ErrorConfiguracion
from kerna_conector.estado import EstadoSqlite, abrir_estado

pr = lambda x: pytest.mark.pr(x)  # noqa: E731
URL = "https://veridy.test"
SAL = base64.b64encode(bytes(range(16))).decode()


def test_derivacion_de_password_vector_conocido():
    esperado = base64.b64encode(argon2id.kdf(32, "clave-de-prueba".encode(), bytes(range(16)),
                                             opslimit=16, memlimit=1 << 27)).decode()
    assert ver.derivar_password("clave-de-prueba", SAL) == esperado == "+9ASMd0wWB+IemVICj18sbkZvMtOPQ5f/z54kijqiTE="


def test_prueba_de_trabajo_vector_conocido():
    c = ver.prueba_de_trabajo("id-de-prueba", SAL)
    assert c == 58
    h = argon2id.kdf(32, b"id-de-prueba58", bytes(range(16)), opslimit=1, memlimit=1 << 20)
    assert h[31] == 0


def _montar_login(mock, sesiones):
    mock.post(URL + "/api/auth/type").respond(200, json={"type": "key", "salt": SAL})
    mock.post(URL + "/api/auth/token").respond(200, json={"id": "id-de-prueba", "salt": SAL})
    mock.post(URL + "/api/auth/authentication").mock(side_effect=[
        httpx.Response(201, json={"id": s, "user_id": CUENTA, "role": "receiver"}) for s in sesiones])


@respx.mock(assert_all_called=False)
def test_login_cabeceras_y_cuerpo(respx_mock):
    _montar_login(respx_mock, ["S1"])
    respx_mock.get(URL + "/api/recipient/rtips").respond(200, json=[])
    respx_mock.delete(URL + "/api/auth/session").respond(200, json={})
    c = ver.ClienteVeridy(URL, "kerna-conector", "clave-de-prueba")
    assert c.listar_casos() == [] and c.id_usuario == CUENTA
    auth = [x for x in respx_mock.calls if x.request.url.path == "/api/auth/authentication"][0].request
    assert auth.headers["x-token"] == "id-de-prueba:58"
    cuerpo = httpx.Response(200, content=auth.content).json()
    assert cuerpo["password"] == "+9ASMd0wWB+IemVICj18sbkZvMtOPQ5f/z54kijqiTE=" and cuerpo["tid"] == 0
    lista = [x for x in respx_mock.calls if x.request.url.path == "/api/recipient/rtips"][0].request
    assert lista.headers["x-session"] == "S1"
    c.cerrar_sesion()
    assert respx_mock.calls.last.request.method == "DELETE" and respx_mock.calls.last.request.headers["x-session"] == "S1"


@pytest.mark.parametrize("codigo", [401, 412])
@respx.mock(assert_all_called=False)
def test_renueva_sesion_vencida(respx_mock, codigo):
    _montar_login(respx_mock, ["S1", "S2"])
    respx_mock.get(URL + "/api/recipient/rtips/abc").mock(side_effect=[
        httpx.Response(codigo, json={"error_code": 10}), httpx.Response(200, json={"id": "abc"})])
    c = ver.ClienteVeridy(URL, "u", "clave-de-prueba")
    assert c.leer_caso("abc") == {"id": "abc"}
    ultimo = respx_mock.calls.last.request
    assert ultimo.headers["x-session"] == "S2"


@respx.mock(assert_all_called=False)
def test_renueva_sesion_antes_de_vencer_por_edad(respx_mock):
    _montar_login(respx_mock, ["S1", "S2"])
    respx_mock.get(URL + "/api/recipient/rtips").respond(200, json=[])
    t = [0.0]
    c = ver.ClienteVeridy(URL, "u", "clave-de-prueba", reloj=lambda: t[0])
    c.listar_casos()
    t[0] = 91
    c.listar_casos()
    assert respx_mock.calls.last.request.headers["x-session"] == "S2"


@respx.mock(assert_all_called=False)
def test_casos_inaccesibles_y_nota_siempre_interna(respx_mock):
    _montar_login(respx_mock, ["S1"])
    respx_mock.get(URL + "/api/recipient/rtips/x").respond(403, json={})
    ruta = respx_mock.post(URL + "/api/recipient/rtips/y/comments").respond(201, json={"id": "n1"})
    c = ver.ClienteVeridy(URL, "u", "clave-de-prueba")
    with pytest.raises(ver.CasoNoAccesible):
        c.leer_caso("x")
    assert c.publicar_nota("y", "hola")["id"] == "n1"
    assert httpx.Response(200, content=ruta.calls.last.request.content).json() == {"content": "hola", "visibility": "internal"}


@respx.mock(assert_all_called=False)
def test_login_rechazado(respx_mock):
    respx_mock.post(URL + "/api/auth/type").respond(200, json={"type": "key", "salt": SAL})
    respx_mock.post(URL + "/api/auth/token").respond(200, json={"id": "i", "salt": SAL})
    respx_mock.post(URL + "/api/auth/authentication").respond(401, json={})
    with pytest.raises(ver.ErrorVeridy) as exc:
        ver.ClienteVeridy(URL, "u", "x").listar_casos()
    assert exc.value.codigo == 401


# ---- núcleo --------------------------------------------------------------------------------------------------
API = "https://nucleo.test"


def _cliente(esperas, reloj=lambda: 0.0):
    return nuc.ClienteNucleo(API, "cid", "sec", "emp", dormir=esperas.append, reloj=reloj)


@respx.mock(assert_all_called=False)
def test_nucleo_token_en_cache_y_renovacion(respx_mock):
    t = [0.0]
    tok = respx_mock.post(API + "/oauth/token").mock(side_effect=[
        httpx.Response(200, json={"access_token": "A", "expires_in": 600}),
        httpx.Response(200, json={"access_token": "B", "expires_in": 600})])
    respx_mock.get(url__regex=API + r"/v1/casos/.*/sugerencia").respond(200, json={"estado": "pendiente"})
    c = _cliente([], reloj=lambda: t[0])
    c.consultar_sugerencia("r1")
    c.consultar_sugerencia("r1")
    assert tok.call_count == 1
    t[0] = 545  # faltan menos de 60 s: se renueva antes de vencer
    c.consultar_sugerencia("r1")
    assert tok.call_count == 2 and respx_mock.calls.last.request.headers["authorization"] == "Bearer B"


@respx.mock(assert_all_called=False)
def test_nucleo_reintenta_con_espera_creciente_y_se_declara_no_disponible(respx_mock):
    respx_mock.post(API + "/oauth/token").respond(200, json={"access_token": "A", "expires_in": 600})
    ruta = respx_mock.post(API + "/v1/casos").mock(side_effect=[
        httpx.ConnectError("x"), httpx.Response(503), httpx.Response(202, json={"id_solicitud": "s", "estado": "pendiente"})])
    esperas = []
    assert _cliente(esperas).enviar_caso("r", "t")["id_solicitud"] == "s"
    assert esperas == [1.0, 2.0] and ruta.call_count == 3
    ruta.mock(side_effect=None, return_value=httpx.Response(500))
    esperas.clear()
    with pytest.raises(nuc.NucleoNoDisponible):
        _cliente(esperas).enviar_caso("r", "t")
    assert esperas == [1.0, 2.0, 4.0]


@respx.mock(assert_all_called=False)
def test_nucleo_no_reintenta_4xx_y_renueva_token_ante_401(respx_mock):
    respx_mock.post(API + "/oauth/token").mock(side_effect=[
        httpx.Response(200, json={"access_token": "A", "expires_in": 600}),
        httpx.Response(200, json={"access_token": "B", "expires_in": 600})])
    respx_mock.get(url__regex=API + r"/v1/casos/.*/sugerencia").mock(side_effect=[
        httpx.Response(401), httpx.Response(404)])
    esperas = []
    c = _cliente(esperas)
    assert c.consultar_sugerencia("r") is None and esperas == []
    assert respx_mock.calls.call_count == 4  # token, 401, nuevo token, 404
    respx_mock.post(API + "/v1/casos/r/feedback").respond(422)
    with pytest.raises(nuc.ErrorNucleo):
        c.enviar_feedback("r", "n", "s", "arriba")
    assert esperas == []


# ---- lector de casos / config / estado ----------------------------------------------------------------------
def test_lector_solo_relato():
    r = lector_casos.extraer_relato(caso_json("c", relato="Hechos graves"))
    assert r == "Describa los hechos: Hechos graves\nTipo de hecho: Acoso laboral\nLugar\n  Dónde ocurrió: Oficina central"
    assert "Camila" not in r and "foto" not in r and "Identidad" not in r


def test_lector_ignora_respuestas_cifradas_sin_descifrar():
    c = caso_json("c")
    c["questionnaires"][0]["answers"] = "cifrado=="
    assert lector_casos.extraer_relato(c) == ""


def test_config_entorno():
    with pytest.raises(ErrorConfiguracion):
        Config.desde_entorno({})
    e = {"VERIDY_URL": "https://v/", "VERIDY_USUARIO": "u", "VERIDY_PASSWORD": "p", "KERNA_API_URL": "https://k/",
         "KERNA_CLIENT_ID": "i", "KERNA_CLIENT_SECRET": "s"}
    c = Config.desde_entorno(e)
    assert c.veridy_url == "https://v" and c.intervalo_s == 30 and c.veridy_tid == 0
    assert "p" != repr(c) and "s'" not in repr(c)


def test_estado_esquema_idempotente_y_persistente(tmp_path):
    ruta = str(tmp_path / "x.db")
    e = EstadoSqlite(ruta)
    e.crear_esquema()
    e.registrar("c", "ref1")
    e.registrar("c", "ref2")  # la ref_opaca queda fija
    e.marcar_procesado("c", "feedback", "n1", "x")
    e.cerrar()
    e = abrir_estado("sqlite:///" + ruta)
    assert e.obtener("c").ref_opaca == "ref1" and e.objeto_procesado("c", "feedback", "n1")
    assert not e.objeto_procesado("c", "feedback", "n2")


def test_estado_postgres_adapta_marcadores(monkeypatch):
    from kerna_conector import estado as est
    llamadas = []

    class Cur:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def execute(self, sql, p): llamadas.append((sql, p))
        def fetchall(self): return []

    class Con:
        closed = False
        def cursor(self): return Cur()
    monkeypatch.setattr(est.EstadoPostgres, "_conexion", lambda self: Con())
    e = est.EstadoPostgres("postgresql://x")
    e.objeto_procesado("c", "t", "k")
    assert "%s" in llamadas[-1][0] and "?" not in llamadas[-1][0]


def test_main_sin_configuracion_sale_con_2(monkeypatch):
    from kerna_conector.__main__ import main
    for v in ("VERIDY_URL", "VERIDY_USUARIO", "VERIDY_PASSWORD", "KERNA_API_URL", "KERNA_CLIENT_ID", "KERNA_CLIENT_SECRET"):
        monkeypatch.delenv(v, raising=False)
    assert main(["--una-pasada"]) == 2


def test_main_una_pasada_codigo_segun_resultado(monkeypatch):
    from kerna_conector import __main__ as m
    from kerna_conector.reconciliacion import ResultadoPasada
    for k, v in {"VERIDY_URL": "https://v", "VERIDY_USUARIO": "u", "VERIDY_PASSWORD": "p", "KERNA_API_URL": "https://k",
                 "KERNA_CLIENT_ID": "i", "KERNA_CLIENT_SECRET": "s", "CONECTOR_ESTADO": "sqlite:///:memory:"}.items():
        monkeypatch.setenv(k, v)
    resultados = iter([ResultadoPasada(), ResultadoPasada(errores=1)])
    monkeypatch.setattr(m, "ejecutar_pasada", lambda *a, **k: next(resultados))
    assert m.main(["--una-pasada"]) == 0
    assert m.main(["--una-pasada"]) == 1
