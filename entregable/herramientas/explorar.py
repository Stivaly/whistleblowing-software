import asyncio
import sys
from playwright.async_api import async_playwright

JS_CAMPOS = "Array.from(document.querySelectorAll('input,textarea,select,button,a')).map(e=>e.tagName+'|'+(e.type||'')+'|'+(e.id||e.name||'')+'|'+((e.innerText||e.placeholder||'').trim().slice(0,60))).join('\\n')"


async def main(url, nombre):
    async with async_playwright() as p:
        b = await p.chromium.launch()
        pg = await b.new_page(viewport={"width": 1366, "height": 900}, locale="es-CL")
        await pg.goto(url)
        await pg.wait_for_timeout(5000)
        await pg.screenshot(path=f"/out/x_{nombre}.png", full_page=True)
        print(await pg.evaluate("document.body.innerText.slice(0,2500)"))
        print("----")
        print(await pg.evaluate(JS_CAMPOS))
        await b.close()

asyncio.run(main(sys.argv[1], sys.argv[2]))
