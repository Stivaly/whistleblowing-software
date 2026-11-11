"""Índice local en memoria: vectores + payload de los fragmentos + punto meta, con coseno por fuerza bruta."""
from __future__ import annotations

import io
import json
from dataclasses import dataclass, field

import httpx
import numpy as np

from .config import PUNTO_META_ID


@dataclass
class Indice:
    vectores: np.ndarray                      # (n, dims) float32, filas unitarias
    payloads: list[dict]
    meta: dict = field(default_factory=dict)
    origen: str = ""                          # "qdrant" | "blob"

    def __len__(self) -> int:
        return len(self.payloads)

    @property
    def version_corpus(self) -> int:
        return int(self.meta.get("version_corpus", 0) or 0)

    def buscar(self, consulta: list[float], k: int) -> list[dict]:
        """Top-k por coseno solo sobre vigentes. Cada resultado es el payload más `puntaje`."""
        if not len(self):
            return []
        q = np.asarray(consulta, dtype=np.float32)
        norma = float(np.linalg.norm(q))
        if norma == 0.0:
            return []
        puntajes = self.vectores @ (q / norma)
        vigentes = np.fromiter((p.get("vigente") is not False and p.get("tipo") != "meta" for p in self.payloads),
                               dtype=bool, count=len(self.payloads))
        puntajes = np.where(vigentes, puntajes, -np.inf)
        k = max(0, min(k, int(vigentes.sum())))
        if k == 0:
            return []
        orden = np.argsort(-puntajes)[:k]
        return [dict(self.payloads[i], puntaje=float(puntajes[i])) for i in orden]

    # ---- copia en blob (npz sin pickle)
    def a_bytes(self) -> bytes:
        buf = io.BytesIO()
        cuerpo = json.dumps({"payloads": self.payloads, "meta": self.meta}, ensure_ascii=False).encode()
        np.savez_compressed(buf, vectores=self.vectores, cuerpo=np.frombuffer(cuerpo, dtype=np.uint8))
        return buf.getvalue()

    @classmethod
    def desde_bytes(cls, datos: bytes, origen: str = "blob") -> "Indice":
        with np.load(io.BytesIO(datos), allow_pickle=False) as z:
            cuerpo = json.loads(bytes(z["cuerpo"]).decode())
            return cls(np.asarray(z["vectores"], dtype=np.float32), cuerpo["payloads"], cuerpo["meta"], origen)


def normalizar(vectores: list[list[float]]) -> np.ndarray:
    m = np.asarray(vectores, dtype=np.float32).reshape(len(vectores), -1)
    n = np.linalg.norm(m, axis=1, keepdims=True)
    return m / np.where(n == 0, 1, n)


def desde_qdrant(url: str, api_key: str, coleccion: str, http: httpx.Client | None = None) -> Indice:
    """Lee toda la colección (vectores + payload) con scroll. Lanza si Qdrant no responde o falta la colección."""
    if not url:
        raise RuntimeError("sin URL de Qdrant")
    cliente = http or httpx.Client(timeout=30.0)
    cabecera = {"api-key": api_key}
    vectores, payloads, meta, offset = [], [], {}, None
    while True:
        cuerpo = {"limit": 256, "with_payload": True, "with_vector": True}
        if offset is not None:
            cuerpo["offset"] = offset
        r = cliente.post(f"{url.rstrip('/')}/collections/{coleccion}/points/scroll", headers=cabecera, json=cuerpo)
        r.raise_for_status()
        res = r.json()["result"]
        for p in res["points"]:
            pl = p.get("payload") or {}
            if str(p.get("id")) == PUNTO_META_ID or pl.get("tipo") == "meta":
                meta = pl
            elif pl.get("fragmento_id") and p.get("vector"):
                vectores.append(p["vector"])
                payloads.append(pl)
        offset = res.get("next_page_offset")
        if offset is None:
            break
    if not payloads:
        raise RuntimeError("colección vacía")
    return Indice(normalizar(vectores), payloads, meta, "qdrant")


class AlmacenBlob:
    """Copia del índice en Azure Blob Storage con identidad administrada."""

    def __init__(self, cuenta_url: str, contenedor: str):
        self._url, self._contenedor = cuenta_url, contenedor
        self._servicio = None

    def _blob(self, nombre: str):
        if self._servicio is None:
            from azure.identity import DefaultAzureCredential
            from azure.storage.blob import BlobServiceClient
            self._servicio = BlobServiceClient(self._url, credential=DefaultAzureCredential())
        return self._servicio.get_blob_client(self._contenedor, nombre)

    def guardar(self, nombre: str, datos: bytes) -> None:
        self._blob(nombre).upload_blob(datos, overwrite=True)

    def leer(self, nombre: str) -> bytes | None:
        from azure.core.exceptions import ResourceNotFoundError
        try:
            return self._blob(nombre).download_blob().readall()
        except ResourceNotFoundError:
            return None
