"""Fixtures compartidas de las pruebas del pipeline."""
import os
from urllib.parse import urlparse

import pytest


@pytest.fixture
def db():
    from pymongo import MongoClient

    uri = os.environ.get("MONGODB_TEST_URI", "mongodb://127.0.0.1:27018/kerna_test")
    # Cada prueba borra la base: solo se acepta un servidor local y una base *_test.
    host = urlparse(uri).hostname
    assert host in ("127.0.0.1", "localhost"), f"MONGODB_TEST_URI debe ser local, no {host}"
    client = MongoClient(uri, serverSelectionTimeoutMS=3000)
    base = client.get_default_database()
    assert base.name.endswith("_test"), f"la base de prueba debe terminar en _test, no {base.name}"
    client.drop_database(base.name)
    yield base
    client.drop_database(base.name)
    client.close()
