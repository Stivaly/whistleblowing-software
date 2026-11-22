#!/usr/bin/env python3
"""Ajustes con cambios sin guardar (barra fija visible): captura la parte baja a 390 y 1366 px y mide que la barra no tape la última fila.
Uso: playwright.sh script capturar_ajustes_sucio.py [prefijo]   Salida: salida/<prefijo>ajustes-sucio-<navegador>-<ancho>.png   Cambia el valor SOLO en pantalla: no guarda."""
import os, sys
from playwright.sync_api import sync_playwright
B = os.environ["FRONT_URL"].rstrip("/"); C = os.environ["FRONT_CLAVE"]; PREF = sys.argv[1] if len(sys.argv) > 1 else ""
fallos = []
with sync_playwright() as p:
    for nom in ("chromium", "firefox"):
        nav = getattr(p, nom).launch()
        for w in (390, 1366):
            ctx = nav.new_context(viewport={"width": w, "height": 800 if w < 600 else 850}, has_touch=w < 600); pg = ctx.new_page()
            pg.goto(B + "/acceso"); pg.fill("input[name=usuario]", "admin"); pg.fill("input[name=clave]", C); pg.click("button[type=submit]"); pg.wait_for_load_state("networkidle")
            pg.goto(B + "/panel/ajustes"); pg.wait_for_load_state("networkidle"); pg.wait_for_timeout(800)
            pg.locator("[data-ajuste] .seg button, .seg button").first.click(); pg.wait_for_timeout(600)
            pg.evaluate("scrollTo(0, document.documentElement.scrollHeight)"); pg.wait_for_timeout(500)
            r = pg.evaluate("""() => { const b = document.querySelector('[data-barra]').getBoundingClientRect();
              const f = [...document.querySelectorAll('#app section')].pop().getBoundingClientRect();
              const bs = [...document.querySelectorAll('[data-barra] button')].map(e => { const r = e.getBoundingClientRect(), t = e.querySelector('span') || e, rr = document.createRange(); rr.selectNodeContents(e); const q = rr.getBoundingClientRect(); return [Math.round(r.left), Math.round(r.width), Math.round((q.left + q.width / 2) - (r.left + r.width / 2))]; });
              return { barraTop: Math.round(b.top), baseSeccion: Math.round(f.bottom), alto: innerHeight, botones: bs, vis: !document.querySelector('[data-barra]').hidden }; }""")
            print(nom, w, r)
            if not r["vis"]: fallos.append(f"{nom}@{w}: la barra no aparece")
            elif r["baseSeccion"] > r["barraTop"]: fallos.append(f"{nom}@{w}: la barra tapa la última sección ({r['baseSeccion']} > {r['barraTop']})")
            for x in r["botones"]:
                if abs(x[2]) > 6: fallos.append(f"{nom}@{w}: texto de botón descentrado {x}")
            pg.screenshot(path=f"/out/{PREF}ajustes-sucio-{nom}-{w}.png")
            ctx.close()
        nav.close()
print("FALLOS:" if fallos else "OK", *fallos, sep="\n")
sys.exit(1 if fallos else 0)
