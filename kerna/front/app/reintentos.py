"""Casos pendientes de reintento y disparo manual desde el panel.

Qué se muestra sale de la telemetría (Log Analytics): solo conteos por motivo y fechas, nunca textos ni identificadores.
El disparo manual escribe UNA fila en la tabla `reintentosmanuales` (PartitionKey "kerna", RowKey "solicitud"):
  estado "solicitado" -> el conector la lee al comienzo de su pasada, reintenta sin esperar las 24 h y la marca "atendido"
  (con cuántos casos reintentó). Mientras la fila diga "solicitado" otra pulsación no hace nada (un doble clic no dispara
  dos veces); crear/reemplazar la fila usa la condición de versión (ETag) de la tabla, así que es atómico.
El conector reintenta solo los casos que ya reintentaría solo (fallo de modelos); el texto de las denuncias sigue
viajando únicamente de Veridy al núcleo, como siempre, y nada de eso pasa por el front.
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

from . import consultas

TABLA = "reintentosmanuales"
PK, RK = "kerna", "solicitud"
HORAS_AUTO = float(os.environ.get("KERNA_REINTENTO_HORAS", "24"))
MOTIVOS = {  # motivo técnico -> (texto simple, ¿se reintenta solo?)
    "cadena_agotada": ("Los modelos de IA no estaban disponibles", True),
    "tiempo_agotado": ("El análisis tardó más de lo permitido", True),
    "validacion_fallida": ("La sugerencia no pasó la revisión de calidad", False),
    "sin_normativa_aplicable": ("No se encontró una norma que aplique", False),
    "sin_motivo": ("Sin motivo registrado", False),
}


def _tabla():
    from azure.data.tables import TableClient
    from azure.identity import DefaultAzureCredential
    url = os.environ.get("REINTENTOS_TABLA_URL") or os.environ["NEGOCIO_TABLA_URL"]
    return TableClient(endpoint=url, table_name=TABLA, credential=DefaultAzureCredential())


def _kql(nombre: str) -> str:
    """La consulta empaquetada con la app (kql/) o, en desarrollo y pruebas, la del repositorio."""
    for base in (consultas.DIR_KQL, Path(__file__).resolve().parents[2] / "docs" / "observabilidad" / "consultas"):
        if (base / nombre).exists():
            return (base / nombre).read_text(encoding="utf-8")
    raise FileNotFoundError(nombre)


def resumen(dias: int = 7, ejecutar=None, ahora=None) -> dict:
    """{"total", "reintentables", "motivos": [{"motivo","texto","casos","se_reintenta"}], "proximo_auto", "ultimo_reintento"}."""
    ejecutar = ejecutar or consultas.filas
    ahora = ahora or datetime.now(timezone.utc)
    mot = ejecutar(_kql("front_pendientes_motivos.kql"), dias)
    res = ejecutar(_kql("front_reintentos_resumen.kql"), dias)
    motivos = []
    for f in mot:
        m = str(f["motivo"])
        texto, auto = MOTIVOS.get(m, ("Otro motivo", False))
        motivos.append({"motivo": m, "texto": texto, "casos": int(f["casos"]), "se_reintenta": auto})
    por = {str(f["evento"]): f for f in res}
    resueltos = int(por.get("conector_reproceso", {}).get("eventos", 0))
    reint = sum(x["casos"] for x in motivos if x["se_reintenta"])
    pendientes = max(0, reint - resueltos)  # aproximación: los reprocesados con éxito ya no esperan
    ultimo = por.get("conector_reintento", {}).get("ultimo")
    proximo = None
    if pendientes and ultimo:
        u = datetime.fromisoformat(str(ultimo).replace("Z", "+00:00"))
        proximo = max(u + timedelta(hours=HORAS_AUTO), ahora).isoformat()
    return {"total": sum(x["casos"] for x in motivos), "reintentables": pendientes, "motivos": motivos,
            "proximo_auto": proximo, "ultimo_reintento": str(ultimo) if ultimo else None}


def estado_solicitud(tabla=None) -> dict:
    """{"estado": "ninguna"|"solicitado"|"atendido", "solicitado_en", "atendido_en", "reintentados"}."""
    from azure.core.exceptions import ResourceNotFoundError
    t = tabla or _tabla()
    try:
        e = t.get_entity(PK, RK)
    except ResourceNotFoundError:
        return {"estado": "ninguna"}
    return {"estado": e.get("estado", "ninguna"), "solicitado_en": e.get("solicitado_en"),
            "atendido_en": e.get("atendido_en"), "reintentados": e.get("reintentados")}


def solicitar(tabla=None, ahora=None) -> str:
    """Pide el reintento. Devuelve "solicitado" (se registró) o "ya_solicitado" (había una sin atender)."""
    from azure.core import MatchConditions
    from azure.core.exceptions import ResourceExistsError, ResourceModifiedError, ResourceNotFoundError
    t = tabla or _tabla()
    marca = (ahora or datetime.now(timezone.utc)).strftime("%Y-%m-%dT%H:%M:%SZ")
    nueva = {"PartitionKey": PK, "RowKey": RK, "estado": "solicitado", "solicitado_en": marca}
    try:
        actual = t.get_entity(PK, RK)
    except ResourceNotFoundError:
        try:
            t.create_entity(nueva)
            return "solicitado"
        except ResourceExistsError:
            return "ya_solicitado"
    if actual.get("estado") == "solicitado":
        return "ya_solicitado"
    try:
        t.update_entity(nueva, mode="replace", etag=actual.metadata["etag"], match_condition=MatchConditions.IfNotModified)
    except (ResourceModifiedError, ResourceExistsError):
        return "ya_solicitado"
    return "solicitado"
