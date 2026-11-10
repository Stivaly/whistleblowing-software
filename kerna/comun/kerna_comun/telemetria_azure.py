"""Envío de la telemetría de Kerna AI a Application Insights (OpenTelemetry, distribución de Azure Monitor).

Solo salen las señales de `kerna_comun.telemetria`, ya filtradas por su lista de atributos permitidos:
- cada evento y cada etapa, como registro del logger `kerna.eventos` (tabla AppTraces, con sus atributos);
- la duración de cada etapa, en el histograma `kerna.etapa.duracion` (milisegundos);
- cada contador, en el contador `kerna.<nombre>`.
Las instrumentaciones automáticas de HTTP quedan desactivadas: registrarían las URL de Veridy, que llevan el
identificador real del caso.
"""
from __future__ import annotations

import logging

from kerna_comun import telemetria

LOGGER = "kerna.eventos"
# Atributos de baja cardinalidad: los únicos que se usan como dimensiones de métricas.
DIMENSIONES = frozenset({"etapa", "modo", "recuperacion", "proveedor", "modelo", "embedding", "coleccion",
                         "estado", "motivo", "codigo", "cliente", "contingencia", "resultado", "tipo",
                         "json_valido"})
_SIN_INSTRUMENTAR = ("azure_sdk", "django", "fastapi", "flask", "psycopg2", "requests", "urllib", "urllib3")

_activo = False


def activar(servicio: str) -> None:
    global _activo
    if _activo:
        return
    from azure.monitor.opentelemetry import configure_azure_monitor
    from opentelemetry import metrics
    from opentelemetry.sdk.resources import Resource

    configure_azure_monitor(
        logger_name=LOGGER,
        resource=Resource.create({"service.name": servicio, "service.namespace": "kerna"}),
        instrumentation_options={nombre: {"enabled": False} for nombre in _SIN_INSTRUMENTAR},
    )
    registro = logging.getLogger(LOGGER)
    registro.setLevel(logging.INFO)
    medidor = metrics.get_meter("kerna")
    duracion = medidor.create_histogram("kerna.etapa.duracion", unit="ms")
    contadores: dict = {}

    def emisor(clase: str, nombre: str, valor, atributos: dict) -> None:
        dimensiones = {c: v for c, v in atributos.items() if c in DIMENSIONES}
        if clase == "contador":
            if nombre not in contadores:
                contadores[nombre] = medidor.create_counter(f"kerna.{nombre}")
            contadores[nombre].add(valor, dimensiones)
            return
        if clase == "etapa":
            duracion.record(valor, dimensiones)
        registro.info(nombre, extra={"clase": clase, **atributos})

    telemetria.registrar_emisor(emisor)
    _activo = True
