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
import json
from pathlib import Path

from . import consultas
from .formato import fecha_hora

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



def _motivos_conector(crudo, total: int) -> list:
    """Desglose por motivo de la fila `conector` (JSON `pendientes_por_motivo`). [] si falta, es inválido o no suma el total."""
    try:
        d = json.loads(crudo) if isinstance(crudo, str) else dict(crudo or {})
        cuenta = {str(k): int(v) for k, v in d.items() if int(v) > 0}
    except (ValueError, TypeError, AttributeError):
        return []
    if not cuenta or sum(cuenta.values()) != total:
        return []
    out = []
    for k, n in sorted(cuenta.items(), key=lambda kv: -kv[1]):
        texto, auto = ("Con error al procesar", True) if k == "error" else MOTIVOS.get(k, ("Otro motivo", False))
        out.append({"motivo": k, "texto": texto, "casos": n, "se_reintenta": auto})
    return out


def con_estado_real(r: dict | None, c: dict | None, ahora=None) -> dict | None:
    """Lo pendiente HOY: siempre el último estado real conocido de la fila `conector` (casos de Veridy ya reconciliados), con su hora;
    nunca la estimación de la telemetría, que cuenta casos ya resueltos. Solo si el conector jamás escribió su fila queda la telemetría. `fuente` = conector | telemetria.
    El conector no informa el motivo de cada caso en espera: con `pendientes_por_motivo` el desglose es por motivo; sin él, por situación (revisión manual, error). Siempre suma el total."""
    act = _fecha((c or {}).get("actualizado_en"))
    if not (c and act):
        if r is None:
            return None
        return {**r, "fuente": "telemetria", "conector_visto": (c or {}).get("actualizado_en")}
    man, err = _num(c.get("en_revision_manual")), _num(c.get("error"))
    motivos = _motivos_conector(c.get("pendientes_por_motivo"), man + err) or [
        {"motivo": k, "texto": t, "casos": n, "se_reintenta": True} for k, t, n in (("revision_manual", "En revisión manual", man), ("error", "Con error al procesar", err)) if n]
    casos, hecho = _num(c.get("casos")), _num(c.get("completado"))
    return {"total": man + err, "reintentables": man + err, "motivos": motivos, "proximo_auto": None, "ultimo_reintento": (r or {}).get("ultimo_reintento"),
            "fuente": "conector", "actualizado_en": c.get("actualizado_en"), "casos": casos, "con_sugerencia": max(0, hecho - man), "manual": man,
            "manual_motivos": [(m["texto"], m["casos"]) for m in motivos if m["motivo"] != "error"], "sin_sugerencia": max(0, casos - max(0, hecho - man)), "en_proceso": _num(c.get("nuevo")) + _num(c.get("pendiente"))}


def ayuda_pendientes(r: dict, dias: int = 7, ahora=None) -> str:
    """Texto del «?» del bloque (una línea): estado del conector y su hora."""
    if r.get("fuente") == "conector":
        return f"Último estado del conector: {fecha_hora(r.get('actualizado_en'))}."
    return "Aún sin estado del conector."


CAMPOS = ("estado", "solicitado_en", "atendido_en", "reintentados", "origen", "inicio", "fin", "total", "enviados", "resueltos", "con_sugerencia",
          "sin_sugerencia", "en_vuelo", "eta_s", "actualizado_en", "incompleto")


def _limpio(e) -> dict:
    return {k: e.get(k) for k in CAMPOS if e.get(k) is not None}


def estado_solicitud(tabla=None) -> dict:
    """Fila `solicitud` (contrato del conector): estado ninguna|solicitado|en_curso|atendido y, con corrida, sus conteos y fechas."""
    from azure.core.exceptions import ResourceNotFoundError
    t = tabla or _tabla()
    try:
        e = t.get_entity(PK, RK)
    except ResourceNotFoundError:
        return {"estado": "ninguna"}
    return {"estado": "ninguna", **_limpio(e)}


def estado_conector(tabla=None) -> dict | None:
    """Fila `conector`: estado en vivo (segundos de latencia, sin Log Analytics). None si el conector aún no la escribe."""
    from azure.core.exceptions import ResourceNotFoundError
    t = tabla or _tabla()
    try:
        e = t.get_entity(PK, "conector")
    except ResourceNotFoundError:
        return None
    return {k: v for k, v in e.items() if k not in ("PartitionKey", "RowKey", "Timestamp") and v is not None}


def _fecha(iso):
    try:
        return datetime.fromisoformat(str(iso).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None


def hace(iso, ahora) -> str:
    d = _fecha(iso)
    if not d:
        return ""
    s = max(0, int((ahora - d).total_seconds()))
    return "ahora mismo" if s < 20 else f"hace {s} s" if s < 90 else f"hace {s // 60} min" if s < 5400 else f"hace {round(s / 3600)} h" if s < 172800 else f"hace {s // 86400} días"


def _num(x, defecto=0):
    try:
        return int(float(x))
    except (TypeError, ValueError):
        return defecto


def vista_boton(s: dict | None, ahora=None) -> dict:
    """Qué muestra el botón de reintento. El botón nunca desaparece:
    modo `normal` (se puede pulsar; con `resultado` si el último pedido terminó) o `curso` (deshabilitado, con progreso y ayuda)."""
    from . import formato
    ahora = ahora or datetime.now(timezone.utc)
    s = s or {}
    est = s.get("estado")
    if est in ("solicitado", "en_curso"):
        curso = est == "en_curso"
        total, listos = _num(s.get("total")), _num(s.get("resueltos"))
        avance = _fecha(s.get("actualizado_en"))
        quieto = bool(avance and (ahora - avance).total_seconds() > 300)
        if curso:
            partes = [f"En curso desde {formato.fecha_hora(s.get('inicio') or s.get('solicitado_en'))}"]
            eta = _num(s.get("eta_s"), -1)
            partes.append("aún sin estimación de término" if eta < 0 else "termina en menos de 1 min" if eta < 60 else f"faltan unos {round(eta / 60)} min")
            if total:
                partes.append(f"{listos} de {total} listos")
        else:
            partes = [f"Pedido {hace(s.get('solicitado_en'), ahora) or 'recién'}", "esperando que el conector lo tome", "si Veridy está apagado, se atiende al encenderlo"]
        if quieto:
            partes.append(f"sin avance {hace(s.get('actualizado_en'), ahora)}: el conector puede estar detenido")
        return {"modo": "curso", "texto": "Reintentando… espera", "sub": f"{listos} de {total}" if curso and total else "", "ayuda": ". ".join(x[:1].upper() + x[1:] for x in partes) + ".",
                "avance": round(100 * listos / total) if curso and total else None, "detenido": quieto}
    vm = {"modo": "normal", "texto": "Reintentar ahora", "sub": "", "ayuda": "", "avance": None, "detenido": False}
    if est == "atendido" and s.get("reintentados") is not None:
        n, cs = _num(s.get("reintentados")), s.get("con_sugerencia")
        r = f"{n} reintentados" + (f" · {_num(cs)} con sugerencia" if cs is not None else "")
        vm["resultado"] = r + (" · se cerró por tiempo, quedó incompleto" if str(s.get("incompleto")).lower() == "true" else "")
        vm["resultado_en"] = formato.fecha_hora(s.get("fin") or s.get("atendido_en"))
    return vm


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
