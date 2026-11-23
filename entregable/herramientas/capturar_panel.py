"""Capturas del panel de Kerna (manual de usuario, parte 3). Los recuadros se dibujan después con anotar.py."""
import asyncio
import os

from playwright.async_api import async_playwright

K = "http://localhost:8402"


async def foto(pg, nombre, completa=True):
    await pg.screenshot(path=f"/out/{nombre}.png", full_page=completa)
    print("captura", nombre)


async def ir(pg, ruta, espera=9000):
    await pg.goto(K + ruta, timeout=120000)
    await pg.wait_for_timeout(espera)


async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        pg = await b.new_page(viewport={"width": 1366, "height": 900}, locale="es-CL")
        await ir(pg, "/", 4000)
        await foto(pg, "k00_portada", completa=False)
        await ir(pg, "/acceso", 2000)
        await pg.fill("input[name=usuario]", "evaluador.prueba")
        await pg.fill("input[name=clave]", os.environ["KERNA_PANEL_CLAVE"])
        await foto(pg, "k01_acceso", completa=False)
        await pg.locator("button:has-text('Entrar')").click(no_wait_after=True)
        await pg.wait_for_url("**/panel**", timeout=120000)
        await pg.wait_for_timeout(9000)
        await foto(pg, "k02_resumen")
        ayuda = pg.locator("text=SUGERENCIAS ACERTADAS").locator("xpath=..").locator("button, [role=button], .ayuda, summary").first
        try:
            await pg.get_by_text("Sugerencias acertadas", exact=False).first.locator("xpath=following::*[contains(@class,'ayuda') or self::button][1]").click(timeout=4000)
            await pg.wait_for_timeout(800)
            await foto(pg, "k03_ayuda", completa=False)
            await pg.keyboard.press("Escape")
        except Exception as exc:
            print("sin ayuda", type(exc).__name__)
        await ir(pg, "/panel/informe")
        await foto(pg, "k04_informe")
        for i, pest in enumerate(("Rapidez", "Costos", "Rentabilidad", "Incidentes", "Datos")):
            try:
                await pg.get_by_role("tab", name=pest).click(timeout=4000)
            except Exception:
                await pg.get_by_text(pest, exact=True).first.click()
            await pg.wait_for_timeout(1500)
            await foto(pg, f"k05_informe_{i + 1}_{pest.lower()}")
        await ir(pg, "/panel/negocio")
        await foto(pg, "k06_negocio")
        await ir(pg, "/panel/clientes")
        await foto(pg, "k07_clientes")
        await ir(pg, "/panel/ajustes")
        await foto(pg, "k08_ajustes")
        await ir(pg, "/panel/cuentas", 15000)
        await foto(pg, "k09_cuentas")
        await ir(pg, "/panel/demo")
        await foto(pg, "k10_demo", completa=False)
        await pg.get_by_text("Acoso en la oficina", exact=True).click()
        await pg.wait_for_timeout(800)
        await pg.get_by_role("button", name="Anonimizar").click()
        await pg.wait_for_timeout(6000)
        await foto(pg, "k10_demo_anon")
        print(await pg.evaluate("document.querySelector('main')?.innerText.slice(0,2500)"))
        await pg.get_by_text("Denuncias", exact=True).last.click()
        await pg.wait_for_timeout(3000)
        await foto(pg, "k10_demo_denuncias")
        print("== DENUNCIAS")
        print(await pg.evaluate("document.querySelector('main')?.innerText.slice(0,2500)"))
        await ir(pg, "/cuenta", 4000)
        await foto(pg, "k11_cuenta")
        await b.close()

asyncio.run(main())
