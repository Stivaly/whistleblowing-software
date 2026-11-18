"""Clientes del panel (listar, agregar, baja suave y borrado por ley) y su efecto en la autenticación del núcleo. Sin red."""
import hashlib
import os
import re
import sys
from pathlib import Path

import pytest
from azure.core.exceptions import ResourceNotFoundError

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "front"))
os.environ["FRONT_CLAVE"] = "clave-de-prueba"

from app import clientes as cl  # noqa: E402
from kerna_comun import clientes_esquema as esq  # noqa: E402
from kerna_nucleo.auth import Autenticador  # noqa: E402
from kerna_nucleo.clientes_vivos import ClientesVivos  # noqa: E402


class Tabla:
    def __init__(self):
        self.f = {}

    def _ok(self, e, filtro):
        m = re.fullmatch(r"(PartitionKey|RowKey) eq '(.*)'", filtro or "")
        return True if not m else e[m.group(1)] == m.group(2)

    def list_entities(self):
        return [dict(e) for e in self.f.values()]

    def query_entities(self, filtro=None, select=None):
        return [dict(e) for e in self.f.values() if self._ok(e, filtro)]

    def get_entity(self, pk, rk):
        if (pk, rk) not in self.f:
            raise ResourceNotFoundError("no existe")
        return dict(self.f[(pk, rk)])

    def create_entity(self, e):
        self.f[(e["PartitionKey"], e["RowKey"])] = dict(e)

    def upsert_entity(self, e, mode="replace"):
        self.f[(e["PartitionKey"], e["RowKey"])] = dict(e)

    def update_entity(self, e, mode="merge"):
        self.f[(e["PartitionKey"], e["RowKey"])].update(e)

    def delete_entity(self, pk, rk):
        self.f.pop((pk, rk), None)


@pytest.fixture
def tablas():
    d = {n: Tabla() for n in ("clientes", "solicitud", "usodiario", "sugerenciaarticulo", "valoracion", "clasificacion")}
    d["clientes"].create_entity({"PartitionKey": "veridy-dev", "RowKey": "perfil", "nombre": "Veridy", "estado": "activo"})
    return lambda n: d[n], d


def nuevo(f, **kw):
    return cl.crear({"id": "acme-sa", "nombre": "Acme S.A.", "rubro": "Minería", "plan_tipo": "pro", "plan_denuncias_mes": 200, **kw}, tablas=f,
                    ahora=None)


def test_crear_guarda_solo_el_hash_y_muestra_la_clave_una_vez(tablas):
    f, d = tablas
    r = nuevo(f)
    fila = d["clientes"].f[("acme-sa", "perfil")]
    assert r["id"] == "acme-sa" and r["secreto"].startswith("kc_")
    assert fila["secreto_sha256"] == hashlib.sha256(r["secreto"].encode()).hexdigest()
    assert r["secreto"] not in str(fila) and fila["estado"] == "activo" and fila["cliente"] == "acme-sa"


def test_crear_rechaza_repetidos_y_datos_malos(tablas):
    f, _ = tablas
    nuevo(f)
    with pytest.raises(cl.ErrorCliente) as e:
        nuevo(f)
    assert e.value.codigo == "existe"
    for malo in ({"id": "A"}, {"id": "con espacio"}, {"nombre": ""}, {"plan_tipo": "oro"}, {"plan_denuncias_mes": 0}, {"plan_denuncias_mes": "x"}):
        with pytest.raises(cl.ErrorCliente) as e:
            nuevo(f, **{"id": "otro-cli", **malo})
        assert e.value.codigo == "invalido"


def test_listar_agrupa_por_estado(tablas):
    f, _ = tablas
    nuevo(f)
    cl.dar_de_baja("acme-sa", tablas=f)
    cl.crear({"id": "beta-ltda", "nombre": "Beta", "plan_tipo": "basico", "plan_denuncias_mes": 50}, tablas=f)
    r = cl.listar(f)
    assert [c["id"] for c in r["activos"]] == ["beta-ltda", "veridy-dev"] and [c["id"] for c in r["bajas"]] == ["acme-sa"]
    assert next(c for c in r["activos"] if c["id"] == "veridy-dev")["protegido"] is True


def test_baja_suave_conserva_todo_y_se_puede_reactivar(tablas):
    f, d = tablas
    nuevo(f)
    d["solicitud"].create_entity({"PartitionKey": "acme-sa", "RowKey": "r1", "cliente": "acme-sa", "id_solicitud": "s1"})
    cl.dar_de_baja("acme-sa", tablas=f)
    assert d["clientes"].f[("acme-sa", "perfil")]["estado"] == "baja" and ("acme-sa", "r1") in d["solicitud"].f
    with pytest.raises(cl.ErrorCliente):
        cl.dar_de_baja("acme-sa", tablas=f)
    cl.reactivar("acme-sa", tablas=f)
    assert d["clientes"].f[("acme-sa", "perfil")]["estado"] == "activo"


def test_el_cliente_de_la_plataforma_no_se_toca(tablas):
    f, _ = tablas
    for fn in (cl.dar_de_baja, cl.reactivar, cl.previa, cl.anonimizar):
        with pytest.raises(cl.ErrorCliente) as e:
            fn("veridy-dev", tablas=f)
        assert e.value.codigo == "protegido"


def prepara_ejecucion(d):
    d["solicitud"].create_entity({"PartitionKey": "acme-sa", "RowKey": "r1", "cliente": "acme-sa", "id_empresa": "acme", "id_solicitud": "s1", "estado": "completada"})
    d["solicitud"].create_entity({"PartitionKey": "otro", "RowKey": "r2", "cliente": "otro", "id_empresa": "otro", "id_solicitud": "s2"})
    for dia in ("2026-11-01", "2026-11-02"):
        d["usodiario"].create_entity({"PartitionKey": "acme-sa", "RowKey": dia, "denuncias": 3})
    d["clasificacion"].create_entity({"PartitionKey": "s1", "RowKey": "n1", "observacion": "Caso de Acme S.A. y ACME-SA, ver acme", "resultado": "aceptada"})
    d["valoracion"].create_entity({"PartitionKey": "s1", "RowKey": "n2", "observacion": "sin nombres", "valoracion": "util"})
    d["sugerenciaarticulo"].create_entity({"PartitionKey": "s1", "RowKey": "a1", "cita": "Ley 21.643 art. 2", "explicacion": "texto"})


def test_previa_cuenta_sin_tocar(tablas):
    f, d = tablas
    nuevo(f)
    prepara_ejecucion(d)
    assert cl.previa("acme-sa", tablas=f) == {"id": "acme-sa", "nombre": "Acme S.A.", "solicitudes": 1, "dias_de_uso": 2}
    assert ("acme-sa", "r1") in d["solicitud"].f


def test_borrado_por_ley_reemplaza_todo_lo_que_identifica_y_conserva_la_ejecucion(tablas):
    f, d = tablas
    nuevo(f)
    prepara_ejecucion(d)
    r = cl.anonimizar("acme-sa", referencia="  solicitud   escrita 2026-11-18 ", tablas=f, nuevo_id=lambda: "uuid-sustituto")
    u = "uuid-sustituto"
    assert r == {"uuid": u, "filas": 3, "textos": 1}
    # la fila del cliente desaparece y no queda rastro del identificador, del nombre ni del id de empresa
    assert ("acme-sa", "perfil") not in d["clientes"].f
    todo = " ".join(str(v) for t in d.values() for v in t.f.values()).lower()
    assert "acme" not in todo and "minería" not in todo
    # los datos de ejecución siguen, bajo el uuid
    assert d["solicitud"].f[(u, "r1")]["cliente"] == u and d["solicitud"].f[(u, "r1")]["id_empresa"] == u and d["solicitud"].f[(u, "r1")]["estado"] == "completada"
    assert d["usodiario"].f[(u, "2026-11-01")]["denuncias"] == 3 and len([k for k in d["usodiario"].f if k[0] == u]) == 2
    assert ("otro", "r2") in d["solicitud"].f  # otro cliente intacto
    assert d["clasificacion"].f[("s1", "n1")]["observacion"] == f"Caso de {u} y {u}, ver {u}" and d["clasificacion"].f[("s1", "n1")]["resultado"] == "aceptada"
    assert d["valoracion"].f[("s1", "n2")]["observacion"] == "sin nombres"
    assert d["sugerenciaarticulo"].f[("s1", "a1")]["cita"] == "Ley 21.643 art. 2"  # texto de la ley: no es del cliente
    p = d["clientes"].f[(u, "perfil")]
    assert p["estado"] == "anonimizado" and p["nombre"] == u and p["rubro"] == "" and "secreto_sha256" not in p
    assert p["filas_anonimizadas"] == 3 and p["referencia"] == "solicitud escrita 2026-11-18" and p["plan_tipo"] == "pro"
    assert [c["id"] for c in cl.listar(f)["anonimizados"]] == [u]
    with pytest.raises(cl.ErrorCliente) as e:
        cl.anonimizar(u, tablas=f)
    assert e.value.codigo == "estado"


def test_borrado_por_ley_cortado_se_reanuda_con_el_mismo_uuid(tablas):
    f, d = tablas
    nuevo(f)
    prepara_ejecucion(d)
    original = d["usodiario"].delete_entity
    llamadas = []

    def falla(pk, rk):
        llamadas.append(1)
        if len(llamadas) == 2:
            raise RuntimeError("corte")
        original(pk, rk)
    d["usodiario"].delete_entity = falla
    with pytest.raises(RuntimeError):
        cl.anonimizar("acme-sa", tablas=f, nuevo_id=lambda: "primero")
    assert d["clientes"].f[("acme-sa", "perfil")]["anonimizando_como"] == "primero" and d["clientes"].f[("acme-sa", "perfil")]["estado"] == "baja"
    d["usodiario"].delete_entity = original
    r = cl.anonimizar("acme-sa", tablas=f, nuevo_id=lambda: "segundo")
    assert r["uuid"] == "primero" and ("acme-sa", "perfil") not in d["clientes"].f
    assert not [k for k in d["usodiario"].f if k[0] == "acme-sa"] and len([k for k in d["usodiario"].f if k[0] == "primero"]) == 2


# ---- el núcleo: quién puede entrar
def reloj():
    return 1000.0


def auth(tabla, env=None):
    return Autenticador(env or {}, "s" * 32, reloj, ClientesVivos(tabla, ttl_s=0))


def test_el_cliente_nuevo_entra_con_su_clave_y_deja_de_entrar_al_darlo_de_baja(tablas):
    f, d = tablas
    r = nuevo(f)
    a = auth(d["clientes"])
    t = a.emitir("acme-sa", r["secreto"])
    assert t and a.verificar(t) == "acme-sa"
    assert a.emitir("acme-sa", "kc_otra") is None
    cl.dar_de_baja("acme-sa", tablas=f)
    assert a.emitir("acme-sa", r["secreto"]) is None and a.verificar(t) is None
    cl.reactivar("acme-sa", tablas=f)
    assert a.emitir("acme-sa", r["secreto"])


def test_la_baja_tambien_corta_a_un_cliente_de_las_variables_de_entorno():
    t = Tabla()
    t.create_entity({"PartitionKey": "viejo", "RowKey": "perfil", "estado": "baja"})
    env = {"viejo": {"secreto_sha256": esq.hash_secreto("x"), "cliente": "viejo"}, "veridy-dev": {"secreto_sha256": esq.hash_secreto("y"), "cliente": "veridy-dev"}}
    a = auth(t, env)
    assert a.emitir("viejo", "x") is None and a.emitir("veridy-dev", "y")


def test_si_la_tabla_falla_se_conserva_lo_ultimo_y_las_variables():
    class Rota:
        def query_entities(self, *a, **k):
            raise RuntimeError("sin red")
    env = {"veridy-dev": {"secreto_sha256": esq.hash_secreto("y"), "cliente": "veridy-dev"}}
    assert auth(Rota(), env).emitir("veridy-dev", "y")


# ---- rutas del panel
from fastapi.testclient import TestClient  # noqa: E402

from app import principal, seguridad  # noqa: E402
from test_front_vistas import H  # noqa: E402


@pytest.fixture
def web(tablas, monkeypatch):
    f, d = tablas
    monkeypatch.setattr(cl, "_tabla", f)
    c = TestClient(principal.app, base_url="https://t")
    c.d = d
    c.hj = {**H, "Accept": "application/json", "Origin": "https://t"}
    c.tok = seguridad.token_csrf({})
    return c


def test_pagina_clientes_pide_sesion_y_lista(web):
    assert web.get("/panel/clientes", follow_redirects=False).headers["location"] == "/acceso"
    web.post("/panel/clientes/crear", headers=web.hj, data={"csrf": web.tok, "id": "acme-sa", "nombre": "Acme S.A.", "plan_tipo": "pro", "plan_denuncias_mes": "200"})
    r = web.get("/panel/clientes", headers=H)
    assert r.status_code == 200 and "Acme S.A." in r.text and "Cuenta de la plataforma" in r.text and "Agregar cliente" in r.text
    assert "ejemplo" not in r.text.lower() and 'href="/panel/clientes"' in web.get("/panel", headers=H).text


def test_las_acciones_exigen_sesion_origen_y_token(web):
    datos = {"csrf": web.tok, "id": "acme-sa", "nombre": "Acme", "plan_tipo": "pro", "plan_denuncias_mes": "5"}
    assert web.post("/panel/clientes/crear", headers={"Accept": "application/json"}, data=datos).status_code == 401
    assert web.post("/panel/clientes/crear", headers={**web.hj, "Origin": "https://otro.example"}, data=datos).json()["estado"] == "origen"
    assert web.post("/panel/clientes/crear", headers=web.hj, data={**datos, "csrf": "mal"}).json()["estado"] == "token"
    assert web.get("/panel/clientes/previa?id=acme-sa", headers={"Accept": "application/json"}).status_code == 401
    assert ("acme-sa", "perfil") not in web.d["clientes"].f


def test_crear_devuelve_la_clave_una_vez_y_rechaza_repetido(web):
    datos = {"csrf": web.tok, "id": "acme-sa", "nombre": "Acme", "plan_tipo": "pro", "plan_denuncias_mes": "5"}
    r = web.post("/panel/clientes/crear", headers=web.hj, data=datos)
    assert r.json()["estado"] == "ok" and r.json()["secreto"].startswith("kc_")
    assert web.post("/panel/clientes/crear", headers=web.hj, data=datos).status_code == 409
    assert web.post("/panel/clientes/crear", headers=web.hj, data={**datos, "id": "X"}).status_code == 400


def test_baja_reactivar_y_cuenta_protegida(web):
    web.post("/panel/clientes/crear", headers=web.hj, data={"csrf": web.tok, "id": "acme-sa", "nombre": "Acme", "plan_tipo": "pro", "plan_denuncias_mes": "5"})
    assert web.post("/panel/clientes/baja", headers=web.hj, data={"csrf": web.tok, "id": "acme-sa"}).json()["estado"] == "ok"
    assert web.post("/panel/clientes/baja", headers=web.hj, data={"csrf": web.tok, "id": "acme-sa"}).status_code == 409
    assert web.post("/panel/clientes/reactivar", headers=web.hj, data={"csrf": web.tok, "id": "acme-sa"}).json()["estado"] == "ok"
    assert web.post("/panel/clientes/baja", headers=web.hj, data={"csrf": web.tok, "id": "veridy-dev"}).status_code == 403
    assert web.post("/panel/clientes/borrar-por-ley", headers=web.hj, data={"csrf": web.tok, "id": "veridy-dev", "confirmar": "veridy-dev"}).status_code == 403


def test_borrar_por_ley_exige_escribir_el_identificador(web):
    web.post("/panel/clientes/crear", headers=web.hj, data={"csrf": web.tok, "id": "acme-sa", "nombre": "Acme", "plan_tipo": "pro", "plan_denuncias_mes": "5"})
    web.d["usodiario"].create_entity({"PartitionKey": "acme-sa", "RowKey": "2026-11-01", "denuncias": 1})
    assert web.get("/panel/clientes/previa?id=acme-sa", headers=web.hj).json() == {"estado": "ok", "id": "acme-sa", "nombre": "Acme", "solicitudes": 0, "dias_de_uso": 1}
    mal = web.post("/panel/clientes/borrar-por-ley", headers=web.hj, data={"csrf": web.tok, "id": "acme-sa", "confirmar": "otro"})
    assert mal.status_code == 400 and mal.json()["estado"] == "confirmacion" and ("acme-sa", "perfil") in web.d["clientes"].f
    ok = web.post("/panel/clientes/borrar-por-ley", headers=web.hj, data={"csrf": web.tok, "id": "acme-sa", "confirmar": " ACME-SA ", "referencia": "carta 12"})
    j = ok.json()
    assert j["estado"] == "ok" and j["filas"] == 1 and ("acme-sa", "perfil") not in web.d["clientes"].f and (j["uuid"], "2026-11-01") in web.d["usodiario"].f
    assert "Borrados por ley" in web.get("/panel/clientes", headers=H).text and j["uuid"] in web.get("/panel/clientes", headers=H).text


def test_el_despliegue_del_front_empaqueta_cada_modulo_de_kerna_comun_que_importa():
    """Fallo real: un módulo nuevo de kerna_comun no estaba en el zip y el panel desplegado no arrancó (503)."""
    import re
    usados = set()
    for f in (RAIZ / "front" / "app").glob("*.py"):
        usados |= set(re.findall(r"from kerna_comun import ([a-z_]+)(?: as \w+)?", f.read_text()))
        usados |= set(re.findall(r"from kerna_comun\.([a-z_]+) import", f.read_text()))
    script = (RAIZ / "front" / "desplegar.sh").read_text()
    assert usados, "el panel usa kerna_comun"
    faltan = {m for m in usados if f"{m}.py" not in script}
    assert not faltan, f"desplegar.sh no copia: {sorted(faltan)}"
