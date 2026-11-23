"""Envía una denuncia real en el Veridy local y captura cada paso con recuadros (manual de usuario, parte 1).
Uso: pw.sh capturar_denuncia.py <caso>   (caso = acoso | datos | vago). Guarda el código de seguimiento en /out/codigo_<caso>.txt
"""
import asyncio
import re
import sys

from playwright.async_api import async_playwright

from capturas_comun import capturar, marcar

V = "http://localhost:8401"
CASOS = {
    "acoso": {
        "tipo": "Acoso laboral", "nombres": "Rodrigo", "apellidos": "Valenzuela", "relacion": "Empleado",
        "pais": "Chile", "region": "Región Metropolitana", "comuna": "Providencia", "area": "Área de Contabilidad",
        "relato": ("Desde marzo de este año mi jefe directo, el señor Rodrigo Valenzuela, jefe del área de contabilidad, me grita "
                   "delante de mis compañeros, me dice que soy una inútil y que si no me gusta me vaya. En las reuniones de los lunes "
                   "me deja fuera a propósito y me asigna tareas imposibles de cumplir con plazos de un día para el otro, y después "
                   "me reprocha frente a todos que no las terminé. Hace dos semanas me dijo que me iba a hacer la vida imposible hasta "
                   "que renuncie. Le escribí a recursos humanos por correo y nadie me ha respondido. Tengo licencia médica por estrés "
                   "desde el 3 de noviembre y temo que me despidan al volver. Dos compañeras, Daniela Soto y Francisca Muñoz, han "
                   "visto lo que pasa y también han recibido gritos."),
        "evidencia": "No tengo evidencias, pero podría obtenerlas y suministrarlas", "compartir": "No",
    },
    "datos": {
        "tipo": "Uso indebido de información", "nombres": "No sé su nombre", "apellidos": "Supervisor de la sucursal centro", "relacion": "Empleado",
        "pais": "Chile", "region": "Valparaíso", "comuna": "Viña del Mar", "area": "Sucursal centro",
        "relato": ("Soy cliente de la empresa. El 10 de octubre recibí en mi WhatsApp publicidad de una financiera que conocía mi RUT "
                   "12.345.678-5, mi dirección y el monto de mi deuda con la empresa. Al reclamar, un ejecutivo de la sucursal centro "
                   "me reconoció que un supervisor vende planillas con datos de clientes a terceros y que eso pasa hace meses. Nunca "
                   "autoricé que mis datos se compartieran. Cuando pedí que borraran mis datos, me dijeron que no era posible y no me "
                   "dieron ningún comprobante."),
        "evidencia": "No tengo evidencias, pero podría obtenerlas y suministrarlas", "compartir": "No",
    },
    "vago": {
        "tipo": "Fraude", "nombres": "No sé", "apellidos": "No sé", "relacion": "Otro",
        "pais": "Chile", "region": "Biobío", "comuna": "Concepción", "area": "No sé",
        "relato": "Creo que algo raro pasa en la empresa, pero no sé bien qué es. Solo quería avisar.",
        "evidencia": "No me es posible proporcionar evidencias de ningún tipo", "compartir": "No",
    },
}


def selects(pg):
    """Listas desplegables del formulario (sin el selector de idioma)."""
    return pg.locator("ng-select:visible").filter(has_not=pg.locator("#language-picker-select"))


def nativos(pg):
    return pg.locator("select.form-control:visible")


async def elegir(pg, n_select, opcion):
    """Lista con buscador (10 opciones o más)."""
    await selects(pg).nth(n_select).click()
    await pg.locator(".ng-dropdown-panel .ng-option", has_text=opcion).first.click()


async def elegir_nativo(pg, n, opcion):
    """Lista simple (menos de 10 opciones)."""
    sel = nativos(pg).nth(n)
    valor = await sel.evaluate("(s, t) => (Array.from(s.options).find(o => o.text.trim().startsWith(t)) || {}).value", opcion)
    await sel.select_option(value=valor)


async def siguiente(pg):
    await pg.locator("#NextStepButton").click()
    await pg.wait_for_timeout(1200)


async def main(caso, con_capturas):
    d = CASOS[caso]
    pre = f"v_{caso}_"
    async with async_playwright() as p:
        b = await p.chromium.launch()
        pg = await b.new_page(viewport={"width": 1366, "height": 900}, locale="es-CL")
        await pg.goto(V + "/#/")
        await pg.wait_for_timeout(3500)
        if con_capturas:
            await marcar(pg, "#WhistleblowingButton", 1)
            await capturar(pg, pre + "01_portada")
        await pg.click("#WhistleblowingButton")
        await pg.wait_for_timeout(2500)

        # Paso 1: tipo
        if con_capturas:
            await marcar(pg, selects(pg).first, 1)
            await capturar(pg, pre + "02_tipo")
        await elegir(pg, 0, d["tipo"])
        if con_capturas:
            await marcar(pg, selects(pg).first, 1)
            await marcar(pg, "#NextStepButton", 2)
            await capturar(pg, pre + "03_tipo_elegido")
        await siguiente(pg)

        # Paso 2: quién denuncia
        campos = pg.locator("input[type=text]:visible:not(#language-picker-select):not(.ng-select input)")
        await campos.nth(0).fill(d["nombres"])
        await campos.nth(1).fill(d["apellidos"])
        await elegir_nativo(pg, 0, d["relacion"])
        if con_capturas:
            await marcar(pg, campos.nth(0), 1)
            await marcar(pg, campos.nth(1), 2)
            await marcar(pg, nativos(pg).first, 3)
            await marcar(pg, "#NextStepButton", 4)
            await capturar(pg, pre + "04_persona")
        await siguiente(pg)

        # Paso 3: dónde y cuándo
        campos = pg.locator("input[type=text]:visible:not(#language-picker-select):not(.ng-select input)")
        print("campos paso 3:", await campos.count())
        for i, k in enumerate(("pais", "region", "comuna", "area")):
            await campos.nth(i).fill(d[k])
        fecha = campos.nth(4)
        fecha_fin = campos.nth(5)
        for entrada, n in ((fecha, 3), (fecha_fin, 10)):
            await entrada.click()
            await pg.wait_for_timeout(500)
            await pg.locator("ngb-datepicker [role=gridcell]:not(.disabled)").filter(has_text=re.compile(rf"^\s*{n}\s*$")).first.click()
            await pg.wait_for_timeout(300)
        await pg.keyboard.press("Escape")
        await pg.wait_for_timeout(400)
        if con_capturas:
            for i in range(4):
                await marcar(pg, campos.nth(i), i + 1)
            await marcar(pg, fecha, 5)
            await marcar(pg, fecha_fin, 6)
            await marcar(pg, "#NextStepButton", 7)
            await capturar(pg, pre + "05_lugar_fecha")
        await siguiente(pg)

        # Paso 4: relato y evidencia
        await pg.locator("textarea:visible").first.fill(d["relato"])
        await elegir_nativo(pg, 0, d["evidencia"])
        await pg.wait_for_timeout(500)
        extra = pg.locator("input[type=text]:visible:not(#language-picker-select):not(.ng-select input)")
        if await extra.count():
            await extra.first.fill("Puedo entregarla en una reunión presencial.")
        if con_capturas:
            await marcar(pg, "textarea:visible", 1)
            await marcar(pg, nativos(pg).first, 2)
            await marcar(pg, "#NextStepButton", 3)
            await capturar(pg, pre + "06_relato", completa=True)
        await siguiente(pg)

        # Paso 5: datos de contacto
        await elegir_nativo(pg, 0, d["compartir"])
        await pg.wait_for_timeout(400)
        print(await pg.evaluate("document.querySelector('main, body').innerText.slice(0,1500)"))
        envio = pg.locator("#SubmitButton, button:has-text('Enviar')").first
        if con_capturas:
            await marcar(pg, nativos(pg).first, 1)
            await marcar(pg, envio, 2)
            await capturar(pg, pre + "07_contacto", completa=True)
        await envio.click()
        await pg.wait_for_timeout(6000)

        # Código de seguimiento
        texto = await pg.evaluate("document.body.innerText")
        print(texto[:1500])
        codigo = await pg.locator("#ReceiptCode").input_value()
        print("CODIGO", codigo)
        open(f"/out/codigo_{caso}.txt", "w").write(codigo.strip())
        if con_capturas:
            zona = pg.locator("#ReceiptCode")
            await marcar(pg, zona, 1)
            await marcar(pg, "button:has-text('Ver su denuncia')", 2)
            await capturar(pg, pre + "08_codigo")
            await pg.click("button:has-text('Ver su denuncia')")
            await pg.wait_for_timeout(4000)
            await capturar(pg, pre + "09_seguimiento", completa=True)
        await b.close()

asyncio.run(main(sys.argv[1], "--sin-capturas" not in sys.argv))
