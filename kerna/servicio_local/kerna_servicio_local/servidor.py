"""API del servicio local: POST /embed, POST /buscar, GET /salud (+ POST /recargar). Todas salvo /salud exigen
`X-Token-Interno`, comparado en tiempo constante."""
from __future__ import annotations

import asyncio
import hmac
import logging
import os
import threading
from contextlib import asynccontextmanager
from typing import Callable, Literal

import uvicorn
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from kerna_comun import telemetria

from .config import MAX_TEXTOS, Config
from .indice import AlmacenBlob, Indice, desde_qdrant

_log = logging.getLogger("kerna.servicio_local")


class PeticionEmbed(BaseModel):
    textos: list[str] = Field(max_length=MAX_TEXTOS)
    tipo: Literal["document", "query"] = "document"


class PeticionBuscar(BaseModel):
    texto: str
    k: int = Field(default=8, ge=1, le=50)


class Estado:
    def __init__(self):
        self.indice: Indice | None = None
        self.embedder_listo = False
        self.error = ""


def cargar_indice(config: Config, qdrant: Callable | None, almacen) -> Indice | None:
    """Qdrant si responde (y deja copia en el blob); si no, la copia del blob; si no hay ninguna, None."""
    nombre = f"{config.coleccion}.npz"
    try:
        indice = (qdrant or (lambda: desde_qdrant(config.qdrant_url, config.qdrant_api_key, config.coleccion)))()
    except Exception as e:
        telemetria.evento("indice_local_qdrant_fallo", codigo=type(e).__name__)
        indice = None
    if indice is not None:
        if almacen is not None:
            try:
                almacen.guardar(nombre, indice.a_bytes())
            except Exception as e:
                telemetria.evento("indice_local_blob_fallo", codigo=type(e).__name__)
        return indice
    if almacen is not None:
        try:
            datos = almacen.leer(nombre)
            if datos:
                return Indice.desde_bytes(datos, "blob")
        except Exception as e:
            telemetria.evento("indice_local_blob_fallo", codigo=type(e).__name__)
    return None


def crear_app(config: Config, embedder, qdrant: Callable | None = None, almacen=None,
              en_segundo_plano: bool = True) -> FastAPI:
    """`embedder`: objeto con `embed(textos, tipo)` y, opcional, `cargar()`. `qdrant`: función sin argumentos que
    devuelve un Indice (para pruebas). `almacen`: objeto con guardar/leer (blob)."""
    estado = Estado()
    cerrojo = threading.Lock()  # el modelo atiende una vectorización a la vez

    def arrancar():
        try:
            with telemetria.etapa("indice_local_carga") as a:
                estado.indice = cargar_indice(config, qdrant, almacen)
                a["coleccion"] = config.coleccion
                a["fragmentos"] = len(estado.indice) if estado.indice else 0
            if hasattr(embedder, "cargar"):
                with telemetria.etapa("modelo_local_carga", modelo=config.modelo):
                    embedder.cargar()
            estado.embedder_listo = True
        except Exception as e:  # el modelo no cargó: /salud sigue en 503 y el contenedor se reinicia
            estado.error = type(e).__name__
            _log.exception("falló el arranque")

    @asynccontextmanager
    async def vida(app):
        if en_segundo_plano:
            threading.Thread(target=arrancar, daemon=True).start()
        else:
            arrancar()
        yield

    app = FastAPI(title="Servicio local de Kerna AI", lifespan=vida)

    def autenticar(x_token_interno: str = Header(default="")):
        esperado = config.token.encode()
        if not esperado or not hmac.compare_digest(x_token_interno.encode(), esperado):
            raise HTTPException(401, "token inválido")

    def vectorizar(textos: list[str], tipo: str) -> list[list[float]]:
        with cerrojo:
            return embedder.embed(textos, tipo)

    @app.get("/salud")
    async def salud():
        ind = estado.indice
        cuerpo = {"estado": "ok" if estado.embedder_listo else "cargando", "modelo": config.modelo,
                  "coleccion": config.coleccion, "fragmentos": len(ind) if ind else 0,
                  "version_corpus": ind.version_corpus if ind else 0, "origen_indice": ind.origen if ind else ""}
        return JSONResponse(cuerpo, status_code=200 if estado.embedder_listo else 503)

    @app.post("/embed", dependencies=[Depends(autenticar)])
    async def embed(p: PeticionEmbed):
        if not estado.embedder_listo:
            raise HTTPException(503, "modelo cargando")
        with telemetria.etapa("embed_local", modelo=config.modelo, tipo=p.tipo) as a:
            vs = await asyncio.to_thread(vectorizar, p.textos, p.tipo) if p.textos else []
            a["fragmentos"] = len(p.textos)
        return {"vectores": vs, "modelo": config.modelo}

    @app.post("/buscar", dependencies=[Depends(autenticar)])
    async def buscar(p: PeticionBuscar):
        if not estado.embedder_listo:
            raise HTTPException(503, "modelo cargando")
        ind = estado.indice
        if ind is None:
            raise HTTPException(503, "sin índice local")
        with telemetria.etapa("buscar_local", modelo=config.modelo, coleccion=config.coleccion) as a:
            vector = (await asyncio.to_thread(vectorizar, [p.texto], "query"))[0]
            frags = ind.buscar(vector, p.k)
            a["fragmentos"] = len(frags)
        return {"fragmentos": frags, "modelo": config.modelo, "coleccion": config.coleccion,
                "version_corpus": ind.version_corpus}

    @app.post("/recargar", dependencies=[Depends(autenticar)])
    async def recargar():
        """Vuelve a leer la colección (después de sincronizarla) y actualiza la copia en el blob."""
        nuevo = await asyncio.to_thread(cargar_indice, config, qdrant, almacen)
        if nuevo is None:
            raise HTTPException(503, "sin índice local")
        estado.indice = nuevo
        return {"fragmentos": len(nuevo), "version_corpus": nuevo.version_corpus, "origen_indice": nuevo.origen}

    return app


def main() -> None:
    telemetria.configurar("kerna-servicio-local")
    config = Config.desde_entorno()
    from .embedder import EmbedderE5
    almacen = AlmacenBlob(config.blob_url, config.blob_contenedor) if config.blob_url else None
    app = crear_app(config, EmbedderE5(), almacen=almacen)
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "8080")), log_level="info")


if __name__ == "__main__":
    main()
