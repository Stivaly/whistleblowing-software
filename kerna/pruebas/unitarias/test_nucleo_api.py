import asyncio
import hashlib
import uuid

import pytest

from nucleo_apoyo import (FLASH, SECRETO, FakeGemini, armar, cabeceras, cliente_http, falla, obtener_token,
                          procesar_caso)


def run(c):
    return asyncio.run(c)


@pytest.mark.pr("PR-29")
def test_salud_sin_autenticacion_ni_proveedores():
    e = armar()

    async def f():
        async with cliente_http(e.app) as c:
            return await c.get("/salud")
    r = run(f())
    assert r.status_code == 200 and r.json()["estado"] == "ok" and "version" in r.json()
    assert not e.gemini.llamadas and not e.voyage.llamadas


@pytest.mark.pr("PR-29")
def test_token_correcto_incorrecto_y_rutas_sin_token():
    e = armar()

    async def f():
        async with cliente_http(e.app) as c:
            ok = await obtener_token(c)
            mal = await obtener_token(c, secreto="otro")
            sin = await obtener_token(c, client_id="desconocido")
            gt = await c.post("/oauth/token", data={"grant_type": "password", "client_id": "conector", "client_secret": SECRETO})
            ref = str(uuid.uuid4())
            r1 = await c.post("/v1/casos", json={"ref_opaca": ref, "id_empresa": "e", "texto": "x"})
            r2 = await c.get(f"/v1/casos/{ref}/sugerencia")
            r3 = await c.get(f"/v1/casos/{ref}/sugerencia", headers={"Authorization": "Bearer basura"})
            return ok, mal, sin, gt, r1, r2, r3
    ok, mal, sin, gt, r1, r2, r3 = run(f())
    assert ok.status_code == 200 and ok.json()["token_type"] == "bearer" and ok.json()["expires_in"] == 600
    assert mal.status_code == sin.status_code == gt.status_code == 401
    assert r1.status_code == r2.status_code == r3.status_code == 401


@pytest.mark.pr("PR-29")
def test_token_vencido_da_401():
    e = armar()

    async def f():
        async with cliente_http(e.app) as c:
            h = await cabeceras(c)
            antes = await c.get(f"/v1/casos/{uuid.uuid4()}/sugerencia", headers=h)
            e.reloj.avanzar(599)
            casi = await c.get(f"/v1/casos/{uuid.uuid4()}/sugerencia", headers=h)
            e.reloj.avanzar(2)
            despues = await c.get(f"/v1/casos/{uuid.uuid4()}/sugerencia", headers=h)
            return antes, casi, despues
    antes, casi, despues = run(f())
    assert antes.status_code == casi.status_code == 404 and despues.status_code == 401


@pytest.mark.pr("PR-31")
def test_envios_simultaneos_una_sola_solicitud_y_una_ejecucion():
    e = armar()
    ref = str(uuid.uuid4())

    async def f():
        async with cliente_http(e.app) as c:
            h = await cabeceras(c)
            rs = await asyncio.gather(*[c.post("/v1/casos", json={"ref_opaca": ref, "id_empresa": "e", "texto": "acoso reiterado"},
                                               headers=h) for _ in range(25)])
            await e.app.state.esperar_tareas()
            return rs
    rs = run(f())
    assert {r.status_code for r in rs} == {202} and len({r.json()["id_solicitud"] for r in rs}) == 1
    assert len(e.almacen.solicitudes) == 1
    assert len(e.gemini.generacion()) == 1 and len(e.voyage.llamadas) == 1


@pytest.mark.pr("PR-31")
def test_clientes_distintos_no_se_mezclan():
    sha = lambda s: hashlib.sha256(s.encode()).hexdigest()
    e = armar(clientes={"a": {"secreto_sha256": sha("sa"), "cliente": "cli_a"},
                        "b": {"secreto_sha256": sha("sb"), "cliente": "cli_b"}})
    ref = str(uuid.uuid4())

    async def f():
        async with cliente_http(e.app) as c:
            ha, hb = await cabeceras(c, "a", "sa"), await cabeceras(c, "b", "sb")
            ra = await c.post("/v1/casos", json={"ref_opaca": ref, "id_empresa": "e", "texto": "caso a"}, headers=ha)
            rb = await c.post("/v1/casos", json={"ref_opaca": ref, "id_empresa": "e", "texto": "caso b"}, headers=hb)
            await e.app.state.esperar_tareas()
            ga = await c.get(f"/v1/casos/{ref}/sugerencia", headers=ha)
            return ra, rb, ga
    ra, rb, ga = run(f())
    assert ra.json()["id_solicitud"] != rb.json()["id_solicitud"] and len(e.almacen.solicitudes) == 2
    assert ga.json()["id_solicitud"] == ra.json()["id_solicitud"] and len(e.gemini.generacion()) == 2


@pytest.mark.pr("PR-34")
def test_rafaga_con_429_conmuta_sin_perder_solicitudes():
    e = armar(gemini=FakeGemini({FLASH: falla(429)}))
    refs = [str(uuid.uuid4()) for _ in range(12)]

    async def f():
        async with cliente_http(e.app) as c:
            h = await cabeceras(c)
            rs = await asyncio.gather(*[c.post("/v1/casos", json={"ref_opaca": r, "id_empresa": "e", "texto": "texto"}, headers=h) for r in refs])
            await e.app.state.esperar_tareas()
            return rs, [(await c.get(f"/v1/casos/{r}/sugerencia", headers=h)).json() for r in refs]
    rs, gs = run(f())
    assert {r.status_code for r in rs} == {202}
    assert all(g["estado"] == "completada" and g["modo"] == "respaldo" and g["contingencia"] for g in gs)


@pytest.mark.pr("PR-29")
def test_validacion_de_entrada_y_404():
    e = armar()

    async def f():
        async with cliente_http(e.app) as c:
            h = await cabeceras(c)
            grande = await c.post("/v1/casos", json={"ref_opaca": str(uuid.uuid4()), "id_empresa": "e", "texto": "x" * 60001}, headers=h)
            mala = await c.post("/v1/casos", json={"ref_opaca": "no-uuid", "id_empresa": "e", "texto": "x"}, headers=h)
            nada = await c.get(f"/v1/casos/{uuid.uuid4()}/sugerencia", headers=h)
            return grande, mala, nada
    grande, mala, nada = run(f())
    assert grande.status_code == 422 and mala.status_code == 422 and nada.status_code == 404


@pytest.mark.pr("PR-29")
def test_pendiente_antiguo_pasa_a_tiempo_agotado_al_consultar():
    e = armar()

    async def f():
        async with cliente_http(e.app) as c:
            h = await cabeceras(c)
            ref = str(uuid.uuid4())
            await e.almacen.crear_solicitud({"id_solicitud": "s1", "cliente": "conector", "ref_opaca": ref,
                                             "id_empresa": "e", "estado": "pendiente", "creada_en": e.reloj() - 300})
            return (await c.get(f"/v1/casos/{ref}/sugerencia", headers=h)).json()
    g = run(f())
    assert g["estado"] == "revision_manual" and g["motivo_revision"] == "tiempo_agotado" and g["articulos"] == []


@pytest.mark.pr("PR-16")
def test_feedback_idempotente_por_id_nota():
    e = armar()

    async def f():
        g, ref = await procesar_caso(e)
        sug = g["articulos"][0]["id_sugerencia"]
        async with cliente_http(e.app) as c:
            h = await cabeceras(c)
            cuerpo = {"id_nota": "n1", "id_sugerencia": sug, "valoracion": "arriba", "observacion": "útil"}
            r1 = await c.post(f"/v1/casos/{ref}/feedback", json=cuerpo, headers=h)
            r2 = await c.post(f"/v1/casos/{ref}/feedback", json=cuerpo, headers=h)
            r3 = await c.post(f"/v1/casos/{ref}/feedback", json={**cuerpo, "id_sugerencia": "nada"}, headers=h)
            r4 = await c.post(f"/v1/casos/{uuid.uuid4()}/feedback", json=cuerpo, headers=h)
            return r1, r2, r3, r4
    r1, r2, r3, r4 = run(f())
    assert (r1.status_code, r2.status_code, r3.status_code, r4.status_code) == (201, 200, 404, 404)
    assert len(e.almacen.valoraciones) == 1


@pytest.mark.pr("PR-16")
def test_clasificacion_idempotente_y_resultado_derivado():
    casos = {
        "aceptada": ([("ley21643_art1", "sugerido"), ("cdt_art2", "sugerido")]),
        "corregida": ([("ley21643_art1", "sugerido"), ("otro_art", "agregado_por_auditor")]),
        "rechazada": ([("otro_art", "agregado_por_auditor")]),
    }
    for esperado, arts in casos.items():
        e = armar()

        async def f():
            g, ref = await procesar_caso(e)
            assert {a["id_articulo"] for a in g["articulos"]} == {"ley21643_art1", "cdt_art2"}
            async with cliente_http(e.app) as c:
                h = await cabeceras(c)
                cuerpo = {"id_nota": "c1", "articulos": [{"id_articulo": i, "origen": o} for i, o in arts]}
                r1 = await c.post(f"/v1/casos/{ref}/clasificacion", json=cuerpo, headers=h)
                r2 = await c.post(f"/v1/casos/{ref}/clasificacion", json=cuerpo, headers=h)
                r3 = await c.post(f"/v1/casos/{ref}/clasificacion", json={**cuerpo, "articulos": []}, headers=h)
                return r1, r2, r3
        r1, r2, r3 = run(f())
        assert r1.status_code == 201 and r1.json() == {"resultado": esperado}
        assert r2.status_code == 200 and r2.json() == {"resultado": esperado}
        assert r3.json() == {"resultado": esperado} and len(e.almacen.clasificaciones) == 1
