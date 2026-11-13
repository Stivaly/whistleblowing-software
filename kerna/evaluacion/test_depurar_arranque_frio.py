import depurar_arranque_frio as d


def ped(ts, ms):
    return [{"id": f"p{i}", "t": f"2026-11-12T10:{t}:00Z", "ms": m} for i, (t, m) in enumerate(zip(ts, ms))]


def test_excluye_primero_atipico_tras_inactividad():
    r = d.depurar(ped(["00", "01", "02", "03", "04"], [15000, 100, 120, 110, 105]))
    assert r["n_excluidos"] == 1 and r["excluidos"][0]["id"] == "p0"
    assert r["con_exclusion"]["p95"] < r["sin_exclusion"]["p95"]


def test_mantiene_alto_que_no_es_primero_tras_pausa():
    r = d.depurar(ped(["00", "01", "02", "03", "04"], [100, 15000, 120, 110, 105]))
    assert r["n_excluidos"] == 0


def test_mantiene_primero_no_atipico():
    assert d.depurar(ped(["00", "01", "02", "03"], [130, 100, 120, 110]))["n_excluidos"] == 0


def test_pedido_tras_pausa_de_20_min():
    r = d.depurar(ped(["00", "01", "02", "30", "31"], [100, 110, 105, 9000, 100]))
    assert [e["id"] for e in r["excluidos"]] == ["p3"]


def test_sin_marcas_de_hora_no_inventa():
    r = d.depurar([{"id": "a", "t": None, "ms": 1}, {"id": "b", "t": None, "ms": 999}])
    assert r["n_excluidos"] == 0 and "repetir con calentamiento" in r["estado"]
