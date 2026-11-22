"""Cuentas, roles y permisos del panel (usuario y contraseña, sesión, matriz de permisos, auditoría). Tablas simuladas, sin red."""
import json
import os
import re
import sys
import uuid
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "front"))
os.environ["FRONT_CLAVE"] = "clave-de-prueba"
os.environ.pop("FRONT_AUTH", None)

from fastapi import FastAPI  # noqa: E402
from fastapi.routing import APIRoute  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

import sesion_prueba  # noqa: E402
from app import cuentas, permisos, principal, seguridad  # noqa: E402
from sesion_prueba import H  # noqa: E402

ROLES = ["direccion", "operacion", "comercial", "evaluacion", "invitado"]


@pytest.fixture(autouse=True)
def _sin_limites(monkeypatch):
    seguridad._fallos.clear()
    monkeypatch.setattr(cuentas, "_enviar", lambda tipo, para, datos: False)   # sin correo: la contraseña temporal se ve en pantalla
    yield
    seguridad._fallos.clear()


@pytest.fixture
def tablas(monkeypatch):
    return sesion_prueba.instalar(monkeypatch)


@pytest.fixture
def web(tablas):
    return TestClient(principal.app, base_url="https://t", follow_redirects=False)


def ip(n):
    return {"X-Forwarded-For": f"10.0.0.{n}"}


def entrar(web, usuario, clave, n=1):
    return web.post("/acceso", data={"usuario": usuario, "clave": clave}, headers=ip(n))


def cookie_de(r):
    m = re.search(rf"{seguridad.COOKIE}=([^;]+)", r.headers.get("set-cookie", ""))
    return m.group(1) if m else None


def con_cookie(valor):
    return {"Cookie": f"{seguridad.COOKIE}={valor}"}, seguridad.token_csrf({seguridad.COOKIE: valor})


def eventos(tablas, accion=None):
    ev = [e for e in tablas[cuentas.T_EVENTOS].f.values()]
    return [e for e in ev if accion is None or e["accion"] == accion]


# ---- contraseñas ---------------------------------------------------------------------------------------------------------------------

def test_la_clave_se_guarda_como_hash_argon2id_con_sal(tablas):
    h1, h2 = cuentas.hash_clave("una clave larga de prueba"), cuentas.hash_clave("una clave larga de prueba")
    assert h1.startswith("$argon2id$") and h1 != h2 and "una clave larga" not in h1
    assert cuentas.clave_correcta(h1, "una clave larga de prueba") and not cuentas.clave_correcta(h1, "otra clave larga de prueba")
    assert not cuentas.clave_correcta("no-es-un-hash", "x")


def test_ninguna_tabla_guarda_claves_en_claro(tablas, web):
    web.post("/panel/cuentas/crear", headers={**H, "Accept": "application/json"}, data={"csrf": sesion_prueba.csrf(), "usuario": "ana", "nombre": "Ana", "correo": "ana@x.cl", "rol": "comercial"})
    volcado = json.dumps([dict(e) for t in tablas.values() for e in t.f.values()], default=str)
    assert "clave-de-prueba" not in volcado and "$argon2id$" in volcado


@pytest.mark.parametrize("clave,codigo", [("corta", "clave_corta"), ("a" * 200, "clave_larga"), ("aaaaaaaaaaaaaaaa", "clave_obvia"), ("ADMIN" * 3, None)])
def test_politica_de_clave(clave, codigo):
    if codigo:
        with pytest.raises(cuentas.ErrorCuenta) as e:
            cuentas.validar_clave(clave, "admin")
        assert e.value.codigo == codigo
    else:
        cuentas.validar_clave(clave, "admin")
    cuentas.validar_clave("una clave larga de verdad", "admin")
    with pytest.raises(cuentas.ErrorCuenta) as e:
        cuentas.validar_clave("maria.perez.larga", "maria.perez.larga")       # no puede ser el propio usuario
    assert e.value.codigo == "clave_obvia"
    with pytest.raises(cuentas.ErrorCuenta):
        cuentas.validar_clave("maria perez gonzalez", "mp", "Maria Perez Gonzalez")       # tampoco el nombre


def test_clave_temporal_es_aleatoria_y_cumple_la_politica():
    claves = {cuentas.clave_temporal() for _ in range(30)}
    assert len(claves) == 30 and all(len(c) >= cuentas.CLAVE_MIN for c in claves)


# ---- cuenta por defecto -----------------------------------------------------------------------------------------------------------

def test_cuenta_admin_por_defecto_con_la_clave_actual(monkeypatch):
    tablas = sesion_prueba.instalar(monkeypatch, con_admin=False)
    assert cuentas.asegurar_admin() is True and cuentas.asegurar_admin() is False
    f = tablas[cuentas.T_CUENTAS].f[(cuentas.PK, "admin")]
    assert f["rol"] == "direccion" and f["debe_cambiar_clave"] is False and f["activa"] is True
    assert f["hash"].startswith("$argon2id$") and cuentas.clave_correcta(f["hash"], "clave-de-prueba") and "clave-de-prueba" not in json.dumps(f)
    assert [e["accion"] for e in eventos(tablas)] == ["creada"]


def test_el_primer_acceso_crea_admin_si_la_tabla_esta_vacia(monkeypatch):
    sesion_prueba.instalar(monkeypatch, con_admin=False)
    web = TestClient(principal.app, base_url="https://t", follow_redirects=False)
    r = entrar(web, "admin", "clave-de-prueba")
    assert r.status_code == 303 and r.headers["location"] == "/panel" and cookie_de(r)


def test_sin_clave_compartida_no_se_crea_admin(monkeypatch):
    sesion_prueba.instalar(monkeypatch, con_admin=False)
    monkeypatch.setenv("FRONT_CLAVE", "@Microsoft.KeyVault(SecretUri=x)")
    assert cuentas.asegurar_admin() is False


def test_no_se_vuelve_a_crear_admin_si_ya_hay_cuentas(monkeypatch):
    tablas = sesion_prueba.instalar(monkeypatch, con_admin=False)
    f = sesion_prueba.cuenta("otra", "operacion")
    tablas[cuentas.T_CUENTAS].f[(cuentas.PK, "otra")] = f
    assert cuentas.asegurar_admin() is False and (cuentas.PK, "admin") not in tablas[cuentas.T_CUENTAS].f


# ---- login ------------------------------------------------------------------------------------------------------------------------------

def test_login_ok_pone_cookie_segura_y_registra_el_acceso(web, tablas):
    r = entrar(web, "Admin", "clave-de-prueba")
    set_cookie = r.headers["set-cookie"].lower()
    assert r.status_code == 303 and r.headers["location"] == "/panel"
    assert "httponly" in set_cookie and "secure" in set_cookie and "samesite=strict" in set_cookie and "max-age=28800" in set_cookie
    assert tablas[cuentas.T_CUENTAS].f[(cuentas.PK, "admin")]["ultimo_acceso"]
    assert web.get("/panel/demo", headers=con_cookie(cookie_de(r))[0]).status_code == 200
    assert [e["accion"] for e in eventos(tablas)] == ["acceso_ok"]


def test_cada_rol_aterriza_en_su_primera_pagina(web, tablas):
    for rol, destino in (("operacion", "/panel"), ("comercial", "/panel"), ("evaluacion", "/panel"), ("invitado", "/panel/demo")):
        tablas[cuentas.T_CUENTAS].f[(cuentas.PK, rol)] = sesion_prueba.cuenta(rol, rol)
        cuentas.olvidar_todo()
        assert entrar(web, rol, "clave-de-prueba").headers["location"] == destino


def test_login_fallido_mensaje_generico_igual_con_usuario_inexistente(web, tablas):
    a = entrar(web, "admin", "mala-mala-mala-1")
    b = entrar(web, "nadie", "mala-mala-mala-1", 2)
    quitar = lambda t, u: t.replace(f'value="{u}"', 'value=""')  # noqa: E731
    assert a.status_code == b.status_code == 401
    assert quitar(a.text, "admin") == quitar(b.text, "nadie") and "set-cookie" not in a.headers and "set-cookie" not in b.headers
    assert "Revisa tu usuario y contraseña" in a.text and "no existe" not in a.text.lower()
    assert [e["accion"] for e in eventos(tablas)] == ["acceso_fallido"]      # el usuario inexistente no deja evento


def test_login_con_campos_vacios_o_sin_usuario(web):
    assert entrar(web, "", "").status_code == 401
    assert web.post("/acceso", data={"clave": "clave-de-prueba"}, headers=ip(3)).status_code == 401


def test_bloqueo_de_la_cuenta_tras_cinco_fallos_aunque_cambie_la_ip(web, tablas):
    for n in range(cuentas.INTENTOS_MAX):
        assert entrar(web, "admin", "mala-mala-mala-1", n + 1).status_code == 401
    assert tablas[cuentas.T_CUENTAS].f[(cuentas.PK, "admin")]["bloqueada_hasta"] > cuentas._ahora()
    r = entrar(web, "admin", "clave-de-prueba", 50)      # la clave buena tampoco entra mientras dura el bloqueo
    assert r.status_code == 401 and "set-cookie" not in r.headers and "Revisa tu usuario y contraseña" in r.text
    assert "bloqueada" in [e["accion"] for e in eventos(tablas)]
    tablas[cuentas.T_CUENTAS].f[(cuentas.PK, "admin")]["bloqueada_hasta"] = "2020-01-01T00:00:00Z"
    cuentas.olvidar_todo()
    assert entrar(web, "admin", "clave-de-prueba", 51).status_code == 303


def test_un_acceso_correcto_reinicia_los_intentos(web, tablas):
    for n in range(3):
        entrar(web, "admin", "mala-mala-mala-1", n + 1)
    assert entrar(web, "admin", "clave-de-prueba", 9).status_code == 303
    assert tablas[cuentas.T_CUENTAS].f[(cuentas.PK, "admin")]["intentos_fallidos"] == 0


def test_limite_de_intentos_por_ip(web):
    for _ in range(5):
        assert entrar(web, "nadie", "x", 7).status_code == 401
    r = entrar(web, "admin", "clave-de-prueba", 7)
    assert r.status_code == 429 and "Demasiados intentos" in r.text


def test_cuenta_desactivada_no_entra(web, tablas):
    tablas[cuentas.T_CUENTAS].f[(cuentas.PK, "admin")]["activa"] = False
    r = entrar(web, "admin", "clave-de-prueba")
    assert r.status_code == 401 and "set-cookie" not in r.headers


def test_acceso_desde_otro_origen_se_rechaza(web):
    r = web.post("/acceso", data={"usuario": "admin", "clave": "clave-de-prueba"}, headers={"Origin": "https://otro.example"})
    assert r.status_code == 403 and "set-cookie" not in r.headers


def test_tabla_caida_responde_503_sin_dejar_pasar(web, monkeypatch):
    def rota(nombre):
        raise ConnectionError("tabla caída")
    monkeypatch.setattr(cuentas, "_tabla", rota)
    cuentas.olvidar_todo()
    assert web.get("/panel/demo", headers=H).status_code == 503
    assert entrar(web, "admin", "clave-de-prueba").status_code == 503


def test_salir_borra_la_cookie(web):
    r = web.get("/salir")
    assert r.status_code == 303 and r.headers["location"] == "/acceso" and "kerna_panel=" in r.headers["set-cookie"] and "max-age=0" in r.headers["set-cookie"].lower()
    assert web.post("/salir").status_code == 303


def test_pagina_de_acceso_es_un_login_con_usuario_y_clave(web):
    t = web.get("/acceso").text
    assert 'name="usuario"' in t and 'name="clave"' in t and 'type="password"' in t and "Entra a tu cuenta" in t and "Dirección" in t


# ---- sesión ---------------------------------------------------------------------------------------------------------------------------

def test_cookie_alterada_vencida_o_ajena_no_vale(web):
    valor = seguridad.emitir_cookie("admin", 1, "direccion")
    carga, firma = valor.split(".")
    assert web.get("/panel/demo", headers=con_cookie(valor)[0]).status_code == 200
    for malo in (carga + "." + "0" * len(firma), carga[:-2] + "xx." + firma, "basura", "", valor + "x", seguridad.emitir_cookie("admin", 1, "direccion", vida_s=-5)):
        r = web.get("/panel/demo", headers=con_cookie(malo)[0])
        assert r.status_code == 303 and r.headers["location"] == "/acceso"
    # un rol inflado en la carga, con la firma original, no sirve
    import base64
    falsa = base64.urlsafe_b64encode(json.dumps({"u": "admin", "r": "direccion", "v": 1, "e": 9999999999}).encode()).decode().rstrip("=")
    assert web.get("/panel/demo", headers=con_cookie(falsa + "." + firma)[0]).status_code == 303


def test_cambiar_la_clave_invalida_las_otras_sesiones_y_la_propia_sigue(web, tablas):
    antes = cookie_de(entrar(web, "admin", "clave-de-prueba"))
    h, tok = con_cookie(antes)
    r = web.post("/cuenta/clave", headers=h, data={"csrf": tok, "actual": "clave-de-prueba", "nueva": "una clave nueva y larga", "repetir": "una clave nueva y larga"})
    assert r.status_code == 303 and r.headers["location"] == "/cuenta?clave=ok"
    nueva = cookie_de(r)
    assert nueva and nueva != antes
    assert web.get("/panel/demo", headers=con_cookie(antes)[0]).status_code == 303                       # la sesión anterior murió
    assert web.get("/panel/demo", headers=con_cookie(nueva)[0]).status_code == 200                       # la de quien cambió la clave sigue
    assert entrar(web, "admin", "clave-de-prueba", 2).status_code == 401 and entrar(web, "admin", "una clave nueva y larga", 3).status_code == 303
    assert "clave_cambiada" in [e["accion"] for e in eventos(tablas)]


def test_cambio_de_rol_desactivar_y_eliminar_invalidan_la_sesion(web, tablas):
    hd, td = sesion_prueba.sesion(tablas, "direccion", "jefa")
    h, tok = sesion_prueba.sesion(tablas, "comercial", "pedro")
    assert web.get("/panel/negocio", headers=h).status_code == 200
    hj = {**hd, "Accept": "application/json"}
    def editar(**kw):
        return web.post("/panel/cuentas/editar", headers=hj, data={"csrf": td, "usuario": "pedro", "nombre": "Pedro", "correo": "pedro@x.cl", "rol": "comercial", "activa": "1", **kw})
    assert editar(rol="invitado").json()["estado"] == "ok"
    assert web.get("/panel/negocio", headers=h).status_code == 303
    nuevo = sesion_prueba.cabeceras("pedro", tablas[cuentas.T_CUENTAS].f[(cuentas.PK, "pedro")]["sesion"], "invitado")[0]
    cuentas.olvidar_todo()
    assert web.get("/panel/demo", headers=nuevo).status_code == 200
    assert editar(rol="invitado", activa="0").json()["estado"] == "ok" and web.get("/panel/demo", headers=nuevo).status_code == 303
    h2 = sesion_prueba.sesion(tablas, "invitado", "luis")[0]
    assert web.post("/panel/cuentas/eliminar", headers=hj, data={"csrf": td, "usuario": "luis", "confirmar": "luis"}).json()["estado"] == "ok"
    assert web.get("/panel/demo", headers=h2).status_code == 303


def test_restablecer_la_clave_cierra_sesiones_y_obliga_a_cambiarla(web, tablas):
    hd, td = sesion_prueba.sesion(tablas, "direccion", "jefa")
    h, _ = sesion_prueba.sesion(tablas, "operacion", "marta")
    r = web.post("/panel/cuentas/restablecer", headers={**hd, "Accept": "application/json"}, data={"csrf": td, "usuario": "marta"}).json()
    assert r["estado"] == "ok" and r["correo_enviado"] is False and len(r["clave"]) >= cuentas.CLAVE_MIN
    assert web.get("/panel", headers=h).status_code == 303
    assert entrar(web, "marta", "clave-de-prueba").status_code == 401
    ingreso = entrar(web, "marta", r["clave"], 4)
    assert ingreso.status_code == 303 and ingreso.headers["location"] == "/cuenta/clave"


def test_clave_temporal_obliga_a_cambiarla_antes_de_entrar(web, tablas):
    tablas[cuentas.T_CUENTAS].f[(cuentas.PK, "nuevo")] = sesion_prueba.cuenta("nuevo", "comercial", debe_cambiar_clave=True)
    r = entrar(web, "nuevo", "clave-de-prueba")
    assert r.headers["location"] == "/cuenta/clave"
    h, tok = con_cookie(cookie_de(r))
    assert web.get("/panel", headers=h).headers["location"] == "/cuenta/clave"
    assert web.get("/panel/negocio", headers=h).headers["location"] == "/cuenta/clave"
    j = web.post("/panel/clientes/crear", headers={**h, "Accept": "application/json"}, data={"csrf": tok})
    assert j.status_code == 403 and j.json()["estado"] == "cambiar_clave"
    pagina = web.get("/cuenta/clave", headers=h)
    assert pagina.status_code == 200 and "Elige tu contraseña" in pagina.text and 'href="/panel/negocio"' not in pagina.text
    mala = web.post("/cuenta/clave", headers=h, data={"csrf": tok, "actual": "clave-de-prueba", "nueva": "corta", "repetir": "corta"})
    assert mala.status_code == 400 and "al menos 12 caracteres" in mala.text
    r = web.post("/cuenta/clave", headers=h, data={"csrf": tok, "actual": "clave-de-prueba", "nueva": "ahora mi propia clave", "repetir": "ahora mi propia clave"})
    assert r.status_code == 303 and r.headers["location"] == "/panel"
    assert web.get("/panel/negocio", headers=con_cookie(cookie_de(r))[0]).status_code in (200, 502, 500) and tablas[cuentas.T_CUENTAS].f[(cuentas.PK, "nuevo")]["debe_cambiar_clave"] is False


def test_mi_cuenta_valida_la_clave_actual_la_repeticion_y_la_politica(web, tablas):
    h, tok = con_cookie(cookie_de(entrar(web, "admin", "clave-de-prueba")))
    def cambiar(**kw):
        return web.post("/cuenta/clave", headers=h, data={"csrf": tok, "actual": "clave-de-prueba", "nueva": "una clave nueva y larga", "repetir": "una clave nueva y larga", **kw})
    assert "actual no es correcta" in cambiar(actual="incorrecta-incorrecta").text
    assert "no coinciden" in cambiar(repetir="otra distinta y larga").text
    assert "al menos 12" in cambiar(nueva="corta", repetir="corta").text
    assert "distinta de la actual" in cambiar(nueva="clave-de-prueba", repetir="clave-de-prueba").text
    assert web.post("/cuenta/clave", headers=h, data={"actual": "x", "nueva": "y", "repetir": "y"}).status_code == 403          # sin token CSRF
    pagina = web.get("/cuenta", headers=h)
    assert pagina.status_code == 200 and "Mi cuenta" in pagina.text and "Admin" in pagina.text and "$argon2" not in pagina.text


def test_clave_actual_incorrecta_en_mi_cuenta_cuenta_como_intento_fallido(web, tablas):
    h, tok = con_cookie(cookie_de(entrar(web, "admin", "clave-de-prueba")))
    for _ in range(cuentas.INTENTOS_MAX):
        web.post("/cuenta/clave", headers=h, data={"csrf": tok, "actual": "mala-mala-mala-1", "nueva": "una clave nueva y larga", "repetir": "una clave nueva y larga"})
    assert tablas[cuentas.T_CUENTAS].f[(cuentas.PK, "admin")]["bloqueada_hasta"]


# ---- clave compartida (scripts) -------------------------------------------------------------------------------------------------------

def test_clave_compartida_solo_vale_en_api_y_solo_lectura(web, monkeypatch):
    from app import consultas
    monkeypatch.setattr(consultas, "filas", lambda t, d: [])
    x = {"X-Clave": "clave-de-prueba"}
    assert web.get("/api/metricas", headers=x).status_code == 200
    assert web.get("/api/metricas", headers={"X-Clave": "mala"}).status_code == 401
    for ruta in ("/panel", "/panel/cuentas", "/panel/ajustes", "/panel/demo", "/cuenta"):
        r = web.get(ruta, headers=x)
        assert r.status_code == 303 and r.headers["location"] == "/acceso", ruta
    r = web.post("/panel/ajustes", headers={**x, "Accept": "application/json"}, data={"csrf": "x", "valores": "{}"})
    assert r.status_code == 401


def test_modo_entra_da_rol_direccion_y_no_exige_cookie(web, monkeypatch):
    monkeypatch.setenv("FRONT_AUTH", "entra")
    e = {"x-ms-client-principal-id": "abc", "x-ms-client-principal-name": "ana@empresa.cl"}
    r = web.get("/panel/cuentas", headers=e)
    assert r.status_code == 200 and "Cuentas" in r.text and "ana@empresa.cl" in r.text
    assert web.get("/panel/cuentas").status_code == 303
    mi = web.get("/cuenta", headers=e)
    assert mi.status_code == 200 and "Microsoft Entra" in mi.text


# ---- matriz de permisos, ruta por ruta ------------------------------------------------------------------------------------------------

# Escrita aparte de permisos.py, a propósito: si alguien cambia la matriz, esta prueba lo nota.
EDITAN = {"resumen": {"direccion", "operacion", "comercial"}, "informe": {"direccion", "operacion", "comercial"}, "negocio": {"direccion", "comercial"},
          "clientes": {"direccion", "comercial"}, "ajustes": {"direccion", "operacion"}, "cuentas": {"direccion"}, "demo": set(ROLES)}
VEN = {"resumen": {"evaluacion"}, "informe": {"evaluacion"}, "negocio": {"evaluacion"}, "clientes": {"evaluacion"}, "ajustes": {"evaluacion"}, "cuentas": {"evaluacion"}, "demo": set()}


def seccion_esperada(ruta):
    if ruta.startswith(("/cuenta",)):
        return "propia"
    for prefijo, s in (("/panel/reintentar/estado", "resumen"), ("/panel/reintentar", "ajustes"), ("/panel/informe", "informe"), ("/panel/negocio", "negocio"),
                       ("/panel/clientes", "clientes"), ("/panel/ajustes", "ajustes"), ("/panel/cuentas", "cuentas"), ("/panel/demo", "demo"),
                       ("/api/negocio", "negocio"), ("/api/metricas", "resumen"), ("/api/proveedores", "resumen")):
        if ruta.startswith(prefijo):
            return s
    return "resumen" if ruta == "/panel" else None


def permitido(rol, seccion, metodo):
    if seccion == "propia":
        return True
    return rol in EDITAN[seccion] or (metodo == "GET" and rol in VEN[seccion])


def rutas_reales():
    salida = []
    for r in principal.app.routes:
        if isinstance(r, APIRoute) and r.path.startswith(("/panel", "/api", "/cuenta")) and "_prueba" not in r.path:
            salida.append((r.path.replace("{ext}", "pdf").replace("{ref}", str(uuid.uuid4())), sorted(r.methods - {"HEAD", "OPTIONS"})))
    return salida


def test_toda_ruta_del_panel_tiene_una_seccion_asignada():
    rutas = rutas_reales()
    assert len(rutas) >= 30
    for ruta, _ in rutas:
        assert permisos.seccion_de(ruta) is not None, f"{ruta} no tiene sección en permisos.RUTAS"
        assert permisos.seccion_de(ruta) == seccion_esperada(ruta), ruta
    assert {permisos.seccion_de(r) for r, _ in rutas} >= set(EDITAN)


@pytest.fixture
def espejo(tablas):
    """Una app con el mismo control de acceso (principal.control_acceso) y las mismas rutas, pero con manejadores triviales: así se prueba cada ruta real
    para cada rol sin ejecutar las consultas a Azure."""
    app = FastAPI()
    app.middleware("http")(principal.control_acceso)
    for ruta, metodos in rutas_reales():
        app.add_api_route(re.sub(r"/[0-9a-f-]{36}$", "/{ref}", ruta).replace("descargar.pdf", "descargar.{ext}"), lambda: {"ok": True}, methods=metodos)
    return TestClient(app, base_url="https://t", follow_redirects=False)


@pytest.mark.parametrize("rol", ROLES)
def test_matriz_de_permisos_ruta_por_ruta(espejo, tablas, rol):
    h, _ = sesion_prueba.sesion(tablas, rol)
    comprobadas = 0
    for ruta, metodos in rutas_reales():
        for m in metodos:
            r = espejo.request(m, ruta, headers={**h, "Accept": "application/json"})
            esperado = permitido(rol, seccion_esperada(ruta), m)
            assert (r.status_code == 200) == esperado, f"{rol} {m} {ruta}: {r.status_code}"
            if not esperado:
                assert r.status_code == 403 and r.json()["estado"] == "permiso", f"{rol} {m} {ruta}"
            comprobadas += 1
    assert comprobadas >= 30


def test_sin_sesion_ninguna_ruta_del_panel_responde_con_datos(web, monkeypatch):
    from app import consultas
    monkeypatch.setattr(consultas, "filas", lambda t, d: [])
    for ruta, metodos in rutas_reales():
        if ruta.startswith("/cuenta") or "salir" in ruta:
            continue
        for m in metodos:
            r = web.request(m, ruta, headers={"Accept": "application/json"}, data={} if m == "POST" else None)
            assert r.status_code in (401, 303), f"{m} {ruta}: {r.status_code}"


def test_ruta_nueva_sin_seccion_no_se_atiende_con_sesion(web, tablas):
    principal.app.add_api_route("/panel/_sin_seccion", lambda: {"ok": 1})
    assert web.get("/panel/_sin_seccion", headers=H).status_code == 404


def test_denegar_responde_con_la_pantalla_de_kerna(web, tablas):
    h, tok = sesion_prueba.sesion(tablas, "comercial")
    r = web.get("/panel/ajustes", headers=h)
    assert r.status_code == 403 and "Tu rol no tiene acceso a esta sección" in r.text and "Volver al panel" in r.text and 'id="sprites"' in r.text
    assert "sliders" not in r.text.split("<main")[1] and 'href="/panel/ajustes"' not in r.text
    r = web.get("/panel/cuentas", headers=h)
    assert r.status_code == 403 and "Pídele a Dirección" in r.text


# ---- menú por rol ----------------------------------------------------------------------------------------------------------------------

ENLACES = {"resumen": 'href="/panel"', "informe": 'href="/panel/informe"', "negocio": 'href="/panel/negocio"', "clientes": 'href="/panel/clientes"',
           "ajustes": 'href="/panel/ajustes"', "cuentas": 'href="/panel/cuentas"', "demo": 'href="/panel/demo"'}


@pytest.mark.parametrize("rol", ROLES)
def test_el_menu_muestra_solo_lo_permitido_con_usuario_rol_y_salir(web, tablas, rol):
    h, _ = sesion_prueba.sesion(tablas, rol, nombre="Persona Prueba")
    t = web.get("/panel/demo", headers=h).text
    for s, enlace in ENLACES.items():
        visible = rol in EDITAN[s] or rol in VEN[s]
        assert (enlace in t) == visible, f"{rol}: enlace a {s}"
    assert "Persona Prueba" in t and permisos.nombre_rol(rol) in t and 'href="/salir"' in t and 'href="/cuenta"' in t
    assert t.count('class="tabbar') == 1 and (rol != "invitado" or t.count('href="/panel/negocio"') == 0)


# ---- Evaluación: ve todo y no modifica nada --------------------------------------------------------------------------------------------

def test_evaluacion_ve_cuentas_con_historial_pero_sin_acciones(web, tablas):
    tablas[cuentas.T_CUENTAS].f[(cuentas.PK, "ana")] = sesion_prueba.cuenta("ana", "comercial")
    cuentas.registrar_evento("admin", "creada", "ana", "rol Comercial")
    cuentas.registrar_evento("ana", "acceso_ok", "ana")
    h, tok = sesion_prueba.sesion(tablas, "evaluacion")
    r = web.get("/panel/cuentas", headers=h)
    assert r.status_code == 200 and "Historial" in r.text and "Cuenta creada" in r.text and "Entró al panel" in r.text and "Solo puede ver" not in r.text
    assert "Tu rol solo puede ver esta sección" in r.text and "data-ro" in r.text
    assert "Crear cuenta" not in r.text and "data-editar" not in r.text and "data-eliminar" not in r.text and "cuentas.js" not in r.text
    for ruta in ("/panel/negocio", "/panel/clientes", "/panel/ajustes", "/panel/informe?dias=7", "/panel", "/panel/demo"):
        assert web.get(ruta, headers=h).status_code != 403, ruta


@pytest.mark.parametrize("ruta,datos", [
    ("/panel/ajustes", {"valores": "{}"}), ("/panel/reintentar", {}), ("/panel/clientes/crear", {"id": "acme-sa", "nombre": "Acme", "plan_tipo": "pro", "plan_denuncias_mes": "5"}),
    ("/panel/clientes/baja", {"id": "x"}), ("/panel/clientes/reactivar", {"id": "x"}), ("/panel/clientes/borrar-por-ley", {"id": "x", "confirmar": "x"}),
    ("/panel/cuentas/crear", {"usuario": "zeta", "nombre": "Z", "correo": "z@x.cl", "rol": "invitado"}), ("/panel/cuentas/editar", {"usuario": "admin", "nombre": "x", "correo": "x@x.cl", "rol": "invitado"}),
    ("/panel/cuentas/restablecer", {"usuario": "admin"}), ("/panel/cuentas/eliminar", {"usuario": "admin", "confirmar": "admin"})])
def test_evaluacion_no_puede_modificar_nada(web, tablas, ruta, datos):
    h, tok = sesion_prueba.sesion(tablas, "evaluacion")
    antes = json.dumps({k: [dict(e) for e in t.f.values()] for k, t in tablas.items()}, default=str, sort_keys=True)
    r = web.post(ruta, headers=h, data={"csrf": tok, **datos})              # formulario normal: pantalla de Kerna
    assert r.status_code == 403 and "Tu rol solo puede ver esta sección" in r.text and "Error 403" in r.text
    r = web.post(ruta, headers={**h, "Accept": "application/json"}, data={"csrf": tok, **datos})
    assert r.status_code == 403 and r.json()["estado"] == "permiso"
    assert json.dumps({k: [dict(e) for e in t.f.values()] for k, t in tablas.items()}, default=str, sort_keys=True) == antes


def test_evaluacion_ve_los_formularios_de_ajustes_y_clientes_deshabilitados(web, tablas, monkeypatch):
    from app import ajustes as aj, clientes as cli
    monkeypatch.setattr(aj, "cargar", lambda: {"valores": aj.RECOMENDADO, "guardado_en": None})
    monkeypatch.setattr(cli, "listar", lambda: {"activos": [], "bajas": [], "anonimizados": []})
    h, _ = sesion_prueba.sesion(tablas, "evaluacion")
    for ruta in ("/panel/ajustes", "/panel/clientes"):
        t = web.get(ruta, headers=h).text
        assert "data-ro" in t and "Tu rol solo puede ver esta sección" in t, ruta
    assert 'data-abrir="dlg-nuevo"' in web.get("/panel/clientes", headers=h).text            # el botón existe y el script lo deja sin uso
    assert "kerna.js" in web.get("/panel/clientes", headers=h).text
    d, _ = sesion_prueba.sesion(tablas, "direccion", "jefa")
    assert "data-ro" not in web.get("/panel/ajustes", headers=d).text.split("<main")[1]


def test_reintento_en_el_resumen_segun_el_rol(web, tablas):
    from app import reintentos
    macro = principal.plantillas.get_template("_reintento_accion.html").module.accion
    vm = reintentos.vista_boton(None)
    assert "data-reintentar" in str(macro(vm, "editar")) and "data-reintentar" not in str(macro(vm, "ver")) and "disabled" in str(macro(vm, "ver"))
    assert "data-reintentar" not in str(macro(vm, None))
    h, _ = sesion_prueba.sesion(tablas, "comercial")
    j = web.get("/panel/reintentar/estado", headers=h)
    assert j.status_code in (200, 502) and (j.status_code == 502 or "data-reintentar" not in j.json()["html"])


# ---- administración de cuentas ----------------------------------------------------------------------------------------------------------------

def post(web, ruta, tok, h=None, **datos):
    return web.post(ruta, headers={**(h or H), "Accept": "application/json", "Origin": "https://t"}, data={"csrf": tok, **datos})


def test_crear_cuenta_muestra_la_clave_temporal_una_vez_si_no_sale_el_correo(web, tablas):
    r = post(web, "/panel/cuentas/crear", sesion_prueba.csrf(), usuario="Maria.Perez", nombre="María Pérez", correo="MARIA@x.cl", rol="operacion").json()
    assert r["estado"] == "ok" and r["usuario"] == "maria.perez" and r["correo_enviado"] is False and len(r["clave"]) >= cuentas.CLAVE_MIN
    f = tablas[cuentas.T_CUENTAS].f[(cuentas.PK, "maria.perez")]
    assert f["rol"] == "operacion" and f["correo"] == "maria@x.cl" and f["debe_cambiar_clave"] is True and f["activa"] is True and cuentas.clave_correcta(f["hash"], r["clave"])
    assert r["clave"] not in json.dumps([dict(e) for e in tablas[cuentas.T_EVENTOS].f.values()]) and r["clave"] not in web.get("/panel/cuentas", headers=H).text
    ev = eventos(tablas, "creada")[0]
    assert ev["cuenta"] == "maria.perez" and ev["actor"] == "admin" and "correo no enviado" in ev["detalle"]
    assert entrar(web, "maria.perez", r["clave"]).headers["location"] == "/cuenta/clave"


def test_crear_con_correo_enviado_envia_y_muestra_la_clave_una_vez(web, tablas, monkeypatch):
    enviados = []
    monkeypatch.setattr(cuentas, "_enviar", lambda tipo, para, datos: enviados.append((tipo, para, datos)) or True)
    r = post(web, "/panel/cuentas/crear", sesion_prueba.csrf(), usuario="luis", nombre="Luis", correo="luis@x.cl", rol="comercial").json()
    assert r["estado"] == "ok" and r["correo_enviado"] is True and r["clave"]   # un correo mal escrito no deja la cuenta sin entrada
    tipo, para, datos = enviados[0]
    assert tipo == "cuenta_creada" and para == "luis@x.cl" and set(datos) == {"usuario", "nombre", "rol", "clave_temporal", "url"} and datos["rol"] == "Comercial"
    assert r["clave"] == datos["clave_temporal"]
    assert datos["url"] == "https://t/acceso" and cuentas.clave_correcta(tablas[cuentas.T_CUENTAS].f[(cuentas.PK, "luis")]["hash"], datos["clave_temporal"])
    assert "clave temporal enviada por correo" in eventos(tablas, "creada")[0]["detalle"] and datos["clave_temporal"] not in json.dumps([dict(e) for e in tablas[cuentas.T_EVENTOS].f.values()])


def test_los_otros_tipos_de_correo_llevan_los_datos_del_contrato(web, tablas, monkeypatch):
    enviados = []
    monkeypatch.setattr(cuentas, "_enviar", lambda tipo, para, datos: enviados.append((tipo, set(datos))) or True)
    tablas[cuentas.T_CUENTAS].f[(cuentas.PK, "ana")] = sesion_prueba.cuenta("ana", "comercial")
    cuentas.olvidar_todo()
    post(web, "/panel/cuentas/editar", sesion_prueba.csrf(), usuario="ana", nombre="Ana", correo="ana@prueba.cl", rol="operacion", activa="1")
    post(web, "/panel/cuentas/restablecer", sesion_prueba.csrf(), usuario="ana")
    post(web, "/panel/cuentas/eliminar", sesion_prueba.csrf(), usuario="ana", confirmar="ana")
    assert enviados == [("rol_cambiado", {"usuario", "nombre", "rol"}), ("clave_restablecida", {"usuario", "nombre", "clave_temporal", "url"}), ("cuenta_eliminada", {"usuario", "nombre"})]
    h, tok = con_cookie(cookie_de(entrar(web, "admin", "clave-de-prueba")))
    web.post("/cuenta/clave", headers=h, data={"csrf": tok, "actual": "clave-de-prueba", "nueva": "otra clave bien larga", "repetir": "otra clave bien larga"})
    assert enviados[-1] == ("clave_cambiada", {"usuario", "nombre"})


def test_sin_modulo_de_correo_no_se_rompe(monkeypatch):
    monkeypatch.undo()
    monkeypatch.setitem(sys.modules, "app.correo", None)         # importar falla, como si el archivo no existiera
    assert cuentas._enviar("cuenta_creada", "a@x.cl", {}) is False
    assert cuentas._enviar("cuenta_creada", "", {}) is False
    import types
    roto = types.ModuleType("app.correo")
    roto.enviar = lambda *a: (_ for _ in ()).throw(RuntimeError("smtp caído"))
    monkeypatch.setitem(sys.modules, "app.correo", roto)
    monkeypatch.setattr("app.correo", roto, raising=False)
    assert cuentas._enviar("cuenta_creada", "a@x.cl", {}) is False
    roto.enviar = lambda *a: True
    assert cuentas._enviar("cuenta_creada", "a@x.cl", {}) is True


@pytest.mark.parametrize("datos", [dict(usuario="ab", nombre="A", correo="a@x.cl", rol="comercial"), dict(usuario="con espacio", nombre="A", correo="a@x.cl", rol="comercial"),
                                   dict(usuario="valido", nombre="", correo="a@x.cl", rol="comercial"), dict(usuario="valido", nombre="A", correo="no-es-correo", rol="comercial"),
                                   dict(usuario="valido", nombre="A", correo="a@x.cl", rol="superadmin")])
def test_crear_valida_los_datos(web, tablas, datos):
    r = post(web, "/panel/cuentas/crear", sesion_prueba.csrf(), **datos)
    assert r.status_code == 400 and r.json()["estado"] == "invalido" and len(tablas[cuentas.T_CUENTAS].f) == 1


def test_no_se_repite_un_usuario(web, tablas):
    assert post(web, "/panel/cuentas/crear", sesion_prueba.csrf(), usuario="admin", nombre="Otro", correo="o@x.cl", rol="invitado").status_code == 409


def test_editar_cambia_datos_rol_y_estado_con_eventos(web, tablas):
    tablas[cuentas.T_CUENTAS].f[(cuentas.PK, "ana")] = sesion_prueba.cuenta("ana", "comercial")
    cuentas.olvidar_todo()
    r = post(web, "/panel/cuentas/editar", sesion_prueba.csrf(), usuario="ana", nombre="Ana Torres", correo="ana.t@x.cl", rol="evaluacion", activa="0")
    assert r.json()["estado"] == "ok"
    f = tablas[cuentas.T_CUENTAS].f[(cuentas.PK, "ana")]
    assert f["nombre"] == "Ana Torres" and f["rol"] == "evaluacion" and f["activa"] is False and f["sesion"] == 2
    acciones = [e["accion"] for e in eventos(tablas)]
    assert {"editada", "rol_cambiado", "desactivada"} <= set(acciones)
    assert post(web, "/panel/cuentas/editar", sesion_prueba.csrf(), usuario="fantasma", nombre="x", correo="x@x.cl", rol="invitado").status_code == 404


def test_no_se_puede_eliminar_a_si_mismo_ni_dejar_el_sistema_sin_direccion(web, tablas):
    tok = sesion_prueba.csrf()
    assert post(web, "/panel/cuentas/eliminar", tok, usuario="admin", confirmar="admin").json()["estado"] == "propia"
    assert post(web, "/panel/cuentas/restablecer", tok, usuario="admin").json()["estado"] == "propia"
    assert post(web, "/panel/cuentas/editar", tok, usuario="admin", nombre="A", correo="a@x.cl", rol="direccion", activa="0").json()["estado"] == "propia"
    # una segunda Dirección: la primera puede ser eliminada por la segunda, pero nunca la última
    h2, tok2 = sesion_prueba.sesion(tablas, "direccion", "jefa")
    assert post(web, "/panel/cuentas/eliminar", tok2, h2, usuario="admin", confirmar="admin").json()["estado"] == "ok"
    assert post(web, "/panel/cuentas/eliminar", tok2, h2, usuario="jefa", confirmar="jefa").json()["estado"] == "propia"
    # desde otra cuenta con permiso no hay otra: Evaluación no puede, y cambiar el rol de la última Dirección tampoco
    tablas[cuentas.T_CUENTAS].f[(cuentas.PK, "admin")] = sesion_prueba.cuenta("admin", "direccion")
    cuentas.olvidar_todo()
    tablas[cuentas.T_CUENTAS].f[(cuentas.PK, "admin")]["activa"] = False
    cuentas.olvidar_todo()
    assert post(web, "/panel/cuentas/eliminar", tok2, h2, usuario="admin", confirmar="admin").json()["estado"] == "ok"   # inactiva: no cuenta como Dirección
    assert (cuentas.PK, "jefa") in tablas[cuentas.T_CUENTAS].f
    with pytest.raises(cuentas.ErrorCuenta) as e:
        cuentas.eliminar("alguien", "jefa")
    assert e.value.codigo == "ultima_direccion"
    with pytest.raises(cuentas.ErrorCuenta) as e:
        cuentas.editar("alguien", "jefa", {"nombre": "J", "correo": "j@x.cl", "rol": "comercial"})
    assert e.value.codigo == "ultima_direccion"
    with pytest.raises(cuentas.ErrorCuenta) as e:
        cuentas.editar("alguien", "jefa", {"nombre": "J", "correo": "j@x.cl", "rol": "direccion"}, activa=False)
    assert e.value.codigo == "ultima_direccion"


def test_eliminar_exige_escribir_el_usuario(web, tablas):
    tablas[cuentas.T_CUENTAS].f[(cuentas.PK, "ana")] = sesion_prueba.cuenta("ana", "comercial")
    cuentas.olvidar_todo()
    assert post(web, "/panel/cuentas/eliminar", sesion_prueba.csrf(), usuario="ana", confirmar="otra").json()["estado"] == "confirmacion"
    assert (cuentas.PK, "ana") in tablas[cuentas.T_CUENTAS].f
    assert post(web, "/panel/cuentas/eliminar", sesion_prueba.csrf(), usuario="ana", confirmar="ANA").json()["estado"] == "ok"
    assert (cuentas.PK, "ana") not in tablas[cuentas.T_CUENTAS].f and "eliminada" in [e["accion"] for e in eventos(tablas)]


def test_la_pagina_de_cuentas_lista_estados_y_botones_para_direccion(web, tablas):
    tablas[cuentas.T_CUENTAS].f[(cuentas.PK, "ana")] = sesion_prueba.cuenta("ana", "comercial", debe_cambiar_clave=True)
    tablas[cuentas.T_CUENTAS].f[(cuentas.PK, "beto")] = sesion_prueba.cuenta("beto", "invitado", activa=False)
    cuentas.olvidar_todo()
    t = web.get("/panel/cuentas", headers=H).text
    for esperado in ("Quién puede entrar", "Crear cuenta", "Clave temporal", "Desactivada", "Comercial", "Invitado", "Nunca", "Historial", "cuentas.js", "eres tú"):
        assert esperado in t, esperado
    assert t.count("data-restablecer") == 2 and t.count("data-eliminar") == 2   # sin esos botones sobre la propia cuenta
    assert "$argon2" not in t and "hash" not in t.lower().replace("historial", "")


def test_csrf_y_origen_en_las_acciones_de_cuentas(web, tablas):
    datos = dict(usuario="zeta", nombre="Zeta", correo="z@x.cl", rol="invitado")
    assert post(web, "/panel/cuentas/crear", "token-falso", **datos).json()["estado"] == "token"
    assert post(web, "/panel/cuentas/crear", "", **datos).status_code == 403
    r = web.post("/panel/cuentas/crear", headers={**H, "Accept": "application/json", "Origin": "https://otro.example"}, data={"csrf": sesion_prueba.csrf(), **datos})
    assert r.status_code == 403 and r.json()["estado"] == "origen"
    otra_sesion = sesion_prueba.cabeceras("admin", 1, "direccion")                      # token de otra cookie
    assert post(web, "/panel/cuentas/crear", seguridad.token_csrf({seguridad.COOKIE: "ajena"}), **datos).status_code == 403
    assert otra_sesion[1] != "" and (cuentas.PK, "zeta") not in tablas[cuentas.T_CUENTAS].f
    sin_sesion = web.post("/panel/cuentas/crear", headers={"Accept": "application/json"}, data={"csrf": sesion_prueba.csrf(), **datos})
    assert sin_sesion.status_code == 401 and (cuentas.PK, "zeta") not in tablas[cuentas.T_CUENTAS].f
    form = web.post("/panel/cuentas/crear", headers={**H}, data={"csrf": "mal", **datos})            # sin JSON: pantalla de Kerna, no JSON crudo
    assert form.status_code == 403 and "Error 403" in form.text


def test_el_historial_registra_accesos_y_cambios(web, tablas):
    entrar(web, "admin", "mala-mala-mala-1")
    entrar(web, "admin", "clave-de-prueba", 2)
    t = web.get("/panel/cuentas", headers=H).text
    assert "Intento fallido" in t and "Entró al panel" in t and "intento fallido 1 de 5" in t
    evs = cuentas.eventos(10)
    assert [e["accion"] for e in evs] == ["acceso_ok", "acceso_fallido"] and all(set(e) == {"fecha", "actor", "accion", "cuenta", "detalle"} for e in evs)
    assert set(cuentas.ACCIONES) >= {e["accion"] for e in evs}



def test_la_ip_del_limite_es_la_que_agrega_el_proxy_no_la_que_manda_el_cliente():
    from starlette.requests import Request as R
    def req(xff):
        return R({"type": "http", "headers": [(b"x-forwarded-for", xff.encode())] if xff else [], "client": ("10.0.0.9", 1)})
    assert principal._ip(req("6.6.6.6, 200.1.2.3:51000")) == "200.1.2.3"   # el primero lo inventa quien llama
    assert principal._ip(req("200.1.2.3:51000")) == "200.1.2.3"
    assert principal._ip(req("[2001:db8::1]:443")) == "2001:db8::1"
    assert principal._ip(req("")) == "10.0.0.9"


def test_ajustes_incompletos_se_rechazan_sin_tocar_lo_guardado(web, monkeypatch):
    from app import ajustes as aj
    guardados = []
    monkeypatch.setattr(aj, "guardar", lambda v: guardados.append(v) or {"guardado_en": "x"})
    r = post(web, "/panel/ajustes", sesion_prueba.csrf(), valores="{}")
    assert r.status_code == 400 and r.json()["estado"] == "invalido" and not guardados


def test_limite_de_correos_llega_a_la_pantalla(web, tablas, monkeypatch):
    from app import correo
    def falla(tipo, para, datos):
        cuentas._MOTIVO.update(correo_motivo="limite", correo_espera_min=12)
        return False
    monkeypatch.setattr(cuentas, "_enviar", falla)
    r = post(web, "/panel/cuentas/crear", sesion_prueba.csrf(), usuario="lia", nombre="Lia", correo="lia@x.cl", rol="comercial").json()
    assert r["correo_enviado"] is False and r["correo_motivo"] == "limite" and r["correo_espera_min"] == 12 and r["clave"] is None
    assert "límite de la demo" in eventos(tablas, "creada")[0]["detalle"]
