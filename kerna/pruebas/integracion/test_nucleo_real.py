"""Cadena completa del núcleo con servicios reales (Gemini, Voyage, Qdrant). Lee las variables de entorno:
GEMINI_API_KEY, VOYAGE_API_KEY, QDRANT_URL, QDRANT_API_KEY (y opcionales KERNA_COLECCION, KERNA_EMBEDDING)."""
import asyncio
import hashlib
import os
import uuid

import httpx
import pytest

from kerna_nucleo.api import crear_app
from kerna_nucleo.config import Config

pytestmark = [pytest.mark.integracion, pytest.mark.pr("PR-02")]

REQUERIDAS = ("GEMINI_API_KEY", "VOYAGE_API_KEY", "QDRANT_URL", "QDRANT_API_KEY")
TEXTO = ("Un supervisor ficticio del área de bodega ha hostigado de forma reiterada a una trabajadora durante meses, "
         "con gritos y amenazas de despido frente a sus compañeros, y ella teme represalias si denuncia.")


@pytest.mark.skipif(any(not os.environ.get(v) for v in REQUERIDAS), reason="faltan variables de servicios reales")
def test_cadena_completa_real():
    cfg = Config.desde_entorno()
    cfg.clientes = {"it": {"secreto_sha256": hashlib.sha256(b"it").hexdigest(), "cliente": "it"}}
    cfg.jwt_secreto = "i" * 40
    app = crear_app(cfg)

    async def f():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://n") as c:
            t = (await c.post("/oauth/token", data={"grant_type": "client_credentials", "client_id": "it",
                                                    "client_secret": "it"})).json()["access_token"]
            h = {"Authorization": f"Bearer {t}"}
            ref = str(uuid.uuid4())
            assert (await c.post("/v1/casos", json={"ref_opaca": ref, "id_empresa": "e", "texto": TEXTO}, headers=h)).status_code == 202
            await app.state.esperar_tareas()
            return (await c.get(f"/v1/casos/{ref}/sugerencia", headers=h)).json()
    g = asyncio.run(f())
    assert g["estado"] in ("completada", "revision_manual")
    if g["estado"] == "completada":
        assert g["articulos"] and all(a["enlace_fuente"] and a["cita"] for a in g["articulos"])
