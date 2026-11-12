"""Enmascara credenciales de URIs en mensajes de error y logs (solo biblioteca estándar).

Una URI como mongodb+srv://usuario:clave@host/base lleva la clave en claro. Si un traceback,
un log o un print la reproduce, queda en la salida del job de Azure (Log Analytics), en
terminales y en transcripciones. Este módulo reemplaza la clave por *** en cualquier texto.

  enmascarar(texto)        -> texto con usuario:clave@ convertido en usuario:***@
  proteger()               -> instala el filtro en logging y en sys.excepthook (llamar en main)
  mongo_client(uri, **kw)  -> MongoClient; si falla, relanza el error sin la URI ni la clave
"""
from __future__ import annotations

import logging
import re
import sys
import traceback

# esquema://usuario:clave@  (la clave llega hasta el último '@' antes del host; admite '@' sin escapar)
_URI = re.compile(r"(?P<esq>[A-Za-z][A-Za-z0-9+.\-]*://)(?P<usr>[^:/?#\s@]*):(?P<clave>[^/?#\s]*)@")


def enmascarar(texto) -> str:
    return _URI.sub(lambda m: f"{m['esq']}{m['usr']}:***@", str(texto))


class FiltroSecretos(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        try:
            record.msg = enmascarar(record.getMessage())
            record.args = ()
            if record.exc_info:
                record.exc_text = enmascarar("".join(traceback.format_exception(*record.exc_info)))
        except Exception:  # un filtro nunca debe romper el log
            pass
        return True


def _excepthook(tipo, valor, tb):
    sys.stderr.write(enmascarar("".join(traceback.format_exception(tipo, valor, tb))))


def proteger() -> None:
    """Enmascara URIs en logging (handlers de la raíz) y en los tracebacks no capturados."""
    raiz = logging.getLogger()
    for h in raiz.handlers:
        if not any(isinstance(f, FiltroSecretos) for f in h.filters):
            h.addFilter(FiltroSecretos())
    sys.excepthook = _excepthook


class ErrorConexion(RuntimeError):
    """Error al conectar con Mongo, con el mensaje ya enmascarado y sin la causa encadenada."""


def mongo_client(uri: str, **opciones):
    from pymongo import MongoClient
    try:
        return MongoClient(uri, **opciones)
    except Exception as e:
        raise ErrorConexion(f"{type(e).__name__}: {enmascarar(e)}") from None
