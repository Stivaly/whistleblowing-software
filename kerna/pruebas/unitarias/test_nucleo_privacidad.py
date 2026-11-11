import asyncio
import json

import pytest

from kerna_comun import telemetria
from nucleo_apoyo import FakeGemini, FakeLocal, FakeQdrant, FakeVoyage, armar, caida, procesar_caso

RUT, CORREO = "12.345.678-5", "pepe.ficticio@ejemplo.cl"
TEXTO = f"El jefe, RUT {RUT}, escribió desde {CORREO} amenazas reiteradas ZXQSENTINELA77 al equipo."


def cuerpos(e):
    out = [json.dumps(x, default=str) for x in e.gemini.llamadas]
    out += [json.dumps(x, default=str) for x in e.voyage.llamadas]
    out += [json.dumps(x, default=str) for x in e.qdrant.llamadas]
    out += [json.dumps(x, default=str) for x in e.local.llamadas]
    return out


@pytest.mark.pr("PR-24")
@pytest.mark.parametrize("nube_caida", [False, True])
def test_identificadores_sembrados_no_llegan_a_los_proveedores(nube_caida):
    e = armar(voyage=FakeVoyage(caida()) if nube_caida else None)
    # el voyage falso registra la consulta aunque falle; el local recibe la del respaldo
    g, _ = asyncio.run(procesar_caso(e, texto=TEXTO))
    assert g["estado"] == "completada"
    todo = "\n".join(cuerpos(e))
    assert todo and RUT not in todo and CORREO not in todo and "12345678" not in todo
    assert "ZXQSENTINELA77" in todo  # el resto del texto sí viaja (solo se retiran los identificadores)
    assert "[RUT" in todo and "[CORREO" in todo


@pytest.mark.rnf("RNF-privacidad")
def test_telemetria_y_almacen_sin_texto_del_caso():
    visto = []
    telemetria.quitar_emisores()
    telemetria.registrar_emisor(lambda clase, nombre, valor, at: visto.append((clase, nombre, valor, dict(at))))
    try:
        e = armar()
        asyncio.run(procesar_caso(e, texto=TEXTO))
    finally:
        telemetria.quitar_emisores()
    assert visto
    for _, nombre, valor, at in visto:
        assert set(at) <= telemetria.ATRIBUTOS_PERMITIDOS
        plano = json.dumps([nombre, valor, at], default=str)
        assert "ZXQSENTINELA77" not in plano and RUT not in plano and CORREO not in plano
    volcado = json.dumps([list(e.almacen.solicitudes.values()), e.almacen.articulos], default=str)
    assert "ZXQSENTINELA77" not in volcado and RUT not in volcado


@pytest.mark.rnf("RNF-privacidad")
def test_el_texto_no_aparece_en_los_logs(caplog):
    caplog.set_level("DEBUG")
    e = armar(gemini=FakeGemini({"gemini-3.8-flash": lambda *a: 1 / 0}))
    asyncio.run(procesar_caso(e, texto=TEXTO))
    assert "ZXQSENTINELA77" not in caplog.text and RUT not in caplog.text
