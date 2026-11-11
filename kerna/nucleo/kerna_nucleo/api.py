"""API del núcleo (FastAPI). Todo es inyectable: configuración, almacén, proveedores y reloj."""
from __future__ import annotations

import asyncio
import time
import uuid
from typing import Literal, Optional

import httpx
from urllib.parse import parse_qs

from fastapi import Depends, FastAPI, Header, HTTPException, Request, Response
from pydantic import BaseModel, Field

from kerna_comun import anonimizador, telemetria

from . import VERSION
from .almacen import Almacen, crear_almacen
from .auth import DURACION_S, Autenticador
from .config import Config
from .enrutador import Enrutador, Nivel
from .orquestador import Orquestador, iso
from .proveedores import Proveedores
from .proveedores.gemini import ClienteGemini
from .proveedores.qdrant import ClienteQdrant
from .proveedores.servicio_local import ClienteLocal
from .proveedores.voyage import ClienteVoyage
from .retriever import Retriever


class CasoEntrada(BaseModel):
    ref_opaca: uuid.UUID
    id_empresa: str = Field(max_length=100)
    texto: str = Field(min_length=1, max_length=60000)


class FeedbackEntrada(BaseModel):
    id_nota: str = Field(min_length=1, max_length=100)
    id_sugerencia: str = Field(min_length=1, max_length=100)
    valoracion: Literal["arriba", "abajo"]
    observacion: Optional[str] = Field(default=None, max_length=500)


class ArticuloAplicadoEntrada(BaseModel):
    id_articulo: str = Field(min_length=1, max_length=200)
    origen: Literal["sugerido", "agregado_por_auditor"]


class ClasificacionEntrada(BaseModel):
    id_nota: str = Field(min_length=1, max_length=100)
    articulos: list[ArticuloAplicadoEntrada] = Field(default_factory=list, max_length=100)
    observacion: Optional[str] = Field(default=None, max_length=500)


def proveedores_reales(c: Config) -> Proveedores:
    return Proveedores(gemini=ClienteGemini(c.gemini_api_key),
                       voyage=ClienteVoyage(c.voyage_api_key, c.embedding, c.dims),
                       qdrant=ClienteQdrant(c.qdrant_url, c.qdrant_api_key),
                       local=ClienteLocal(c.local_url, c.local_token))


def resultado_derivado(sugeridos: set[str], aplicados: set[str]) -> str:
    if aplicados == sugeridos:
        return "aceptada"
    if sugeridos and not (aplicados & sugeridos):
        return "rechazada"
    return "corregida"


def crear_app(config: Config | None = None, almacen: Almacen | None = None, proveedores: Proveedores | None = None,
              reloj=None) -> FastAPI:
    config = config or Config.desde_entorno()
    reloj = reloj or time.time
    almacen = almacen or crear_almacen(config)
    proveedores = proveedores or proveedores_reales(config)
    auth = Autenticador(config.clientes, config.jwt_secreto, reloj)
    niveles = [Nivel.desde_dict(n) for n in config.cadena]
    enrutador = Enrutador(niveles, proveedores.gemini, reloj=reloj, dormir=proveedores.dormir,
                          plazo_llamada=proveedores.plazo_llamada, plazo_global=config.plazo_global_s,
                          corte=config.corte_llamada_s, esperas=config.esperas_s)
    retriever = Retriever(proveedores.voyage, proveedores.qdrant, proveedores.local, config.coleccion,
                          config.embedding, config.top_k, config.umbral_similitud)
    orquestador = Orquestador(config, almacen, enrutador, retriever, reloj)

    app = FastAPI(title="Kerna AI núcleo", version=VERSION)
    app.state.tareas = set()
    app.state.orquestador = orquestador
    app.state.enrutador = enrutador
    app.state.almacen = almacen

    async def esperar_tareas():
        while app.state.tareas:
            await asyncio.gather(*list(app.state.tareas), return_exceptions=True)

    app.state.esperar_tareas = esperar_tareas

    def cliente_actual(authorization: str | None = Header(default=None)) -> str:
        if authorization and authorization.lower().startswith("bearer "):
            cliente = auth.verificar(authorization[7:].strip())
            if cliente:
                return cliente
        raise HTTPException(401, "no autorizado", headers={"WWW-Authenticate": "Bearer"})

    @app.get("/salud")
    async def salud():
        return {"estado": "ok", "version": VERSION}

    @app.post("/oauth/token")
    async def token(peticion: Request):
        f = {k: v[0] for k, v in parse_qs((await peticion.body()).decode("utf-8", "replace")).items()}
        t = (auth.emitir(f.get("client_id", ""), f.get("client_secret", ""))
             if f.get("grant_type") == "client_credentials" else None)
        if not t:
            raise HTTPException(401, "credenciales inválidas", headers={"WWW-Authenticate": "Bearer"})
        return {"access_token": t, "token_type": "bearer", "expires_in": DURACION_S}

    @app.post("/v1/casos", status_code=202)
    async def crear_caso(caso: CasoEntrada, cliente: str = Depends(cliente_actual)):
        ref = str(caso.ref_opaca)
        ahora = reloj()
        nueva = {"id_solicitud": str(uuid.uuid4()), "cliente": cliente, "ref_opaca": ref,
                 "id_empresa": caso.id_empresa, "estado": "pendiente", "creada_en": ahora}
        sol, creada = await almacen.crear_solicitud(nueva)
        if creada:
            tarea = asyncio.create_task(orquestador.procesar(sol, caso.texto))
            app.state.tareas.add(tarea)
            tarea.add_done_callback(app.state.tareas.discard)
            telemetria.evento("solicitud_aceptada", id_solicitud=sol["id_solicitud"], ref_opaca=ref, cliente=cliente)
        return {"id_solicitud": sol["id_solicitud"], "estado": sol["estado"]}

    async def _solicitud(cliente: str, ref: uuid.UUID) -> dict:
        sol = await almacen.obtener_solicitud(cliente, str(ref))
        if sol is None:
            raise HTTPException(404, "solicitud no encontrada")
        return sol

    @app.get("/v1/casos/{ref_opaca}/sugerencia")
    async def sugerencia(ref_opaca: uuid.UUID, cliente: str = Depends(cliente_actual)):
        sol = await _solicitud(cliente, ref_opaca)
        if sol["estado"] == "pendiente" and reloj() - float(sol["creada_en"]) > config.plazo_global_s:
            ok = await almacen.actualizar_solicitud(cliente, str(ref_opaca), {
                "estado": "revision_manual", "motivo_revision": "tiempo_agotado", "modo": "manual",
                "recuperacion": "nube", "contingencia": True, "version_corpus": 0, "generado_en": iso(reloj())},
                solo_si_pendiente=True)
            sol = await _solicitud(cliente, ref_opaca)
            if ok:
                telemetria.evento("solicitud_terminada", id_solicitud=sol["id_solicitud"], cliente=cliente,
                                  estado="revision_manual", motivo="tiempo_agotado")
        out = {"id_solicitud": sol["id_solicitud"], "estado": sol["estado"]}
        if sol["estado"] != "pendiente":
            arts = await almacen.listar_articulos(sol["id_solicitud"]) if sol["estado"] == "completada" else []
            campos = ("id_sugerencia", "id_articulo", "norma", "articulo", "explicacion", "cita", "enlace_fuente", "confianza")
            arts = sorted(arts, key=lambda a: -float(a.get("confianza", 0)))
            out.update(motivo_revision=sol.get("motivo_revision"), modo=sol.get("modo", "manual"),
                       recuperacion=sol.get("recuperacion", "nube"), contingencia=bool(sol.get("contingencia")),
                       version_corpus=int(sol.get("version_corpus", 0)), generado_en=sol.get("generado_en"),
                       articulos=[{k: a.get(k) for k in campos} for a in arts])
        return out

    @app.post("/v1/casos/{ref_opaca}/feedback")
    async def feedback(ref_opaca: uuid.UUID, datos: FeedbackEntrada, respuesta: Response,
                       cliente: str = Depends(cliente_actual)):
        sol = await _solicitud(cliente, ref_opaca)
        arts = await almacen.listar_articulos(sol["id_solicitud"])
        if datos.id_sugerencia not in {a["id_sugerencia"] for a in arts}:
            raise HTTPException(404, "sugerencia no encontrada")
        obs = anonimizador.anonimizar(datos.observacion).texto if datos.observacion else None
        creada = await almacen.guardar_valoracion(sol["id_solicitud"], datos.id_nota, {
            "id_nota": datos.id_nota, "id_sugerencia": datos.id_sugerencia, "valoracion": datos.valoracion,
            "observacion": obs, "creada_en": reloj()})
        respuesta.status_code = 201 if creada else 200
        telemetria.evento("feedback", id_solicitud=sol["id_solicitud"], cliente=cliente, resultado=datos.valoracion)
        return {"id_nota": datos.id_nota}

    @app.post("/v1/casos/{ref_opaca}/clasificacion")
    async def clasificacion(ref_opaca: uuid.UUID, datos: ClasificacionEntrada, respuesta: Response,
                            cliente: str = Depends(cliente_actual)):
        sol = await _solicitud(cliente, ref_opaca)
        sugeridos = {a["id_articulo"] for a in await almacen.listar_articulos(sol["id_solicitud"])}
        aplicados = {a.id_articulo for a in datos.articulos}
        obs = anonimizador.anonimizar(datos.observacion).texto if datos.observacion else None
        reg, creada = await almacen.guardar_clasificacion(sol["id_solicitud"], datos.id_nota, {
            "id_nota": datos.id_nota, "articulos": [a.model_dump() for a in datos.articulos],
            "resultado": resultado_derivado(sugeridos, aplicados), "observacion": obs, "creada_en": reloj()})
        respuesta.status_code = 201 if creada else 200
        telemetria.evento("clasificacion_auditor", id_solicitud=sol["id_solicitud"], cliente=cliente,
                          resultado=reg["resultado"])
        return {"resultado": reg["resultado"]}

    return app
