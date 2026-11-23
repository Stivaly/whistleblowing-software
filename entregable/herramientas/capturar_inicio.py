"""Captura de la página de inicio (manuales de instalación y de usuario)."""
import asyncio

from playwright.async_api import async_playwright

from capturas_comun import capturar, marcar


async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        pg = await b.new_page(viewport={"width": 1366, "height": 900}, locale="es-CL")
        await pg.goto("http://localhost:8400/")
        await pg.wait_for_timeout(9000)
        await marcar(pg, "#aviso", 1)
        await marcar(pg, ".estados", 2)
        await marcar(pg, "text=Hacer una denuncia en Veridy", 3)
        await marcar(pg, ".tarjeta.veridy >> nth=1 >> .clave", 4)
        await marcar(pg, "text=Entrar a Veridy como auditor", 5)
        await marcar(pg, ".tarjeta.kerna >> .clave", 6)
        await marcar(pg, "text=Entrar al panel de Kerna", 7)
        await marcar(pg, ".pie .tarjeta >> nth=0", 8)
        await capturar(pg, "i01_inicio", completa=True)
        await b.close()

asyncio.run(main())
