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
