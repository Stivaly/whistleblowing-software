"""Esquema único de ajustes (kerna_comun.ajustes_esquema): defectos, rangos, opciones y validación."""
import os
import sys
from pathlib import Path

import pytest

from kerna_comun import ajustes_esquema as esq

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "front"))
os.environ.setdefault("FRONT_CLAVE", "clave-de-prueba")
os.environ.setdefault("LOG_ANALYTICS_WORKSPACE_ID", "ws-prueba")


def test_defectos_son_validos_y_son_lo_desplegado():
    assert esq.validar(esq.DEFECTOS) == esq.DEFECTOS
    assert esq.validar({}) == esq.DEFECTOS
    d = esq.DEFECTOS
    assert (d["envios"], d["reintentos"], d["espera"], d["revision"], d["candidatos"], d["maxresp"], d["alerta"]) == (5, 3, 24, 30, 70, 15, 6)
    assert d["compartir"] == ["analista"] and d["evaluador"] is True and d["reprocesar"] is False
    assert d["cadena"] == [{"v": "azure", "on": True}, {"v": "gemini", "on": True}]


@pytest.mark.parametrize("x", [10, 20, 30, 40, 50, 60, 70])
def test_candidatos_de_10_a_70_de_10_en_10(x):
    assert esq.validar({"candidatos": x})["candidatos"] == x


@pytest.mark.parametrize("x", [5, 15, 75, 80, 0, True, "70", 70.0])
def test_candidatos_fuera_de_rango_o_paso(x):
    with pytest.raises(ValueError):
        esq.validar({"candidatos": x})


def test_cadena_necesita_un_modelo_encendido_y_los_dos_proveedores():
    ap = [{"v": "azure", "on": False}, {"v": "gemini", "on": False}]
    with pytest.raises(ValueError):
        esq.validar({"cadena": ap})
    assert esq.validar({"cadena": [{"v": "gemini", "on": True}, {"v": "azure", "on": False}]})["cadena"][0]["v"] == "gemini"
    for malo in ([{"v": "azure", "on": True}], [{"v": "azure", "on": True}, {"v": "otro", "on": True}], "x", [1, 2]):
        with pytest.raises(ValueError):
            esq.validar({"cadena": malo})


def test_compartir_valida_equipos_y_acepta_lista_vacia():
    assert esq.validar({"compartir": []})["compartir"] == []
    assert esq.validar({"compartir": ["legal", "comite"]})["compartir"] == ["legal", "comite"]
    for malo in (["desconocido"], ["legal", "legal"], "legal"):
        with pytest.raises(ValueError):
            esq.validar({"compartir": malo})


def test_equipos_y_proveedores():
    assert esq.EQUIPOS["analista"]["receptor"] == "Auditor Kerna"
    assert {k: e["receptor"] for k, e in esq.EQUIPOS.items() if k != "analista"} == {
        "comite": "kerna-equipo-comite", "auditoria": "kerna-equipo-auditoria", "legal": "kerna-equipo-legal"}
    assert esq.PROVEEDOR_DE == {"azure": "azure-openai", "gemini": "gemini"}


def test_los_defectos_coinciden_con_los_recomendados_del_front():
    from app import ajustes
    assert ajustes.RECOMENDADO == esq.DEFECTOS and ajustes.validar is esq.validar
    assert set(ajustes.APLICA_YA) == set(esq.DEFECTOS)
    por = {it["k"]: it for g in ajustes.GRUPOS for it in g["items"]}
    assert (por["candidatos"]["min"], por["candidatos"]["max"], por["candidatos"]["step"]) == (10, 70, 10)
