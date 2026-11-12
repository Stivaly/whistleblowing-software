"""Enmascarado de credenciales de URIs en mensajes de error y logs."""
import io
import logging
import sys

import pytest

import secretos

CLAVE = "Cl4ve-Falsa_123"
URI = f"mongodb+srv://usuario:{CLAVE}@cluster0.example.mongodb.net/kerna?retryWrites=true"


def test_enmascara_uri_y_conserva_el_resto():
    s = secretos.enmascarar(f"fallo al conectar a {URI} por timeout")
    assert CLAVE not in s
    assert "mongodb+srv://usuario:***@cluster0.example.mongodb.net/kerna?retryWrites=true" in s


def test_clave_con_arroba_sin_escapar():
    s = secretos.enmascarar("mongodb://u:p@ss@host:27017/db")
    assert "p@ss" not in s and "u:***@host:27017/db" in s


def test_otros_esquemas_y_texto_sin_credenciales():
    assert secretos.enmascarar("postgresql://app:x@db/kerna") == "postgresql://app:***@db/kerna"
    assert secretos.enmascarar("https://cloud.mongodb.com/api") == "https://cloud.mongodb.com/api"


def test_filtro_de_logging_enmascara_mensaje_args_y_traceback():
    flujo = io.StringIO()
    h = logging.StreamHandler(flujo)
    h.addFilter(secretos.FiltroSecretos())
    log = logging.getLogger("prueba_secretos")
    log.addHandler(h)
    log.propagate = False
    log.error("uri %s", URI)
    try:
        raise ValueError(f"mala {URI}")
    except ValueError:
        log.exception("fallo")
    assert CLAVE not in flujo.getvalue()
    assert "usuario:***@" in flujo.getvalue()


def test_mongo_client_no_filtra_la_clave_en_el_error(monkeypatch):
    import pymongo

    def falla(uri, **kw):
        raise pymongo.errors.InvalidURI(f"URI rara: {uri}")
    monkeypatch.setattr(pymongo, "MongoClient", falla)
    with pytest.raises(secretos.ErrorConexion) as e:
        secretos.mongo_client(URI)
    assert CLAVE not in str(e.value)
    assert e.value.__cause__ is None and e.value.__suppress_context__


def test_excepthook_enmascara(capsys):
    try:
        raise RuntimeError(f"x {URI}")
    except RuntimeError:
        secretos._excepthook(*sys.exc_info())
    assert CLAVE not in capsys.readouterr().err
