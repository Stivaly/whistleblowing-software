"""Apoyos de las pruebas del núcleo: reloj controlado, proveedores falsos y armado de la aplicación."""
from __future__ import annotations

import asyncio
import hashlib
import json
import re
import uuid

import httpx

from kerna_nucleo.almacen import AlmacenMemoria
from kerna_nucleo.api import crear_app
from kerna_nucleo.config import Config
from kerna_nucleo.proveedores import ErrorProveedor, Proveedores
from kerna_nucleo.proveedores.gemini import RespuestaLLM

SECRETO = "secreto-de-prueba"
FLASH, LITE, GEMMA = "gemini-3.8-flash", "gemini-3.5-flash-lite", "gemma-4-31b-it"

FRAGMENTOS = [
    {"fragmento_id": "ley21643_art1", "id_norma": "n1", "norma": "Ley N.° 21.643", "tipo_numero": "Ley 21643",
     "articulo": "Artículo 1", "texto": "El acoso laboral es toda conducta que constituya agresión u hostigamiento "
                                         "reiterados, ejercida por el empleador o por uno o más trabajadores.",
     "vigente": True, "url_fuente": "https://www.bcn.cl/leychile/navegar?idNorma=1", "puntaje": 0.82},
    {"fragmento_id": "cdt_art2", "id_norma": "n2", "norma": "Código del Trabajo", "tipo_numero": "DFL 1",
     "articulo": "Artículo 2", "texto": "Las relaciones laborales deberán fundarse en un trato compatible con la "
                                         "dignidad de la persona.", "vigente": True,
     "url_fuente": "https://www.bcn.cl/leychile/navegar?idNorma=2", "puntaje": 0.7},
]


class Reloj:
    def __init__(self, t=1_700_000_000.0):
        self.t = t
        self.esperas = []

    def __call__(self):
        return self.t

    def avanzar(self, s):
        self.t += s

    async def dormir(self, s):
        self.esperas.append(s)
        self.t += s


def plazo_simulado(reloj: Reloj, registro: list):
    """Sustituye asyncio.wait_for: sin esperas reales. Si la llamada no termina enseguida, cuenta como silencio."""
    async def plazo(aw, segundos):
        registro.append(segundos)
        tarea = asyncio.ensure_future(aw)
        hechas, _ = await asyncio.wait({tarea}, timeout=0.02)
        if not hechas:
            tarea.cancel()
            reloj.avanzar(segundos)
            raise asyncio.TimeoutError()
        return tarea.result()
    return plazo


def json_ok(modelo_texto: dict) -> RespuestaLLM:
    return RespuestaLLM(json.dumps(modelo_texto), 100, 20)


def falla(codigo: int):
    def f(*a, **k):
        raise ErrorProveedor("gemini", codigo, reintentable=codigo >= 500 or codigo == 429)
    return f


async def _silencio(*a, **k):
    await asyncio.sleep(3600)


SILENCIO = _silencio


class FakeGemini:
    """`comportamientos`: {modelo: callable(args) -> RespuestaLLM | lanza | corutina}. Por defecto responde bien."""

    def __init__(self, comportamientos=None):
        self.comportamientos = comportamientos or {}
        self.llamadas = []  # (modelo, sistema, usuario, esquema)
        self.sano = {}

    def generacion(self, modelo=None):
        return [x for x in self.llamadas if "articulos" in ((x[3] or {}).get("properties") or {})
                and (modelo is None or x[0] == modelo)]

    async def generar(self, modelo, sistema, usuario, esquema=None, con_sistema=True, temperatura=0.2, degradar=False):
        self.llamadas.append((modelo, sistema, usuario, esquema))
        comp = self.comportamientos.get(modelo, self.responder)
        r = comp(modelo, sistema, usuario, esquema)
        if asyncio.iscoroutine(r):
            r = await r
        return r

    @staticmethod
    def responder(modelo, sistema, usuario, esquema):
        if "materia" in ((esquema or {}).get("properties") or {}):
            return json_ok({"materia": "acoso", "riesgo": "medio"})
        ids = re.findall(r'fragmento_id="([^"]+)"', usuario)
        por_id = {f["fragmento_id"]: f for f in FRAGMENTOS}
        arts = [{"fragmento_id": i, "explicacion": "Los hechos podrían relacionarse con esta norma.",
                 "cita": por_id[i]["texto"][:60], "confianza": 0.9 - 0.1 * n} for n, i in enumerate(ids[:2])]
        return json_ok({"articulos": arts})

    async def salud(self, modelo):
        return self.sano.get(modelo, True)


class FakeVoyage:
    def __init__(self, error=None):
        self.error, self.llamadas = error, []

    async def embed_consulta(self, texto):
        self.llamadas.append(texto)
        if self.error:
            raise self.error
        return [0.1] * 8, 12


class FakeQdrant:
    def __init__(self, error=None, fragmentos=None, version=7):
        self.error, self.llamadas = error, []
        self.fragmentos = FRAGMENTOS if fragmentos is None else fragmentos
        self.version = version

    async def buscar(self, coleccion, vector, k):
        self.llamadas.append((coleccion, list(vector), k))
        if self.error:
            raise self.error
        return [dict(f) for f in self.fragmentos[:k]]

    async def version_corpus(self, coleccion):
        if self.error:
            raise self.error
        return self.version


class FakeLocal:
    def __init__(self, error=None):
        self.error, self.llamadas = error, []

    async def buscar(self, texto, k):
        self.llamadas.append(texto)
        if self.error:
            raise self.error
        return {"fragmentos": [dict(f) for f in FRAGMENTOS[:k]], "modelo": "bge-m3-local",
                "coleccion": "normativa_local", "version_corpus": 5}


def caida(proveedor="voyage"):
    return ErrorProveedor(proveedor, 503, True)


class Entorno:
    pass


def armar(gemini=None, voyage=None, qdrant=None, local=None, config=None, clientes=None, almacen=None):
    reloj = Reloj()
    plazos = []
    e = Entorno()
    e.reloj, e.plazos = reloj, plazos
    e.gemini = gemini or FakeGemini()
    e.voyage, e.qdrant, e.local = voyage or FakeVoyage(), qdrant or FakeQdrant(), local or FakeLocal()
    sha = hashlib.sha256(SECRETO.encode()).hexdigest()
    e.config = config or Config(
        clientes=clientes or {"conector": {"secreto_sha256": sha, "cliente": "conector"}},
        jwt_secreto="x" * 40, umbral_similitud=0.3)
    e.almacen = almacen or AlmacenMemoria()
    prov = Proveedores(e.gemini, e.voyage, e.qdrant, e.local, dormir=reloj.dormir,
                       plazo_llamada=plazo_simulado(reloj, plazos))
    e.app = crear_app(e.config, e.almacen, prov, reloj)
    return e


def cliente_http(app):
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://nucleo")


async def obtener_token(c, client_id="conector", secreto=SECRETO):
    r = await c.post("/oauth/token", data={"grant_type": "client_credentials", "client_id": client_id,
                                           "client_secret": secreto})
    return r


async def cabeceras(c, client_id="conector", secreto=SECRETO):
    r = await obtener_token(c, client_id, secreto)
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def procesar_caso(e, texto="Un jefe presiona de forma reiterada a su equipo.", ref=None, cabs=None):
    """Envía un caso, espera la cadena y devuelve la sugerencia."""
    ref = ref or str(uuid.uuid4())
    async with cliente_http(e.app) as c:
        h = cabs or await cabeceras(c)
        r = await c.post("/v1/casos", json={"ref_opaca": ref, "id_empresa": "e1", "texto": texto}, headers=h)
        assert r.status_code == 202, r.text
        await e.app.state.esperar_tareas()
        g = await c.get(f"/v1/casos/{ref}/sugerencia", headers=h)
        return g.json(), ref
