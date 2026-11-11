"""Del JSON de un caso de Veridy (`GET /api/recipient/rtips/<id>`) arma solo el relato y ubica las notas propias.

Campos que usa: `questionnaires[].steps[].children[]` (esquema, con `id`, `type`, `label`, `template_id`, `options`,
`children`), `questionnaires[].answers` (id de pregunta -> lista de respuestas), `comments[]` y `creation_date`.
Todo lo demás (identidad del denunciante en `data`, archivos `wbfiles`/`rfiles`, `receivers`, `label`, `score`,
metadatos) se descarta.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterator, Optional

from kerna_comun import notas

PLANTILLA_IDENTIDAD = "whistleblower_identity"
TIPOS_TEXTO = {"inputbox", "textarea", "date", "daterange"}
TIPOS_OPCION_UNICA = {"selectbox", "multichoice"}
# El resto (fileupload, voice, tos, recipient_selection, ...) no aporta texto al relato.


def _etiqueta(campo: dict) -> str:
    return str(campo.get("label") or "").strip()


def _opciones(campo: dict) -> dict:
    return {o.get("id"): str(o.get("label") or "").strip() for o in campo.get("options") or []}


def _valores_de(campo: dict, entrada: dict) -> list[str]:
    tipo = campo.get("type")
    if tipo in TIPOS_TEXTO:
        v = entrada.get("value")
        return [str(v).strip()] if v not in (None, "") and str(v).strip() else []
    if tipo in TIPOS_OPCION_UNICA:
        etq = _opciones(campo).get(entrada.get("value"))
        return [etq] if etq else []
    if tipo == "checkbox":
        return [etq for oid, etq in _opciones(campo).items() if entrada.get(oid) is True and etq]
    return []


def _lineas(campos: list, respuestas: dict, nivel: int = 0) -> Iterator[str]:
    sangria = "  " * nivel
    for campo in campos:
        if campo.get("template_id") == PLANTILLA_IDENTIDAD or campo.get("id") == PLANTILLA_IDENTIDAD:
            continue  # identidad del denunciante: se descarta completa
        tipo = campo.get("type")
        entradas = respuestas.get(campo.get("id")) or []
        if not isinstance(entradas, list):
            continue
        etiqueta = _etiqueta(campo)
        if tipo == "fieldgroup":
            for entrada in entradas:
                hijas = list(_lineas(campo.get("children") or [], entrada if isinstance(entrada, dict) else {},
                                     nivel + 1))
                if hijas:
                    if etiqueta:
                        yield "%s%s" % (sangria, etiqueta)
                    yield from hijas
            continue
        for entrada in entradas:
            if not isinstance(entrada, dict):
                continue
            valores = _valores_de(campo, entrada)
            if valores:
                yield "%s%s: %s" % (sangria, etiqueta, "; ".join(valores)) if etiqueta else sangria + "; ".join(valores)


def extraer_relato(caso: dict) -> str:
    """Respuestas de texto del cuestionario, en orden, con la etiqueta de cada pregunta."""
    partes: list[str] = []
    for cuestionario in caso.get("questionnaires") or []:
        respuestas = cuestionario.get("answers")
        if not isinstance(respuestas, dict):
            continue  # cifrado sin descifrar o ausente
        for paso in cuestionario.get("steps") or []:
            partes.extend(_lineas(paso.get("children") or [], respuestas))
    return "\n".join(partes)


def fecha_creacion(caso: dict) -> str:
    return str(caso.get("creation_date") or "")


@dataclass
class NotaPropia:
    id_nota: str
    nota: Any
    fecha: str


def notas_de_cuenta(caso: dict, id_cuenta: str, tipo: Optional[str] = None) -> list[NotaPropia]:
    """Notas de Kerna (`kerna_sugerencia`/`kerna_estado`) escritas por la cuenta de servicio en el caso."""
    salida = []
    for c in caso.get("comments") or []:
        if c.get("author_id") != id_cuenta or c.get("visibility") != "internal":
            continue
        nota = notas.leer(c.get("content") or "")
        if nota is None or nota.tipo not in ("kerna_sugerencia", "kerna_estado"):
            continue
        if tipo and nota.tipo != tipo:
            continue
        salida.append(NotaPropia(str(c.get("id")), nota, str(c.get("creation_date") or "")))
    return salida
