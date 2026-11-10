"""Objetos que viajan como JSON en las notas internas del caso en Veridy (ver kerna/docs/contratos.md)."""
from __future__ import annotations

import json
from typing import Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, ValidationError

VERSION = 1

MotivoRevision = Literal["tiempo_agotado", "cadena_agotada", "validacion_fallida", "sin_normativa_aplicable"]
Modo = Literal["oficial", "respaldo", "local", "manual"]


class _Base(BaseModel):
    model_config = ConfigDict(extra="ignore")
    version: int = VERSION


class ArticuloSugerido(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id_sugerencia: str
    id_articulo: str
    norma: str
    articulo: str
    explicacion: str
    cita: str
    enlace_fuente: str
    confianza: float = Field(ge=0, le=1)


class Sugerencia(_Base):
    tipo: Literal["kerna_sugerencia"] = "kerna_sugerencia"
    id_solicitud: str
    version_corpus: int = 0
    estado: Literal["completada", "revision_manual"]
    motivo_revision: Optional[MotivoRevision] = None
    modo: Modo
    recuperacion: Literal["nube", "local"] = "nube"
    contingencia: bool = False
    generado_en: str
    articulos: list[ArticuloSugerido] = []


class Estado(_Base):
    tipo: Literal["kerna_estado"] = "kerna_estado"
    estado: Literal["en_proceso", "nucleo_no_disponible"]
    fecha: str
    id_seguimiento: str


class Feedback(_Base):
    tipo: Literal["kerna_feedback"] = "kerna_feedback"
    id_sugerencia: str
    valoracion: Literal["arriba", "abajo"]
    observacion: Optional[str] = Field(default=None, max_length=500)


class ArticuloAplicado(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id_articulo: str
    origen: Literal["sugerido", "agregado_por_auditor"]


class Clasificacion(_Base):
    tipo: Literal["kerna_clasificacion"] = "kerna_clasificacion"
    articulos: list[ArticuloAplicado] = []
    observacion: Optional[str] = Field(default=None, max_length=500)


Nota = Union[Sugerencia, Estado, Feedback, Clasificacion]
_TIPOS = {"kerna_sugerencia": Sugerencia, "kerna_estado": Estado,
          "kerna_feedback": Feedback, "kerna_clasificacion": Clasificacion}


def leer(contenido: str) -> Optional[Nota]:
    """Devuelve el objeto de Kerna que trae el contenido de una nota, o None si es una nota común."""
    try:
        datos = json.loads(contenido)
    except (TypeError, ValueError):
        return None
    if not isinstance(datos, dict):
        return None
    modelo = _TIPOS.get(datos.get("tipo"))
    if modelo is None:
        return None
    try:
        return modelo.model_validate(datos)
    except ValidationError:
        return None


def escribir(nota: Nota) -> str:
    """Texto JSON que se guarda como contenido de la nota interna."""
    return nota.model_dump_json()
