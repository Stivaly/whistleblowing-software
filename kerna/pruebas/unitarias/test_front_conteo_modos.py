"""El reparto principal/respaldo sale de los casos reales de la fila `conector`: principal + respaldo = con sugerencia."""
from kerna.front.app import reintentos

FILA = {"actualizado_en": "2026-11-15T20:00:00Z", "casos": 10, "completado": 9, "en_revision_manual": 1, "error": 0, "nuevo": 0, "pendiente": 0,
        "modo_oficial": 7, "modo_respaldo": 2, "modo_desconocido": 0}


def test_principal_mas_respaldo_es_con_sugerencia():
    r = reintentos.con_estado_real(None, FILA)
    assert r["principal"] == 7 and r["respaldo"] == 1 and r["con_sugerencia"] == 8 and r["sin_sugerencia"] == 2
    assert r["con_sugerencia"] + r["sin_sugerencia"] == r["casos"]


def test_sin_modo_conocido_no_hay_reparto():
    assert reintentos.con_estado_real(None, {**FILA, "modo_desconocido": 3})["principal"] is None
    assert reintentos.con_estado_real(None, {k: v for k, v in FILA.items() if not k.startswith("modo_")})["respaldo"] is None
