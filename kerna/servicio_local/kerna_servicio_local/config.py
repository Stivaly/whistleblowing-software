from __future__ import annotations

import os
from dataclasses import dataclass

TAREA = "Given a description of a workplace or corporate complaint, retrieve the relevant articles of Chilean legislation"
PREFIJO_CONSULTA = f"Instruct: {TAREA}\nQuery: "  # igual que evaluacion/job_embeddings/evaluar.py
PREFIJO_DOCUMENTO = ""
MODELO = "multilingual-e5-large-instruct"
ETIQUETA_MODELO = "intfloat/multilingual-e5-large-instruct"
DIMS = 1024
PUNTO_META_ID = "00000000-0000-0000-0000-000000000000"
MAX_TEXTOS = 64


@dataclass
class Config:
    token: str
    coleccion: str = "normativa_cl_local"
    qdrant_url: str = ""
    qdrant_api_key: str = ""
    blob_url: str = ""          # https://<cuenta>.blob.core.windows.net
    blob_contenedor: str = "indice-local"
    modelo: str = MODELO
    dims: int = DIMS

    @classmethod
    def desde_entorno(cls) -> "Config":
        e = os.environ
        return cls(token=e.get("KERNA_LOCAL_TOKEN", ""), coleccion=e.get("KERNA_LOCAL_COLECCION", "normativa_cl_local"),
                   qdrant_url=e.get("QDRANT_URL", ""), qdrant_api_key=e.get("QDRANT_API_KEY", ""),
                   blob_url=e.get("KERNA_BLOB_URL", ""), blob_contenedor=e.get("KERNA_BLOB_CONTENEDOR", "indice-local"))
