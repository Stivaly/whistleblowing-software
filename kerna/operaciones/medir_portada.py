"""Captura la portada a 390, 1366 y 1920 px y mide: scroll horizontal, ancho máximo del contenido y huecos verticales > 16 px entre bloques hermanos.
Uso: playwright.sh script kerna/operaciones/medir_portada.py [prefijo]   (capturas en kerna/operaciones/salida/)"""
import os, sys, json
from playwright.sync_api import sync_playwright
URL = os.environ["FRONT_URL"]; PREF = sys.argv[1] if len(sys.argv) > 1 else "portada-"
JS = """() => {
  const de = document.documentElement, r = {sw: de.scrollWidth, cw: de.clientWidth, h: de.scrollHeight, huecos: [], ancho: 0};
  const m = document.querySelector('main') || document.body;
  for (const sec of m.children) { const b = sec.getBoundingClientRect(); r.ancho = Math.max(r.ancho, Math.round(b.width)); }
  const hs = [...m.children].filter(e => e.getBoundingClientRect().height > 0);
  for (let i = 1; i < hs.length; i++) { const a = hs[i-1].getBoundingClientRect(), b = hs[i].getBoundingClientRect(); const g = Math.round(b.top - a.bottom); if (g > 16) r.huecos.push([hs[i-1].className.slice(0,30), hs[i].className.slice(0,30), g]); }
  return r; }"""
with sync_playwright() as p:
    nav = p.chromium.launch()
    for nom, w, h in (("m", 390, 844), ("d", 1366, 850), ("d1920", 1920, 1000)):
        pag = nav.new_page(viewport={"width": w, "height": h}); pag.goto(URL + "/", wait_until="networkidle"); pag.wait_for_timeout(1500)
        print(nom, json.dumps(pag.evaluate(JS), ensure_ascii=False))
        pag.screenshot(path="/out/%s%s.png" % (PREF, nom), full_page=True); pag.close()
    nav.close()
