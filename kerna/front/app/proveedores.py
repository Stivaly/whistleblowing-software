"""Disponibilidad de los proveedores de modelos SEGÚN SU PROPIA página de estado (no según nuestros errores).

Fuentes públicas, solo GET, sin enviar ningún dato nuestro:
- Azure OpenAI: feed RSS de Azure Status (incidentes activos). Se filtra por servicio (OpenAI / Foundry) y por la región
  de la cuenta (REGION_AZURE_OPENAI, por defecto "West US"); cuentan también los incidentes globales o sin región.
- Google Gemini: incidents.json de Google Cloud Status, producto «Vertex Gemini API» (Gemini en Agent Platform).
  El endpoint que usa Kerna es global, así que cuenta un incidente activo si es global o no indica región.
  La página de Gemini API / AI Studio no tiene endpoint legible por máquina.
- Voyage AI: Statuspage (voyageai-status.statuspage.io, /api/v2/summary.json), componente «API». Sin región.
Cada fuente se consulta con timeout corto y el resultado se guarda unos minutos. Si una fuente falla, ese proveedor
queda «sin información»; nunca se propaga el error.
"""
from __future__ import annotations

import json
import os
import re
import time
import urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from email.utils import parsedate_to_datetime
from html import unescape

TTL_S = 240
TIMEOUT_S = 4
REGION_AZURE_OPENAI = os.environ.get("REGION_AZURE_OPENAI", "West US")
URL_AZURE = "https://azure.status.microsoft/en-us/status/feed/"
URL_GOOGLE = "https://status.cloud.google.com/incidents.json"
URL_VOYAGE = "https://voyageai-status.statuspage.io/api/v2/summary.json"
PRODUCTO_GEMINI = "Z0FZJAMvEB4j3NbCJs6B"  # «Vertex Gemini API» en products.json

PROVEEDORES = [
    {"id": "azure", "nombre": "Azure OpenAI", "modelo": "gpt-5 nano y mini", "rol": "principal",
     "enlace": "https://azure.status.microsoft/en-us/status/",
     "si_cae": "Kerna responde con Gemini, un poco más lento."},
    {"id": "gemini", "nombre": "Google Gemini", "modelo": "Gemini Flash", "rol": "respaldo",
     "enlace": "https://status.cloud.google.com/",
     "si_cae": "Kerna sigue con Azure OpenAI; si los dos fallan, el caso pasa a revisión manual."},
    {"id": "voyage", "nombre": "Voyage AI", "modelo": "voyage-4-large", "rol": "búsqueda de leyes",
     "enlace": "https://voyageai-status.statuspage.io/",
     "si_cae": "Kerna busca las leyes con su servicio propio y los casos siguen saliendo."},
]
ESTADOS = ("operativo", "degradado", "caido", "sin_informacion")
GRAVEDAD = {"operativo": 0, "sin_informacion": 1, "degradado": 2, "caido": 3}
_cache: dict = {"t": 0.0, "datos": None}


def _get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "kerna-panel-estado/1.0", "Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=TIMEOUT_S) as r:  # noqa: S310 (URL fija, https)
        return r.read(2_000_000)


def _recorte(t: str, n: int = 160) -> str:
    t = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", unescape(t or ""))).strip()
    return t if len(t) <= n else t[: n - 1].rstrip() + "…"


def _res(estado: str, resumen: str = "", desde: str | None = None) -> dict:
    return {"estado": estado, "resumen": resumen, "desde": desde}


# ---------- Azure (RSS) ----------
_SERVICIO_AZURE = re.compile(r"openai|foundry|azure ai", re.I)
_CERRADO = re.compile(r"\b(resolved|mitigated|post incident|preliminary post)\b", re.I)
_CAIDO = re.compile(r"outage|unavailable|\bdown\b|fail(ed|ing|ures?)|cannot|unable", re.I)


def _region_cuenta(texto: str, region: str) -> bool:
    """True si el incidente menciona nuestra región, es global o no menciona ninguna región."""
    t = texto.lower()
    r = region.lower()
    if re.search(r"all regions|global|multiple regions|worldwide", t):
        return True
    if re.search(rf"{re.escape(r)}(?!\s*(?:[0-9]|central|east|west))", t):
        return True
    return not re.search(r"\b(west|east|north|south|central|uk|france|japan|korea|india|brazil|canada|australia|"
                         r"germany|sweden|norway|switzerland|uae|italy|poland|spain|mexico|chile)\b", t)


def interpretar_azure(xml_texto: str, region: str = REGION_AZURE_OPENAI) -> dict:
    raiz = ET.fromstring(xml_texto)
    if raiz.find("./channel") is None:
        raise ValueError("no es el feed de Azure Status")
    items = raiz.findall("./channel/item")
    peor = None
    for it in items:
        titulo = it.findtext("title") or ""
        cuerpo = _recorte(it.findtext("description") or "", 600)
        texto = f"{titulo} {cuerpo}"
        if not _SERVICIO_AZURE.search(texto) or _CERRADO.search(titulo) or not _region_cuenta(texto, region):
            continue
        est = "caido" if _CAIDO.search(texto) else "degradado"
        try:
            desde = parsedate_to_datetime(it.findtext("pubDate") or "").isoformat()
        except (TypeError, ValueError):
            desde = None
        cand = _res(est, _recorte(titulo), desde)
        if peor is None or GRAVEDAD[est] > GRAVEDAD[peor["estado"]]:
            peor = cand
    return peor or _res("operativo")


# ---------- Google (JSON de incidentes) ----------
def interpretar_google(json_texto: str) -> dict:
    peor = None
    for inc in json.loads(json_texto):
        if inc.get("end"):
            continue  # ya terminó
        if not any(p.get("id") == PRODUCTO_GEMINI for p in inc.get("affected_products", [])):
            continue
        locs = [str(x.get("id", "")).lower() for x in inc.get("currently_affected_locations", [])]
        if locs and "global" not in locs:
            continue  # solo otras regiones: no afecta al endpoint global que usa Kerna
        impacto = inc.get("status_impact")
        est = "caido" if impacto == "SERVICE_OUTAGE" else "degradado"
        cand = _res(est, _recorte(inc.get("external_desc", "")), inc.get("begin"))
        if peor is None or GRAVEDAD[est] > GRAVEDAD[peor["estado"]]:
            peor = cand
    return peor or _res("operativo")


# ---------- Voyage (Statuspage) ----------
def interpretar_voyage(json_texto: str) -> dict:
    d = json.loads(json_texto)
    comp = next((c for c in d.get("components", []) if c.get("name") == "API"), None)
    if comp is None:
        return _res("sin_informacion", "La página de estado no informa el componente API.")
    est = {"operational": "operativo", "degraded_performance": "degradado", "partial_outage": "degradado",
           "major_outage": "caido"}.get(comp.get("status"), "sin_informacion")
    inc = next((i for i in d.get("incidents", []) if any(c.get("id") == comp.get("id") for c in i.get("components", []))), None)
    if inc and est == "operativo":
        est = "caido" if inc.get("impact") == "critical" else "degradado"
    if inc and est != "operativo":
        return _res(est, _recorte(inc.get("name", "")), inc.get("started_at") or inc.get("created_at"))
    return _res(est, "" if est == "operativo" else "La página de estado marca la API con problemas.",
                comp.get("updated_at") if est != "operativo" else None)


FUENTES = {"azure": (URL_AZURE, interpretar_azure), "gemini": (URL_GOOGLE, interpretar_google),
           "voyage": (URL_VOYAGE, interpretar_voyage)}


def _uno(pid: str, get) -> dict:
    url, interpretar = FUENTES[pid]
    try:
        return interpretar(get(url).decode("utf-8", "replace"))
    except Exception:  # fuente caída, lenta o con formato inesperado: sin información, nunca error
        return _res("sin_informacion", "No se pudo consultar la página de estado del proveedor.")


def _mensaje(p: dict, r: dict) -> str:
    if r["estado"] == "operativo":
        return "El proveedor informa que funciona con normalidad."
    if r["estado"] == "sin_informacion":
        return r["resumen"] or "No hay información de estado disponible para este proveedor."
    verbo = "no está disponible" if r["estado"] == "caido" else "tiene problemas"
    desde = f" Desde {r['desde'][:16].replace('T', ' ')} UTC." if r["desde"] else ""
    return f"{p['nombre']} {verbo}: {r['resumen']}{desde} {p['si_cae']}"


def estado_proveedores(get=None) -> dict:
    """{"proveedores": [...], "general": {...}, "consultado": epoch}. `get(url)->bytes` se inyecta en las pruebas."""
    real = get is None
    if real and _cache["datos"] and time.time() - _cache["t"] < TTL_S:
        return _cache["datos"]
    obtener = get or _get
    try:
        with ThreadPoolExecutor(max_workers=len(PROVEEDORES)) as ex:
            res = list(ex.map(lambda p: _uno(p["id"], obtener), PROVEEDORES))
    except Exception:
        res = [_res("sin_informacion", "No se pudo consultar.")] * len(PROVEEDORES)
    lista = [{**p, **r, "mensaje": _mensaje(p, r)} for p, r in zip(PROVEEDORES, res)]
    principal = lista[0]
    if principal["estado"] == "caido":
        general = {"estado": "caido", "texto": "El proveedor principal está caído.",
                   "detalle": f"Azure OpenAI no está disponible; Kerna responde con Gemini."}
    elif any(x["estado"] in ("caido", "degradado") for x in lista):
        general = {"estado": "degradado", "texto": "Algún proveedor tiene problemas.",
                   "detalle": "Kerna sigue funcionando con los demás."}
    else:
        general = {"estado": "operativo", "texto": "Los proveedores funcionan con normalidad.", "detalle": ""}
    out = {"proveedores": lista, "general": general, "consultado": int(time.time())}
    if real:
        _cache.update(t=time.time(), datos=out)
    return out
