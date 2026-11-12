"""Pruebas de los costos y supuestos del capítulo 25 (kerna/front/app/finanzas.py) contra las tablas del informe."""
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "front"))

import pytest  # noqa: E402

from app import finanzas  # noqa: E402


def test_inversion_y_credito_tabla_107_y_113():
    assert finanzas.inversion_total_clp() == 17_621_028
    c = finanzas.tabla_credito()
    assert [round(x["interes"]) for x in c[:3]] == [2_212_372, 1_434_324, 536_539]
    assert [round(x["amortizacion"]) for x in c[:3]] == [5_055_716, 5_833_764, 6_731_548]
    assert c[3]["interes"] == 0


def test_costos_fijos_tabla_111():
    assert [finanzas.total_fijos_clp(a) for a in range(1, 6)] == pytest.approx([4_315_381, 4_363_543, 4_396_186, 4_429_809, 4_742_665], abs=2)
    assert dict(finanzas.costos_fijos(2))["Renovación del certificado digital"] == 16_964
    assert dict(finanzas.costos_fijos(5))["Contabilidad externa"] == 0


def test_precios_y_costo_de_servir_tablas_108_y_110():
    assert round(finanzas.precio_anual_clp("basico", 2)) == 1_527_696
    assert round(finanzas.precio_anual_clp("plataforma", 5)) == 7_998_991
    assert round(finanzas.costo_servir_anual_clp("pro", 3)) == 524_509
    # la cuota de API de 15.000 pesos al mes son 180.000 al año; el resto del costo de servir es infraestructura y soporte
    assert finanzas.costo_servir_sin_ia_anual_clp("plataforma", 1) == 1_236_000 - 180_000


def test_flujo_tabla_114_y_indicadores_tabla_115():
    r = finanzas.proyeccion_capitulo()
    esperado = {"ventas": [25_523_400, 37_937_784, 51_074_060, 64_964_369, 79_642_129],
                "participacion_veridy": [2_898_432, 4_257_692, 5_795_421, 7_519_565, 9_438_385],
                "uai": [8_769_410, 18_370_902, 31_389_924, 41_615_842, 51_480_234],
                "impuesto": [2_236_200, 4_409_016, 7_219_683, 9_571_644, 11_840_454],
                "flujo": [4_343_339, 10_993_967, 17_438_693, 32_044_198, 39_639_780]}
    for k, v in esperado.items():
        assert [x[k] for x in r["anios"]] == pytest.approx(v, abs=3), k
    assert r["van"] == pytest.approx(27_932_860, abs=5)
    assert r["tir"] == pytest.approx(0.665, abs=0.0005)
    assert round(r["indice_rentabilidad"], 2) == 2.59 and r["recuperacion_anio"] == 3


def test_uf_y_dolar():
    p = finanzas.parametros()
    assert p["usd_clp"] == 994.29
    assert finanzas.a_uf(40_000) == 1.0
    assert finanzas.usd_a_uf(40_000 / 994.29) == pytest.approx(1.0)
    assert finanzas.a_uf(40_000 * 1.03, 2) == pytest.approx(1.0)  # la UF sigue la inflación


def test_anio_de_operacion_y_impuesto():
    assert finanzas.anio_operacion(date(2026, 11, 12)) == 1 and finanzas.anio_operacion(date(2028, 3, 1)) == 2 and finanzas.anio_operacion(date(2040, 1, 1)) == 5
    assert [finanzas.tasa_impuesto(a) for a in (1, 2, 3, 5)] == [0.255, 0.24, 0.23, 0.23]
    assert finanzas.prorrata(365_000, 30) == 30_000
