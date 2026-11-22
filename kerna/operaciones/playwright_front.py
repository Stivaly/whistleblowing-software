#!/usr/bin/env python3
"""Pruebas del front con navegador (Playwright). Se ejecuta dentro del contenedor: ver playwright.sh.
Uso: playwright_front.py <pdf|modal> <url_base> <carpeta_salida> [--confirmar]   (la clave llega por FRONT_CLAVE)
  pdf    inicia sesión y descarga el informe en PDF a <carpeta_salida>/informe.pdf
  modal  abre el modal de reintento en /panel, lo captura y lo cancela; con --confirmar lo acepta (pedido real)"""
import os, sys
from playwright.sync_api import sync_playwright

accion, base, salida = sys.argv[1:4]
confirmar = "--confirmar" in sys.argv
with sync_playwright() as p:
    nav = p.chromium.launch(); ctx = nav.new_context(viewport={"width": 1366, "height": 850}, accept_downloads=True); pg = ctx.new_page()
    pg.goto(base + "/acceso"); pg.fill("input[name=usuario]", "admin"); pg.fill("input[name=clave]", os.environ["FRONT_CLAVE"]); pg.click("button[type=submit]"); pg.wait_for_load_state("networkidle")
    assert "/panel" in pg.url, f"el login no entró al panel ({pg.url})"
    if accion == "pdf":
        r = ctx.request.get(base + "/panel/informe/descargar.pdf?dias=7", timeout=90000)
        cuerpo = r.body(); assert r.status == 200 and cuerpo[:4] == b"%PDF", f"descarga inválida: {r.status}"
        open(f"{salida}/informe.pdf", "wb").write(cuerpo); print(f"OK PDF {len(cuerpo)} bytes -> informe.pdf")
    elif accion == "modal":
        enlace = pg.locator("#rei a[data-reintentar]")
        if not enlace.count():
            print("No hay botón de reintento: no hay casos en espera o ya hay un pedido en curso."); pg.screenshot(path=f"{salida}/modal-sin-boton.png", full_page=True)
        else:
            enlace.click(); pg.wait_for_selector("#dlg-rei[open]"); pg.screenshot(path=f"{salida}/modal.png"); print("OK modal abierto -> modal.png")
            if confirmar:
                pg.click("#dlg-rei [data-dlg-ok]"); pg.wait_for_timeout(3000); pg.screenshot(path=f"{salida}/modal-tras-pedido.png")
                print("Pedido enviado:", pg.locator(".cola-av").first.inner_text() if pg.locator(".cola-av").count() else "(sin aviso visible)")
            else:
                pg.click("#dlg-rei button[value=cancelar]"); print("Modal cancelado (no se envió nada).")
    else:
        sys.exit(f"acción desconocida: {accion}")
    nav.close()
