import asyncio
import os

from playwright.async_api import async_playwright

K = "http://localhost:8402"
PAGINAS = ["/panel", "/panel/informe", "/panel/negocio", "/panel/clientes", "/panel/ajustes", "/panel/reintentar",
           "/panel/cuentas", "/panel/demo", "/cuenta"]


async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        pg = await b.new_page(viewport={"width": 1366, "height": 900}, locale="es-CL")
        await pg.goto(K + "/acceso")
        await pg.wait_for_timeout(2000)
        await pg.screenshot(path="/out/k_acceso.png")
        print(await pg.evaluate("Array.from(document.querySelectorAll('input,button')).map(e=>e.tagName+'|'+e.name+'|'+e.id+'|'+e.innerText).join('\\n')"))
        await pg.fill("input[name=usuario]", "evaluador.prueba")
        await pg.fill("input[name=clave]", os.environ["KERNA_PANEL_CLAVE"])
        await pg.locator("button:has-text('Entrar')").click(no_wait_after=True)
        await pg.wait_for_url("**/panel**", timeout=90000)
        await pg.wait_for_timeout(5000)
        for r in PAGINAS:
            await pg.goto(K + r)
            await pg.wait_for_timeout(9000)
            n = r.strip("/").replace("/", "_")
            await pg.screenshot(path=f"/out/k_{n}.png", full_page=True)
            print("=====", r, pg.url)
            print(await pg.evaluate("document.body.innerText.slice(0,3500)"))
        await b.close()

asyncio.run(main())
