"""Configuración común de la suite de Kerna: carga el plugin de resumen y fija la semilla por prueba."""
import random

import pytest

import plugin_resumen

pytest_plugins = []  # el plugin se carga con `-p plugin_resumen` o, si falta, abajo


def pytest_configure(config):
    if not config.pluginmanager.has_plugin("plugin_resumen"):
        config.pluginmanager.register(plugin_resumen, "plugin_resumen")


@pytest.fixture(autouse=True)
def _semilla_fija():
    random.seed(plugin_resumen.SEMILLA)
