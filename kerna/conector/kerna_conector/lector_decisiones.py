"""Extrae del caso las decisiones del auditor (`kerna_feedback` y `kerna_clasificacion`) según las reglas del contrato."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from kerna_comun import notas
from kerna_comun.anonimizador import anonimizar

MAX_OBSERVACION = 500


@dataclass
class Decision:
    tipo: str            # "feedback" | "clasificacion"
    id_nota: str
    fecha: str
    nota: object         # notas.Feedback | notas.Clasificacion con la observación ya anonimizada


def _observacion(texto: Optional[str]) -> Optional[str]:
    if not texto:
        return None
    return anonimizar(texto).texto[:MAX_OBSERVACION]


def extraer(caso: dict, id_cuenta: str) -> list[Decision]:
    """Decisiones vigentes en orden de creación.

    Vale solo un comentario `internal` cuyo autor es un destinatario distinto de la cuenta de servicio (los del
    denunciante no traen `author_id`). Si hay varios `kerna_feedback` para un mismo `id_sugerencia`, o varias
    `kerna_clasificacion`, vale la última.
    """
    candidatas = []
    for pos, c in enumerate(caso.get("comments") or []):
        autor = c.get("author_id")
        if c.get("visibility") != "internal" or not autor or autor == id_cuenta:
            continue
        nota = notas.leer(c.get("content") or "")
        if isinstance(nota, (notas.Feedback, notas.Clasificacion)):
            candidatas.append((str(c.get("creation_date") or ""), pos, str(c.get("id")), nota))
    candidatas.sort(key=lambda t: (t[0], t[1]))

    vigentes: dict = {}
    for fecha, pos, id_nota, nota in candidatas:
        clave = ("feedback", nota.id_sugerencia) if isinstance(nota, notas.Feedback) else ("clasificacion",)
        vigentes[clave] = (fecha, pos, id_nota, nota)

    salida = []
    for fecha, pos, id_nota, nota in sorted(vigentes.values(), key=lambda t: (t[0], t[1])):
        limpia = nota.model_copy(update={"observacion": _observacion(nota.observacion)})
        salida.append(Decision("feedback" if isinstance(nota, notas.Feedback) else "clasificacion",
                               id_nota, fecha, limpia))
    return salida
