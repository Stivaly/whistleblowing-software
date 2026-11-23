import asyncio
from playwright.async_api import async_playwright

JS = "Array.from(document.querySelectorAll('input,textarea,select,button')).filter(e=>e.offsetParent).map(e=>e.tagName+'|'+(e.type||'')+'|'+(e.id||e.name||'')+'|'+((e.innerText||e.placeholder||'').trim().slice(0,60))).join('\\n')"


async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        pg = await b.new_page(viewport={"width": 1366, "height": 900}, locale="es-CL")
        await pg.goto("http://localhost:8401/#/")
        await pg.wait_for_timeout(3000)
        await pg.click("#WhistleblowingButton")
        for i in range(6):
            await pg.wait_for_timeout(2500)
            await pg.screenshot(path=f"/out/d_{i}.png", full_page=True)
            print(f"===== paso {i}")
            print(await pg.evaluate("document.querySelector('#main, main, body').innerText.slice(0,2000)"))
            print("--")
            print(await pg.evaluate(JS))
            sig = pg.locator("button:has-text('Siguiente'), button:has-text('Continuar'), button:has-text('Proceder')")
            if await sig.count() == 0:
                break
            await sig.first.click()
        await b.close()

asyncio.run(main())
