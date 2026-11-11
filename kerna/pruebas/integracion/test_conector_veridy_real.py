"""Acceso real a Veridy con la cuenta de servicio: inicia sesión, lista casos, lee uno y cierra. No publica nada.

Requiere VERIDY_URL, VERIDY_USUARIO y VERIDY_PASSWORD en el entorno.
"""
import os

import pytest

from kerna_conector import lector_casos
from kerna_conector.veridy import CasoNoAccesible, ClienteVeridy

pytestmark = pytest.mark.integracion


@pytest.mark.skipif(not all(os.environ.get(v) for v in ("VERIDY_URL", "VERIDY_USUARIO", "VERIDY_PASSWORD")),
                    reason="faltan VERIDY_URL, VERIDY_USUARIO o VERIDY_PASSWORD")
def test_sesion_listado_y_lectura_reales():
    c = ClienteVeridy(os.environ["VERIDY_URL"], os.environ["VERIDY_USUARIO"], os.environ["VERIDY_PASSWORD"])
    try:
        assert c.id_usuario
        casos = c.listar_casos()
        assert isinstance(casos, list)
        for meta in casos:
            if meta.get("accessible") is False:
                continue
            try:
                caso = c.leer_caso(meta["id"])
            except CasoNoAccesible:
                continue
            assert caso["id"] == meta["id"] and "comments" in caso
            assert isinstance(lector_casos.extraer_relato(caso), str)
            break
    finally:
        c.cerrar_sesion()
