#!/usr/bin/env python3
"""Prueba de movimiento y reposo en producción (navegador real, solo lectura: no guarda ajustes ni pulsa el reintento).
Ajustes: las capas orbitales giran (transform distinto entre dos instantes), los satélites y el arco cambian con los controles (con transición),
con prefers-reduced-motion no hay animaciones, y la CPU en reposo es < 1 %. Resumen: el botón de reintento existe, «En vivo» muestra la hora del último dato.
Se ejecuta con playwright.sh script (recibe FRONT_URL y FRONT_CLAVE); sale con código 1 si algo falla."""
import json, os, sys
from playwright.sync_api import sync_playwright

URL, CLAVE = os.environ["FRONT_URL"], os.environ["FRONT_CLAVE"]
fallos, res = [], {}


def chequeo(nombre, ok, detalle=""):
    res[nombre] = {"ok": bool(ok), "detalle": detalle}
    print(("OK    " if ok else "FALLA ") + nombre + (" · " + str(detalle) if detalle else ""))
    if not ok:
        fallos.append(nombre)


def cpu_reposo(pg, cdp, seg=6):
    pg.wait_for_timeout(1500)
    a = {m["name"]: m["value"] for m in cdp.send("Performance.getMetrics")["metrics"]}
    pg.wait_for_timeout(seg * 1000)
    b = {m["name"]: m["value"] for m in cdp.send("Performance.getMetrics")["metrics"]}
    return round(100 * (b["TaskDuration"] - a["TaskDuration"]) / (b["Timestamp"] - a["Timestamp"]), 2)


def entrar(ctx):
    pg = ctx.new_page()
    pg.goto(URL + "/acceso"); pg.fill("input[name=usuario]", "admin"); pg.fill("input[name=clave]", CLAVE); pg.click("button[type=submit]"); pg.wait_for_load_state("networkidle")
    return pg


with sync_playwright() as p:
    nav = p.chromium.launch()
    ctx = nav.new_context(viewport={"width": 1366, "height": 850})
    pg = entrar(ctx)
    cdp = ctx.new_cdp_session(pg); cdp.send("Performance.enable")
    pg.goto(URL + "/panel/ajustes", wait_until="load"); pg.wait_for_load_state("networkidle"); pg.wait_for_timeout(1500)
    capas = "[data-orb='proc'] .ap-l1, [data-orb='proc'] .ap-l2, [data-orb='ia'] .ap-l1, [data-orb='plazos'] .ap-l1"
    T = "() => [...document.querySelectorAll(\"" + capas + "\")].map(e => getComputedStyle(e).transform)"
    t0 = pg.evaluate(T); pg.wait_for_timeout(2500); t1 = pg.evaluate(T)
    chequeo("las órbitas giran (transform cambia entre dos instantes)", len(t0) == 4 and all(a != b and a != "none" for a, b in zip(t0, t1)), f"{len(t0)} capas")
    chequeo("la guilloche y el halo giran", pg.evaluate("() => ['::before','::after'].every(s => getComputedStyle(document.querySelector('.ap'), s).animationName !== 'none')"))
    # satélites: mover «Casos por ronda» a 8 y a 2 cambia los ángulos y las opacidades con transición
    S = "() => [...document.querySelectorAll(\"[data-orb='proc'] .ap-l1 .sg\")].map(e => [getComputedStyle(e).opacity, e.style.transform])"
    s0 = pg.evaluate(S)
    pg.evaluate("() => { const r = document.querySelector(\".ctl[data-k='envios'] .range\"); r.value = 2; r.dispatchEvent(new Event('input', {bubbles: true})); }")
    pg.wait_for_timeout(120); medio = pg.evaluate("() => [...document.querySelectorAll(\"[data-orb='proc'] .ap-l1 .sg\")].map(e => getComputedStyle(e).opacity)")
    pg.wait_for_timeout(1200); s1 = pg.evaluate(S)
    chequeo("los satélites se desplazan al mover el control", s0 != s1 and sum(1 for o, _ in s1 if o == "1") == 2 and sum(1 for o, _ in s0 if o == "1") == 5, f"antes {sum(1 for o, _ in s0 if o == '1')} → después {sum(1 for o, _ in s1 if o == '1')}")
    chequeo("el cambio tiene transición (valores intermedios de opacity)", any(m not in ("0", "1") for m in medio), str(medio[:6]))
    A = "() => getComputedStyle(document.querySelector(\"[data-orb='plazos'] .arc\")).strokeDasharray"
    a0 = pg.evaluate(A)
    pg.evaluate("() => { const r = document.querySelector(\".ctl[data-k='maxresp'] .range\"); r.value = 45; r.dispatchEvent(new Event('input', {bubbles: true})); }")
    pg.wait_for_timeout(150); am = pg.evaluate(A); pg.wait_for_timeout(1000); a1 = pg.evaluate(A)
    chequeo("el arco de «Meta de respuesta» se anima", a0 != a1 and am not in (a0, a1), f"{a0} → {am} → {a1}")
    chequeo("el cambio sin guardar muestra la barra de guardado y no guarda solo", pg.evaluate("() => !document.querySelector('[data-barra]').hidden"))
    pg.evaluate("() => document.querySelector('[data-restaurar]').click()")
    # teclado: las flechas mueven el selector segmentado
    pg.focus(".ctl[data-k='espera'] .seg button[aria-checked='true']"); pg.keyboard.press("ArrowRight")
    chequeo("el teclado mueve el selector (flecha derecha)", pg.evaluate("() => document.querySelector(\".ctl[data-k='espera'] .seg button[aria-checked='true']\").textContent.trim()") != "24 h")
    pg.evaluate("() => document.querySelector('[data-descartar]').click()")
    pg.wait_for_timeout(1500)
    res["cpu_reposo_ajustes_%"] = cpu_reposo(pg, cdp)
    chequeo("CPU en reposo en Ajustes < 1 %", res["cpu_reposo_ajustes_%"] < 1, f"{res['cpu_reposo_ajustes_%']} %")
    pg.screenshot(path="/out/movimiento-ajustes.png")
    # Resumen: botón y En vivo
    pg.goto(URL + "/panel", wait_until="load"); pg.wait_for_load_state("networkidle"); pg.wait_for_timeout(1500)
    b = pg.evaluate("() => { const a = document.querySelector('[data-rei-acc]'); return a ? a.innerText.trim().replace(/\\s+/g,' ') : null }")
    chequeo("el botón de reintento está en el Resumen (nunca desaparece)", b is not None and ("Reintentar ahora" in b or "Reintentando" in b), b)
    pg.hover("[data-vivo]"); pg.wait_for_timeout(400)
    tt = pg.inner_text("#tt")
    chequeo("«En vivo» dice la hora del último dato y que puede demorar", "Último dato recibido" in tt and "unos minutos" in tt, tt.replace("\n", " ")[:200])
    st = pg.evaluate("async () => { const r = await fetch('/panel/reintentar/estado'); const j = await r.json(); return [r.status, j.modo, j.fuente] }")
    chequeo("el estado en vivo responde", st[0] == 200, str(st))
    res["cpu_reposo_resumen_%"] = cpu_reposo(pg, cdp)
    chequeo("CPU en reposo en el Resumen < 1 %", res["cpu_reposo_resumen_%"] < 1, f"{res['cpu_reposo_resumen_%']} %")
    ctx.close()
    # prefers-reduced-motion: sin animaciones
    c2 = nav.new_context(viewport={"width": 1366, "height": 850}, reduced_motion="reduce"); g2 = entrar(c2)
    g2.goto(URL + "/panel/ajustes", wait_until="load"); g2.wait_for_timeout(1500)
    chequeo("con prefers-reduced-motion no hay animaciones", g2.evaluate("() => [...document.querySelectorAll('.ap-l1,.ap-l2')].every(e => getComputedStyle(e).animationName === 'none')"))
    c2.close(); nav.close()
json.dump(res, open("/out/movimiento.json", "w"), ensure_ascii=False, indent=1)
print("\nFALLAS:", fallos or "ninguna"); sys.exit(1 if fallos else 0)
