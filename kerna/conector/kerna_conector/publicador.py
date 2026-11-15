"""Arma las notas `kerna_sugerencia` y `kerna_estado` que el conector publica en el caso."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from kerna_comun import notas


def ahora_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


_VEREDICTO = {"confirma": "mantiene", "condiciona": "condiciona", "veta": "veta"}


def _con_revisor(art: dict) -> dict:
    """Pasa los campos del revisor (solo códigos) a veredicto/causal/condiciones; sin dictamen no agrega nada."""
    art = dict(art)
    ver = _VEREDICTO.get(art.get("dictamen")) if art.get("revision_juridica", "revisado") == "revisado" else None
    if ver:
        art["veredicto"] = ver
        art["causal"] = art.get("causal_veto") if ver == "veta" else None
        art["condiciones"] = list(art.get("condiciones") or [])
    return art


def armar_sugerencia(resultado: dict, ahora: Optional[str] = None) -> notas.Sugerencia:
    """Nota a partir del objeto de resultado del núcleo, con sus campos tal cual."""
    datos = {k: resultado[k] for k in ("id_solicitud", "version_corpus", "estado", "motivo_revision", "modo",
                                       "recuperacion", "contingencia", "generado_en", "articulos")
             if k in resultado and resultado[k] is not None}
    if datos.get("articulos"):
        datos["articulos"] = [_con_revisor(a) for a in datos["articulos"]]
        datos["vetados"] = [a["id_articulo"] for a in datos["articulos"] if a.get("veredicto") == "veta"]
    datos.setdefault("generado_en", ahora or ahora_iso())
    if "contingencia" not in datos:
        datos["contingencia"] = datos.get("modo") != "oficial" or datos.get("recuperacion") == "local"
    return notas.Sugerencia.model_validate(datos)


def armar_estado(estado: str, id_seguimiento: Optional[str] = None, ahora: Optional[str] = None) -> notas.Estado:
    return notas.Estado(estado=estado, fecha=ahora or ahora_iso(), id_seguimiento=id_seguimiento or str(uuid.uuid4()))


def contenido(nota) -> str:
    return notas.escribir(nota)
