#!/usr/bin/env python3
"""Verificación real del botón de reintento en producción (solo lectura; el pedido se envía antes con probar_front.sh --reintento).
Espera el estado «en curso» del bloque del Resumen, lo captura a 390 y 1366 px y comprueba botón gris deshabilitado, ícono girando y tooltip;
espera el fin y captura el resultado. Se ejecuta con playwright.sh script; guarda en /out (kerna/operaciones/salida)."""
import json, os, sys, time
from playwright.sync_api import sync_playwright

URL, CLAVE = os.environ["FRONT_URL"], os.environ["FRONT_CLAVE"]
ANCHOS = {"m": 390, "d": 1366}
res = {}
JS_BLOQUE = "() => { const a = document.querySelector('[data-rei-acc]'); return a ? (a.closest('section,.band,.card,article') || a.parentElement) : null }"


def entrar(ctx):
    pg = ctx.new_page()
    pg.goto(URL + "/acceso"); pg.fill("input[name=clave]", CLAVE); pg.click("button[type=submit]"); pg.wait_for_load_state("networkidle")
    return pg


def capturar(nav, clave, fase):
    ctx = nav.new_context(viewport={"width": ANCHOS[clave], "height": 900})
    pg = entrar(ctx)
    pg.goto(URL + "/panel", wait_until="load"); pg.wait_for_load_state("networkidle"); pg.wait_for_timeout(1500)
    el = pg.evaluate_handle(JS_BLOQUE).as_element()
    el.scroll_into_view_if_needed()
    datos = pg.evaluate("""() => { const a = document.querySelector('[data-rei-acc]'); const w = a.querySelector('.rei-w');
      const b = w && w.querySelector('button'); const sp = w && w.querySelector('.rei-sp');
      return {texto: a.innerText.replace(/\\s+/g,' ').trim(), curso: !!w, deshabilitado: b ? b.disabled : null,
        fondo: b ? getComputedStyle(b).backgroundColor : null, color: b ? getComputedStyle(b).color : null,
        gira: sp ? getComputedStyle(sp).animationName : null, tip: w ? w.getAttribute('x') : null,
        ok: (a.querySelector('.rei-ok') || {}).innerText || null, desborde: document.documentElement.scrollWidth > innerWidth} }""")
    el.screenshot(path=f"/out/prod17-reintento-{fase}-{clave}.png")
    res[f"{fase}-{clave}"] = datos
    print(fase, clave, json.dumps(datos, ensure_ascii=False))
    ctx.close()


with sync_playwright() as p:
    nav = p.chromium.launch()
    ctx = nav.new_context(viewport={"width": 1366, "height": 900}); pg = entrar(ctx)
    t0 = time.time(); estado = None
    while time.time() - t0 < 300:  # espera a que el conector tome el pedido
        estado = pg.evaluate("async () => (await fetch('/panel/reintentar/estado', {cache:'no-store'})).json()")
        if estado.get("modo") == "curso":
            break
        time.sleep(5)
    print("estado al empezar:", json.dumps(estado, ensure_ascii=False))
    for c in ANCHOS:
        capturar(nav, c, "curso")
    t0 = time.time()
    while time.time() - t0 < 3000:
        estado = pg.evaluate("async () => (await fetch('/panel/reintentar/estado', {cache:'no-store'})).json()")
        if estado.get("modo") != "curso":
            break
        time.sleep(15)
    print("estado al terminar:", json.dumps(estado, ensure_ascii=False))
    for c in ANCHOS:
        capturar(nav, c, "fin")
    json.dump(res, open("/out/prod17-reintento.json", "w"), ensure_ascii=False, indent=1)
