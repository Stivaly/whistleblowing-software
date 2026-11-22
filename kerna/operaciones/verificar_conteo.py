#!/usr/bin/env python3
"""Descarga Informe en PDF/Excel/CSV (30 días) y guarda el texto del Resumen y del Informe para comparar cifras; luego captura Resumen e Informe
a 390, 1366 y 1920 px en Chromium y Firefox como prod15-conteo-<vista>-<navegador>-<ancho>.png. Se ejecuta con playwright.sh script; salida en /out."""
import os, re
from playwright.sync_api import sync_playwright

URL, CLAVE = os.environ["FRONT_URL"], os.environ["FRONT_CLAVE"]
VISTAS = {"resumen": "/panel", "informe": "/panel/informe?dias=30"}
with sync_playwright() as p:
    for nombre in ("chromium", "firefox"):
        nav = getattr(p, nombre).launch()
        for ancho in (390, 1366, 1920):
            ctx = nav.new_context(viewport={"width": ancho, "height": 900}); pg = ctx.new_page()
            pg.goto(URL + "/acceso"); pg.fill("input[name=usuario]", "admin"); pg.fill("input[name=clave]", CLAVE); pg.click("button[type=submit]"); pg.wait_for_load_state("networkidle")
            if nombre == "chromium" and ancho == 1366:
                for ext in ("pdf", "xlsx", "csv"):
                    r = ctx.request.get(f"{URL}/panel/informe/descargar.{ext}?dias=30", timeout=120000)
                    open(f"/out/informe30.{ext}", "wb").write(r.body()); print("descarga", ext, r.status, len(r.body()))
            for v, ruta in VISTAS.items():
                pg.goto(URL + ruta, wait_until="load"); pg.wait_for_load_state("networkidle"); pg.wait_for_timeout(4000)
                pg.screenshot(path=f"/out/prod15-conteo-{v}-{nombre}-{ancho}.png", full_page=True)
                if nombre == "chromium" and ancho == 1366:
                    open(f"/out/texto-{v}.txt", "w").write(pg.inner_text("body"))
                print(v, nombre, ancho, "desborde" if pg.evaluate("document.documentElement.scrollWidth > innerWidth") else "ok")
            ctx.close()
        nav.close()
