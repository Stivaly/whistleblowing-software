import pytest


@pytest.fixture(autouse=True)
def _cache_front_limpia():
    """La caché compartida del front (front/app/cache.py) no debe pasar datos de una prueba a otra."""
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "front"))
    from app import cache
    cache.vaciar()
    yield
    cache.vaciar()


@pytest.fixture(autouse=True)
def _cuentas_simuladas(request, monkeypatch):
    """Las pruebas del front (y las de clientes) corren con tablas de cuentas simuladas que ya tienen la cuenta `admin` (Dirección)."""
    if not request.module.__name__.startswith(("test_front", "test_clientes_admin")):
        yield
        return
    import sesion_prueba
    sesion_prueba.instalar(monkeypatch)
    yield
