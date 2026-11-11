"""Pruebas de integración con servicios reales: se omiten con motivo claro si falta la variable necesaria.

Uso en una prueba: `def test_x(requiere): requiere("QDRANT_URL", "QDRANT_API_KEY")` o las fixtures
`qdrant_url`, `voyage_key`, `gemini_key`, `nucleo_url`. Las variables vienen de kerna/pipeline_bcn/.env
(scripts/probar.sh las carga sin imprimirlas).
"""
import os

import pytest


def pytest_collection_modifyitems(items):
    for item in items:
        if "/integracion/" in str(item.fspath).replace("\\", "/"):
            item.add_marker(pytest.mark.integracion)


@pytest.fixture
def requiere():
    def _requiere(*nombres):
        faltan = [n for n in nombres if not os.environ.get(n)]
        if faltan:
            pytest.skip("integración omitida: falta " + ", ".join(faltan))
        return [os.environ[n] for n in nombres]
    return _requiere


@pytest.fixture
def qdrant_url(requiere):
    return requiere("QDRANT_URL", "QDRANT_API_KEY")


@pytest.fixture
def voyage_key(requiere):
    return requiere("VOYAGE_API_KEY")[0]


@pytest.fixture
def gemini_key(requiere):
    return requiere("GEMINI_API_KEY")[0]


@pytest.fixture
def nucleo_url(requiere):
    return requiere("KERNA_API_URL", "KERNA_CLIENT_ID", "KERNA_CLIENT_SECRET")
