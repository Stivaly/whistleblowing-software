"""Capturas del auditor en Veridy (manual de usuario, parte 2): bandeja, caso, bloque de Kerna y todos sus estados.
Los estados que no se pueden provocar a voluntad (modo alternativo, Kerna no disponible, etc.) se muestran con el bloque
real, cambiando solo la respuesta que recibe el navegador. Al final hace una valoración y una clasificación reales.
Uso: pw.sh capturar_auditor.py <id del caso con sugerencia> [--solo-estados]
"""
import asyncio
import copy
import json
import os
import sys
from datetime import datetime, timedelta, timezone

from playwright.async_api import async_playwright

from capturas_comun import capturar, marcar

V = "http://localhost:8401"
CASO = sys.argv[1]


def iso(delta_min=0):
    return (datetime.now(timezone.utc) + timedelta(minutes=delta_min)).strftime("%Y-%m-%dT%H:%M:%SZ")


def transformar(tip, estado):
    """Reescribe las notas de Kerna del caso para mostrar `estado`."""
    notas, otros = [], []
    for c in tip.get("comments", []):
        try:
            o = json.loads(c.get("content", ""))
            (notas if isinstance(o, dict) and str(o.get("tipo", "")).startswith("kerna_") else otros).append((c, o))
        except ValueError:
            otros.append((c, None))
    sug = next(((c, o) for c, o in notas if o["tipo"] == "kerna_sugerencia"), None)
    est = next(((c, o) for c, o in notas if o["tipo"] == "kerna_estado"), None)
    nuevos = []

    def poner(par, cambios):
        c, o = copy.deepcopy(par[0]), dict(par[1])
        o.update(cambios)
        c["content"] = json.dumps(o, ensure_ascii=False)
        nuevos.append(c)

    if estado == "generando":
        poner(est, {"estado": "en_proceso", "fecha": iso(-1)})
    elif estado == "en-proceso-viejo":
        poner(est, {"estado": "en_proceso", "fecha": iso(-30)})
    elif estado == "nucleo-no-disponible":
        poner(est, {"estado": "nucleo_no_disponible", "fecha": iso(-1)})
    elif estado in ("sin-nota", "sin-info"):
        pass
    elif estado == "modo":
        poner(sug, {"modo": "respaldo", "contingencia": True})
    elif estado == "busqueda":
        poner(sug, {"recuperacion": "local"})
    else:
        motivo = {"revision-tiempo": "tiempo_agotado", "revision-citas": "validacion_fallida",
                  "sin-normativa": "sin_normativa_aplicable", "cadena-agotada": "cadena_agotada"}[estado]
        poner(sug, {"estado": "revision_manual", "motivo_revision": motivo, "articulos": []})
    tip["comments"] = [c for c, _ in otros] + nuevos
    if estado == "sin-info":
        tip["creation_date"] = iso(-3 * 24 * 60)
    elif estado == "sin-nota":
        tip["creation_date"] = iso(-20)
    return tip


async def entrar(pg):
    await pg.goto(V + "/#/login")
    await pg.wait_for_timeout(2500)
    await pg.fill("input[name=username]", "auditor.prueba")
    await pg.fill("input[name=password]", os.environ["VERIDY_AUDITOR_CLAVE"])
    await pg.click("#login-button")
    await pg.wait_for_timeout(7000)


async def abrir_caso(pg):
    await pg.goto(V + "/#/reports/" + CASO)
    await pg.wait_for_timeout(5000)


async def estados(b):
    lista = ["generando", "modo", "busqueda", "revision-tiempo", "revision-citas", "sin-normativa", "cadena-agotada",
             "nucleo-no-disponible", "sin-nota", "en-proceso-viejo", "sin-info"]
    for e in lista:
        ctx = await b.new_context(viewport={"width": 1366, "height": 1000}, locale="es-CL")
        pg = await ctx.new_page()
        await entrar(pg)

        async def ruta(route, _peticion=None, e=e):
            r = await route.fetch()
            try:
                datos = transformar(await r.json(), e)
            except Exception as exc:
                print("   sin cambio:", e, type(exc).__name__, exc)
                return await route.fulfill(response=r)
            cab = {k: v for k, v in r.headers.items() if k.lower() not in ("content-length", "content-encoding")}
            await route.fulfill(status=r.status, body=json.dumps(datos), headers={**cab, "content-type": "application/json"})
        await pg.route(lambda u, c=CASO: u.split("?")[0].endswith("/api/recipient/rtips/" + c), ruta)
        await abrir_caso(pg)
        await pg.click("#kerna-indicador")
        await pg.mouse.move(1300, 990)
        await pg.wait_for_timeout(1200)
        await capturar(pg, f"e_{e}", recorte=["#kerna-indicador", "#kerna-panel"])
        await ctx.close()

    # Sin conexión: se corta la red del navegador con el caso abierto
    ctx = await b.new_context(viewport={"width": 1366, "height": 1000}, locale="es-CL")
    pg = await ctx.new_page()
    await entrar(pg)
    await abrir_caso(pg)
    await pg.click("#kerna-indicador")
    await pg.mouse.move(1300, 990)
    await ctx.set_offline(True)
    await pg.wait_for_timeout(1500)
    await marcar(pg, "[data-cy=kerna-reintentar]", 1)
    await capturar(pg, "e_sin-conexion", recorte=["#kerna-indicador", "#kerna-panel .kerna-aviso"])
    await ctx.set_offline(False)
    await ctx.close()


async def recorrido(b):
    ctx = await b.new_context(viewport={"width": 1366, "height": 1000}, locale="es-CL")
    pg = await ctx.new_page()
    await pg.goto(V + "/#/login")
    await pg.wait_for_timeout(2500)
    await pg.fill("input[name=username]", "auditor.prueba")
    await pg.fill("input[name=password]", os.environ["VERIDY_AUDITOR_CLAVE"])
    await marcar(pg, "input[name=username]", 1)
    await marcar(pg, "input[name=password]", 2)
    await marcar(pg, "#login-button", 3)
    await capturar(pg, "a01_login")
    await pg.click("#login-button")
    await pg.wait_for_timeout(7000)
    await marcar(pg, "#recipient_reports", 1)
    await capturar(pg, "a02_principal")
    await pg.click("#recipient_reports")
    await pg.wait_for_timeout(4000)
    await marcar(pg, "tbody tr >> nth=0", 1)
    await marcar(pg, "#search-input-field", 2)
    await capturar(pg, "a03_bandeja")

    await abrir_caso(pg)
    await marcar(pg, "#kerna-indicador", 1)
    await marcar(pg, "#link-reload", 2)
    await marcar(pg, "#link-tiplist", 3)
    await capturar(pg, "a04_caso")
    await pg.hover("#kerna-indicador")
    await pg.wait_for_timeout(800)
    await capturar(pg, "a05_tooltip", recorte=["#kerna-indicador", "[data-cy=kerna-tooltip]"])
    await pg.mouse.move(900, 900)
    await pg.click("#kerna-indicador")
    await pg.wait_for_timeout(1500)
    await marcar(pg, ".kerna-panel-cabecera", 1)
    await marcar(pg, ".kerna-hero", 2)
    await marcar(pg, "[data-cy=kerna-aviso-permanente]", 3)
    await capturar(pg, "a06_panel_cabecera", recorte=[".kerna-panel-cabecera", "[data-cy=kerna-aviso-permanente]"])
    await capturar(pg, "a07_panel_completo", recorte="#kerna-panel")

    art = pg.locator("[data-cy=kerna-articulo]").first
    await marcar(pg, art.locator(".kerna-articulo-titulo"), 1)
    await marcar(pg, art.locator(".kerna-anillo"), 2, izquierda=True)
    await marcar(pg, art.locator(".kerna-casilla"), 3)
    await marcar(pg, art.locator(".kerna-explicacion"), 4)
    await marcar(pg, art.locator("[data-cy=kerna-ver-cita]"), 5)
    await marcar(pg, art.locator(".kerna-enlace"), 6)
    await marcar(pg, art.locator(".kerna-valoracion"), 7)
    await capturar(pg, "a08_articulo", recorte=art)

    await art.locator("[data-cy=kerna-ver-cita]").click()
    await pg.wait_for_timeout(600)
    await marcar(pg, art.locator(".kerna-cita"), 1)
    await capturar(pg, "a09_cita", recorte=art)

    await art.locator("[data-cy=kerna-voto-arriba]").click()
    await pg.wait_for_timeout(500)
    await art.locator(".kerna-observacion textarea").fill("Corresponde: la empresa debe investigar y adoptar medidas.")
    await marcar(pg, art.locator("[data-cy=kerna-voto-arriba]"), 1)
    await marcar(pg, art.locator(".kerna-observacion textarea"), 2)
    await marcar(pg, art.locator("[data-cy=kerna-enviar-valoracion]"), 3)
    await capturar(pg, "a10_valorar", recorte=art)
    await art.locator("[data-cy=kerna-enviar-valoracion]").click()
    await pg.wait_for_timeout(2500)
    await marcar(pg, art.locator(".kerna-ok"), 1)
    await capturar(pg, "a11_valoracion_enviada", recorte=art)

    arts = pg.locator("[data-cy=kerna-articulo]")
    for i in (0, 1):
        await arts.nth(i).locator(".kerna-casilla input").check()
    await pg.fill("#kerna-otro", "Código del Trabajo, artículo 2")
    await pg.click(".kerna-agregar button")
    await pg.fill("#kerna-obs-clasificacion", "Se abre investigación interna en el plazo legal.")
    await marcar(pg, arts.nth(0).locator(".kerna-casilla"), 1)
    await marcar(pg, arts.nth(1).locator(".kerna-casilla"), 1)
    await capturar(pg, "a12_incluir", recorte=[arts.nth(0), arts.nth(1)])
    await marcar(pg, ".kerna-agregar", 1)
    await marcar(pg, "#kerna-obs-clasificacion", 2)
    await marcar(pg, "[data-cy=kerna-guardar-clasificacion]", 3)
    await marcar(pg, "[data-cy=kerna-ninguno]", 4)
    await marcar(pg, ".kerna-pie", 5)
    await capturar(pg, "a13_clasificar", recorte=".kerna-clasificacion, .kerna-pie")
    await capturar(pg, "a13b_clasificar", recorte=[".kerna-clasificacion", ".kerna-pie"])
    await pg.click("[data-cy=kerna-guardar-clasificacion]")
    await pg.mouse.move(1300, 990)
    await pg.wait_for_timeout(4000)
    await marcar(pg, "#kerna-indicador", 1)
    await marcar(pg, ".kerna-panel-cabecera", 2)
    await capturar(pg, "a14_guardada", recorte=["#kerna-indicador", ".kerna-hero", "[data-cy=kerna-aviso-permanente]"])
    await ctx.close()


async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        await estados(b)
        if "--solo-estados" not in sys.argv:
            await recorrido(b)
        await b.close()

asyncio.run(main())
