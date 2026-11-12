#!/usr/bin/env python3
"""Mide y captura las vistas del panel en producción (Playwright, se ejecuta en la imagen oficial: ver medir_vistas.sh).
Para cada vista y ancho: alto de página, desborde horizontal (scrollWidth > clientWidth) y los elementos que más sobresalen; TTFB, peso y CPU en reposo.
Uso: medir_vistas.py <url_base> <clave> <prefijo_capturas|-> <salida.json> [anchos...]"""
import json, sys, time
from playwright.sync_api import sync_playwright
base, clave, pref, salida = sys.argv[1:5]
anchos = [int(a) for a in sys.argv[5:]] or [1366, 390]
VISTAS = [("resumen", "/panel", None), ("informe", "/panel/informe", "informe"), ("negocio", "/panel/negocio", None), ("ajustes", "/panel/ajustes", None)]
PESTANAS = ["calidad", "desempeno", "costo", "rentabilidad", "incidentes", "datos"]
JS_DESB = """() => { let st=document.getElementById("__ov"); if(!st){st=document.createElement("style");st.id="__ov";st.textContent="html,body{overflow-x:visible!important}.bgfx{display:none!important}";document.head.appendChild(st)} const de=document.documentElement, cw=de.clientWidth; const out=[];
 for (const e of document.querySelectorAll('body *')) { const r=e.getBoundingClientRect(); if (r.width && r.right>cw+1) { let p=e, oculto=false; while((p=p.parentElement)&&p!==document.body){const s=getComputedStyle(p); if(['auto','scroll','hidden','clip'].includes(s.overflowX)&&p.getBoundingClientRect().right<=cw+1){oculto=true;break}} if(!oculto) out.push([e.tagName.toLowerCase()+(e.id?'#'+e.id:'')+(e.className&&typeof e.className==='string'?'.'+e.className.trim().split(/\\s+/).slice(0,3).join('.'):''), Math.round(r.right), Math.round(r.width)]); } }
 out.sort((a,b)=>b[1]-a[1]); return {sw:de.scrollWidth, cw, h:de.scrollHeight, top:out.slice(0,6)}; }"""
res = {}
with sync_playwright() as p:
    nav = p.chromium.launch()
    for w in anchos:
        ctx = nav.new_context(viewport={"width": w, "height": 850 if w > 600 else 800}, device_scale_factor=1, is_mobile=w < 600, has_touch=w < 600)
        pg = ctx.new_page()
        pg.goto(base + "/acceso"); pg.fill("input[name=clave]", clave); pg.click("button[type=submit]"); pg.wait_for_load_state("networkidle")
        for nom, ruta, tabs in VISTAS:
            t0 = time.time(); pg.goto(base + ruta, wait_until="load"); pg.wait_for_load_state("networkidle"); pg.wait_for_timeout(1500)
            nav_t = pg.evaluate("() => { const n=performance.getEntriesByType('navigation')[0]; return {ttfb:Math.round(n.responseStart), kb:Math.round(performance.getEntriesByType('resource').reduce((a,e)=>a+e.transferSize,0)/1024+n.transferSize/1024)} }")
            hay = [(nom, None)] + ([(f"{nom}-{t}", t) for t in PESTANAS] if tabs else [])
            for clave_v, tab in hay:
                if tab:
                    pg.evaluate("t => document.getElementById('t-'+t)?.click()", tab); pg.wait_for_timeout(1200)
                pg.evaluate("async()=>{for(let y=0;y<document.documentElement.scrollHeight;y+=500){scrollTo(0,y);await new Promise(r=>setTimeout(r,120))}scrollTo(0,0)}"); pg.wait_for_timeout(600)  # activa los gráficos perezosos
                d = pg.evaluate(JS_DESB); d.update(nav_t if tab is None else {})
                res[f"{clave_v}@{w}"] = d
                if pref != "-":
                    pg.evaluate("() => { if (!document.getElementById('__cap')) { const s = document.createElement('style'); s.id = '__cap'; s.textContent = 'nav.tabbar{position:static!important}'; document.head.appendChild(s) } }")  # la barra inferior fija no tapa el contenido en la captura de página completa
                    pg.screenshot(path=f"{pref}{clave_v}-{'m' if w < 600 else 'd'}{'' if w in (390, 1366) else w}.png", full_page=True)
                    pg.evaluate("() => document.getElementById('__cap')?.remove()")
        ctx.close()
    nav.close()
json.dump(res, open(salida, "w"), ensure_ascii=False, indent=1)
for k, v in res.items():
    print(f"{k:28} h={v['h']:5} sw={v['sw']} cw={v['cw']} {'DESBORDA ' + str(v['top'][:2]) if v['sw'] > v['cw'] else ''} {v.get('ttfb','')} {v.get('kb','')}")
