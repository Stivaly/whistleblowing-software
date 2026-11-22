"""Tokens de IA realmente gastados en un período, para el costo del panel y del informe.

- Azure OpenAI: métricas de la cuenta (ProcessedPromptTokens y GeneratedTokens por despliegue). Cuentan todas las llamadas:
  denuncias reales, pruebas, mediciones y la demo. Se leen con la API REST de Azure Monitor y la identidad administrada
  del front (rol Monitoring Reader sobre la cuenta; el recurso llega en OPENAI_RECURSO_ID).
- Modelos fuera de Azure (Gemini de respaldo): tokens que el núcleo registra en Log Analytics (solo producción).
- Embeddings: no se incluyen; no tienen tarifa equivalente en Anthropic.

Devuelve filas con el mismo formato que la consulta front_tokens_por_modelo (modelo, tokens_entrada_total, tokens_salida_total).
El costo por denuncia sale aparte, de front_tokens_por_denuncia (toda la cadena de cada denuncia real).
"""
from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

API = "https://management.azure.com"
METRICAS = ("ProcessedPromptTokens", "GeneratedTokens")


def _token() -> str:
    from azure.identity import DefaultAzureCredential
    return DefaultAzureCredential().get_token(API + "/.default").token


def tokens_azure(inicio: datetime, fin: datetime) -> dict[str, list[float]] | None:
    """{despliegue: [tokens de entrada, tokens de salida]} de Azure OpenAI entre inicio y fin; None si no se pudo leer."""
    recurso = os.environ.get("OPENAI_RECURSO_ID", "")
    if not recurso:
        return None
    q = urllib.parse.urlencode({
        "api-version": "2023-10-01", "metricnames": ",".join(METRICAS), "aggregation": "Total", "interval": "P1D",
        "timespan": f"{inicio.astimezone(timezone.utc):%Y-%m-%dT%H:%M:%SZ}/{fin.astimezone(timezone.utc):%Y-%m-%dT%H:%M:%SZ}",
        "$filter": "ModelDeploymentName eq '*'"})
    pet = urllib.request.Request(f"{API}{recurso}/providers/microsoft.insights/metrics?{q}", headers={"Authorization": "Bearer " + _token()})
    try:
        with urllib.request.urlopen(pet, timeout=20) as r:
            datos = json.load(r)
    except Exception:
        return None
    out: dict[str, list[float]] = {}
    for m in datos.get("value", []):
        i = METRICAS.index(m["name"]["value"])
        for ts in m.get("timeseries", []):
            dep = next((x["value"] for x in ts.get("metadatavalues", []) if x.get("name", {}).get("value", "").lower() == "modeldeploymentname"), "")
            if not dep or "embedding" in dep.lower():
                continue
            out.setdefault(dep, [0.0, 0.0])[i] += sum(p.get("total") or 0 for p in ts.get("data", []))
    return out


def filas_totales(etapas: list[dict], inicio: datetime, fin: datetime) -> tuple[list[dict], bool]:
    """(filas de todo lo gastado, True si incluye las métricas de Azure). `etapas` son las filas de front_tokens_por_modelo
    (tokens por modelo de las etapas que lo registran): de ahí salen solo los modelos fuera de Azure (Gemini), porque lo
    que corrió en Azure ya está completo en las métricas. Sin métricas, se devuelven las etapas tal cual."""
    azure = tokens_azure(inicio, fin)
    if azure is None:
        return etapas, False
    filas = [{"modelo": dep, "solicitudes": 0, "tokens_entrada_total": ent, "tokens_salida_total": sal, "tokens_entrada_prom": 0}
             for dep, (ent, sal) in azure.items()]
    filas += [f for f in etapas if str(f.get("modelo")) not in azure and not str(f.get("modelo")).startswith("gpt-")]
    return filas, True


def ultimos(dias: int) -> tuple[datetime, datetime]:
    fin = datetime.now(timezone.utc)
    return fin - timedelta(days=int(dias)), fin


# ---------------------------------------------------------------------------------------------------------------------
# Costo real: lo que Azure cobró (Cost Management, rol Cost Management Reader sobre la suscripción en AZ_SUSCRIPCION_ID).
# ---------------------------------------------------------------------------------------------------------------------
SERVICIOS_IA = {"foundry models", "cognitive services", "azure openai", "azure ai services"}
NOMBRE_SERVICIO = {"Foundry Models": "IA (Azure OpenAI)", "Container Instances": "Veridy (contenedores)",
                   "Azure App Service": "Panel (App Service)", "Azure Container Apps": "Núcleo (Container Apps)",
                   "Azure Database for PostgreSQL": "Base de datos de Veridy"}


def costo_azure(inicio: datetime, fin: datetime) -> dict | None:
    """Lo que Azure cobró entre inicio y fin, por servicio: {"total", "ia", "moneda", "servicios": [(nombre, monto)],
    "desde", "hasta"}. None si no se pudo leer. Azure publica el costo con hasta 24 h de atraso."""
    sub = os.environ.get("AZ_SUSCRIPCION_ID", "")
    if not sub:
        return None
    cuerpo = json.dumps({"type": "ActualCost", "timeframe": "Custom",
                         "timePeriod": {"from": f"{inicio.astimezone(timezone.utc):%Y-%m-%dT00:00:00Z}", "to": f"{fin.astimezone(timezone.utc):%Y-%m-%dT23:59:59Z}"},
                         "dataset": {"granularity": "None", "aggregation": {"c": {"name": "Cost", "function": "Sum"}},
                                     "grouping": [{"type": "Dimension", "name": "ServiceName"}]}}).encode()
    pet = urllib.request.Request(f"{API}/subscriptions/{sub}/providers/Microsoft.CostManagement/query?api-version=2023-11-01", data=cuerpo, method="POST",
                                 headers={"Authorization": "Bearer " + _token(), "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(pet, timeout=30) as r:
            d = json.load(r)
    except Exception:
        return None
    cols = [c["name"] for c in d["properties"]["columns"]]
    ic, isv, imo = cols.index("Cost"), cols.index("ServiceName"), cols.index("Currency")
    por = {}
    moneda = "USD"
    for f in d["properties"]["rows"]:
        moneda = f[imo] or moneda
        por[f[isv]] = por.get(f[isv], 0.0) + float(f[ic] or 0)
    servicios = sorted(((NOMBRE_SERVICIO.get(k, k), v) for k, v in por.items() if v >= 0.005), key=lambda x: -x[1])
    return {"total": sum(por.values()), "ia": sum(v for k, v in por.items() if k.lower() in SERVICIOS_IA), "moneda": moneda,
            "servicios": servicios, "desde": inicio, "hasta": fin}
