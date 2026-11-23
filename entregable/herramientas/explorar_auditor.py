import asyncio
import os

from playwright.async_api import async_playwright

V = "http://localhost:8401"
JS = "Array.from(document.querySelectorAll('input,textarea,select,button,a')).filter(e=>e.offsetParent).map(e=>e.tagName+'|'+(e.id||'')+'|'+((e.innerText||e.placeholder||e.title||'').trim().replace(/\\s+/g,' ').slice(0,70))).join('\\n')"


async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        pg = await b.new_page(viewport={"width": 1366, "height": 900}, locale="es-CL")
        await pg.goto(V + "/#/login")
        await pg.wait_for_timeout(3000)
        await pg.screenshot(path="/out/a_login.png")
        print(await pg.evaluate(JS))
        await pg.fill("input[name=username]", "auditor.prueba")
        await pg.fill("input[name=password]", os.environ["VERIDY_AUDITOR_CLAVE"])
        await pg.click("#login-button, button[type=submit]")
        await pg.wait_for_timeout(8000)
        print("URL", pg.url)
        await pg.screenshot(path="/out/a_inicio.png", full_page=True)
        print(await pg.evaluate("document.body.innerText.slice(0,1500)"))
        print(await pg.evaluate(JS))
        await pg.goto(V + "/#/recipient/reports")
        await pg.wait_for_timeout(4000)
        await pg.screenshot(path="/out/a_lista.png", full_page=True)
        print("=== LISTA"); print(await pg.evaluate("document.body.innerText.slice(0,2000)")); print(await pg.evaluate(JS))
        fila = pg.locator("#tipList tr, tbody tr").first
        await fila.click()
        await pg.wait_for_timeout(6000)
        print("URL", pg.url)
        await pg.screenshot(path="/out/a_caso.png", full_page=True)
        print("=== CASO"); print(await pg.evaluate("document.body.innerText.slice(0,4000)")); print(await pg.evaluate(JS))
        ind = pg.locator("#kerna-indicador")
        print("indicador:", await ind.count())
        if await ind.count():
            await ind.hover(); await pg.wait_for_timeout(800)
            await pg.screenshot(path="/out/a_tooltip.png")
            await ind.click(); await pg.wait_for_timeout(1500)
            await pg.screenshot(path="/out/a_panel.png", full_page=True)
            print(await pg.locator("#kerna-panel").inner_text())
        await b.close()

asyncio.run(main())
