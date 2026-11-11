"""Prueba mínima de kerna_comun.notas: la nota de sugerencia viaja como JSON y se lee de vuelta."""
import json

import pytest

from kerna_comun import notas

pytestmark = [pytest.mark.pr("PR-16"), pytest.mark.rf("RF-06")]


def _sugerencia() -> dict:
    return {
        "tipo": "kerna_sugerencia", "id_solicitud": "sol-1", "version_corpus": 3, "estado": "completada",
        "modo": "oficial", "generado_en": "2026-01-01T00:00:00Z", "articulos": [{
            "id_sugerencia": "11111111-1111-4111-8111-111111111111", "id_articulo": "21643-art-1",
            "norma": "Ley N.° 21.643", "articulo": "1", "explicacion": "Explicación de prueba.",
            "cita": "Texto de prueba.", "enlace_fuente": "https://www.bcn.cl/leychile/", "confianza": 0.8}],
    }


def test_modelo_sugerencia_acepta_el_contrato():
    s = notas.Sugerencia(**_sugerencia())
    assert s.estado == "completada" and s.version == notas.VERSION
    assert s.articulos[0].norma == "Ley N.° 21.643"


def test_ignora_campos_desconocidos():
    datos = _sugerencia() | {"campo_futuro": 1}
    assert not hasattr(notas.Sugerencia(**datos), "campo_futuro")


def test_ida_y_vuelta_json():
    original = notas.Sugerencia(**_sugerencia())
    assert notas.leer(notas.escribir(original)) == original


def test_nota_comun_no_es_de_kerna():
    assert notas.leer("comentario de un auditor") is None
    assert notas.leer(json.dumps({"tipo": "otra_cosa"})) is None
    assert notas.leer(json.dumps([1, 2])) is None
