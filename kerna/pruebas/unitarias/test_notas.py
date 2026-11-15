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


def test_nota_lleva_campos_del_revisor_y_lista_vetados():
    from kerna_conector import publicador
    base = _sugerencia()["articulos"][0]
    arts = [base | {"dictamen": "confirma", "revision_juridica": "revisado", "condiciones": ["x"]},
            base | {"id_articulo": "A-2", "dictamen": "condiciona", "condiciones": ["vigencia"]},
            base | {"id_articulo": "A-3", "dictamen": "veta", "causal_veto": "falta_sujeto_exigido",
                    "hecho_ids_revision": ["H1"]},
            base | {"id_articulo": "A-4", "revision_juridica": "sin_revision"}]
    s = publicador.armar_sugerencia(_sugerencia() | {"articulos": arts})
    assert [a.veredicto for a in s.articulos] == ["mantiene", "condiciona", "veta", None]
    assert s.articulos[1].condiciones == ["vigencia"] and s.articulos[0].condiciones == ["x"]
    assert s.articulos[2].causal == "falta_sujeto_exigido" and s.articulos[1].causal is None
    assert s.vetados == ["A-3"]
    assert "H1" not in publicador.contenido(s)
    assert notas.leer(publicador.contenido(s)) == s


def test_sin_revisor_la_nota_queda_igual():
    from kerna_conector import publicador
    s = publicador.armar_sugerencia(_sugerencia())
    assert s.vetados == [] and s.articulos[0].veredicto is None
