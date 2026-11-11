"""Plugin de pytest de Kerna: registra las marcas del informe y vuelca el mapa nodeid -> marcas -> resultado.

Se carga con `-p plugin_resumen` (scripts/probar.sh lo hace). Si existe la variable KERNA_MARCAS_JSON, escribe ahí
un JSON por corrida; con pytest-xdist lo escribe solo el proceso principal. Fija la semilla (KERNA_SEMILLA).
"""
from __future__ import annotations

import json
import os
import random

import pytest

MARCAS_INFORME = ("pr", "rf", "rnf", "cu")
SEMILLA = int(os.environ.get("KERNA_SEMILLA", "20260101"))
_CLAVE = "kerna_marcas"


def _marcas(item) -> dict:
    salida = {}
    for marca in MARCAS_INFORME:
        ids = [str(a) for m in item.iter_markers(name=marca) for a in m.args]
        if ids:
            salida[marca] = sorted(set(ids))
    return salida


class _Recolector:
    def __init__(self):
        self.resultados: dict[str, dict] = {}

    def pytest_runtest_logreport(self, report):
        if not (report.when == "call" or (report.when == "setup" and report.outcome != "passed")):
            return
        marcas = {}
        for clave, valor in report.user_properties:
            if clave == _CLAVE:
                marcas = json.loads(valor)
        previo = self.resultados.get(report.nodeid)
        if previo and previo["resultado"] == "fallida":
            return
        self.resultados[report.nodeid] = {
            "marcas": marcas,
            "resultado": {"passed": "pasada", "failed": "fallida", "skipped": "omitida"}[report.outcome],
            "duracion_s": round(report.duration, 4),
        }

    def pytest_sessionfinish(self, session):
        destino = os.environ.get("KERNA_MARCAS_JSON")
        if not destino or hasattr(session.config, "workerinput"):
            return
        with open(destino, "w", encoding="utf-8") as f:
            json.dump({"semilla": SEMILLA, "pruebas": self.resultados}, f, ensure_ascii=False, indent=1, sort_keys=True)


def pytest_configure(config):
    for marca in MARCAS_INFORME:
        config.addinivalue_line("markers", f"{marca}(id): ID del informe que verifica la prueba")
    random.seed(SEMILLA)
    if not hasattr(config, "workerinput"):
        config.pluginmanager.register(_Recolector(), "kerna_recolector")


def pytest_sessionstart(session):
    random.seed(SEMILLA)


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    # Las marcas viajan en user_properties para que el proceso principal las vea también con xdist.
    if call.when == "setup":
        item.user_properties.append((_CLAVE, json.dumps(_marcas(item))))
    yield
