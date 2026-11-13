#!/usr/bin/env python3
"""Prueba de íconos y logos con navegador real (Chromium, Firefox y WebKit del contenedor Playwright (--nav=chromium,firefox para elegir)). Lanzador: probar_iconos.sh.
Recorre la portada y cada vista del panel (Resumen, Negocio, Ajustes, Informe y sus pestañas, Datos) a 390, 1366 y 1920 px
y FALLA (código 1) si un ícono o logo ocupa espacio pero no se ve. Revisa, por elemento visible:
  - <svg>: cada <use href> va a un símbolo de la propia página (los sprites externos fallan en Firefox) y apunta a un símbolo que existe en su sprite, con dibujo dentro y viewBox;
  - <img>: cargó (naturalWidth > 0), sin opacity 0;
  - background-image con url(): la imagen cargó;
  - píxeles: la captura del elemento no es plana (todos los píxeles iguales = vacío) con el fondo decorativo fijo oculto.
Uso (desde la raíz del repo):  kerna/operaciones/probar_iconos.sh [anchos...]      o directo: playwright.sh script probar_iconos.py [anchos...]
Entorno: FRONT_URL, FRONT_CLAVE (las pone playwright.sh). Capturas de lo que falle: kerna/operaciones/salida/iconos-*.png"""
import base64, json, os, sys
from playwright.sync_api import sync_playwright

BASE = os.environ["FRONT_URL"].rstrip("/"); CLAVE = os.environ["FRONT_CLAVE"]
SALIDA = "/out" if os.path.isdir("/out") else "."
ARGS = sys.argv[1:]
NAVEGADORES = [a.split("=")[1].split(",") for a in ARGS if a.startswith("--nav=")]
NAVEGADORES = NAVEGADORES[0] if NAVEGADORES else ["chromium", "firefox", "webkit"]
ANCHOS = [int(a) for a in ARGS if a.isdigit()] or [390, 1366, 1920]
PESTANAS = ["calidad", "desempeno", "costo", "rentabilidad", "incidentes", "datos"]
VISTAS = [("portada", "/", None, False), ("resumen", "/panel", None, True), ("negocio", "/panel/negocio", None, True),
          ("ajustes", "/panel/ajustes", None, True), ("informe", "/panel/informe", "informe", True)]

# Estructural: recoge los candidatos con su rectángulo y los problemas que se ven sin pintar.
JS_CAND = r"""async () => {
  const cache = {}, out = [];
  const sprite = async (u) => { if (!(u in cache)) { cache[u] = fetch(u).then(r => r.ok ? r.text() : null).then(t => t && new DOMParser().parseFromString(t, 'image/svg+xml')).catch(() => null); } return cache[u]; };
  const visible = (e) => { const r = e.getBoundingClientRect(); if (r.width < 1 || r.height < 1) return null;
    for (let p = e; p && p !== document.documentElement; p = p.parentElement) { const s = getComputedStyle(p); if (s.display === 'none' || s.visibility === 'hidden') return null; }
    const d = e.closest('details:not([open])'); if (d && !(e.closest('summary') && e.closest('summary').parentElement === d)) return null;
    if (e.closest('.ping')) return null;   // pulso animado: nace y se apaga a propósito
    return r; };
  const op = (e) => { let o = 1; for (let p = e; p && p !== document.documentElement; p = p.parentElement) o *= parseFloat(getComputedStyle(p).opacity); return o; };
  const nombre = (e) => e.tagName.toLowerCase() + (e.id ? '#' + e.id : '') + (typeof e.className === 'string' && e.className.trim() ? '.' + e.className.trim().split(/\s+/).slice(0, 3).join('.') : '');
  let n = 0;
  const marcar = (e, tipo, prob) => { const r = visible(e); if (!r) return; const id = 'ic' + (n++); e.setAttribute('data-ic', id);
    out.push({ id, tipo, nom: nombre(e), x: r.left + scrollX, y: r.top + scrollY, w: r.width, h: r.height, op: op(e), prob }); };
  for (const e of document.querySelectorAll('svg')) {
    if (e.closest('#__echarts, [_echarts_instance_]')) continue;   // gráficos ECharts: se miden por píxeles abajo
    const prob = [];
    for (const u of e.querySelectorAll('use')) {
      const h = u.getAttribute('href') || u.getAttribute('xlink:href') || ''; const [url, id] = h.split('#');
      if (!id) { prob.push('use sin id: ' + h); continue; }
      let doc = document; if (url) { prob.push('sprite externo (Firefox no lo resuelve siempre; el símbolo va dentro de la página): ' + h); doc = await sprite(new URL(url, location.href).href); if (!doc) { prob.push('sprite no carga: ' + url); continue; } }
      const sym = doc.getElementById(id);
      if (!sym) prob.push('símbolo inexistente: ' + h);
      else { if (!sym.querySelector('path,circle,rect,line,polyline,polygon,ellipse,use,g,image,text')) prob.push('símbolo vacío: ' + h);
             if (sym.tagName.toLowerCase() === 'symbol' && !sym.getAttribute('viewBox')) prob.push('símbolo sin viewBox: ' + h); }
    }
    if (!e.querySelector('use') && !e.getAttribute('viewBox') && !(e.getAttribute('width') && e.getAttribute('height'))) prob.push('svg sin viewBox');
    marcar(e, 'svg', prob);
  }
  for (const e of document.querySelectorAll('img')) { const prob = []; if (!e.complete || e.naturalWidth === 0) prob.push('imagen no carga: ' + (e.currentSrc || e.src)); marcar(e, 'img', prob); }
  for (const e of document.querySelectorAll('body *')) {
    const bg = getComputedStyle(e).backgroundImage; const m = bg && bg.match(/url\(["']?([^"')]+)["']?\)/g); if (!m) continue;
    const r = e.getBoundingClientRect(); if (r.width * r.height > 500 * 500) continue;   // texturas de página: no son íconos
    const prob = [];
    for (const u of m) { const url = u.replace(/url\(["']?|["']?\)/g, ''); if (url.startsWith('data:')) continue;
      const ok = await new Promise(res => { const i = new Image(); i.onload = () => res(i.naturalWidth > 0); i.onerror = () => res(false); i.src = url; }); if (!ok) prob.push('background-image no carga: ' + url); }
    marcar(e, 'bg', prob);
  }
  return out; }"""

# Píxeles: decodifica la captura de página completa y mide, por rectángulo, cuántos colores distintos hay.
JS_PIX = r"""async ([b64, rects, esc]) => {
  const bm = await createImageBitmap(await (await fetch('data:image/png;base64,' + b64)).blob());
  const c = document.createElement('canvas'); c.width = bm.width; c.height = bm.height; const g = c.getContext('2d', { willReadFrequently: true }); g.drawImage(bm, 0, 0);
  return rects.map(r => { const x = Math.max(0, Math.floor(r.x * esc)), y = Math.max(0, Math.floor(r.y * esc)), w = Math.min(bm.width - x, Math.ceil(r.w * esc)), h = Math.min(bm.height - y, Math.ceil(r.h * esc));
    if (w < 1 || h < 1) return { fuera: true };
    const d = g.getImageData(x, y, w, h).data; const p0 = [d[0], d[1], d[2]]; let dif = 0;
    for (let i = 0; i < d.length; i += 4) if (Math.abs(d[i] - p0[0]) + Math.abs(d[i + 1] - p0[1]) + Math.abs(d[i + 2] - p0[2]) > 12) dif++;
    return { dif, tot: w * h }; }); }"""

CSS_QUIETO = "html,body{scroll-behavior:auto!important}.bgfx{display:none!important}nav.tabbar{position:static!important}"


ANCHO_ACTUAL = [0]


def revisar(pg, pg_aux, etiqueta):
    """Devuelve la lista de fallos de la vista actual."""
    pg.add_style_tag(content=CSS_QUIETO)
    pg.evaluate("document.querySelectorAll('details:not(.otro)').forEach(d => d.open = true)")   # los plegables cerrados esconden íconos: se abren para revisarlos
    pg.evaluate("async()=>{for(let y=0;y<document.documentElement.scrollHeight;y+=500){scrollTo(0,y);await new Promise(r=>setTimeout(r,120))}scrollTo(0,0)}")
    pg.wait_for_timeout(1500)   # termina las animaciones de entrada
    cands = pg.evaluate(JS_CAND)
    png = pg.screenshot(full_page=True)
    pix = pg_aux.evaluate(JS_PIX, [base64.b64encode(png).decode(), cands, 1])
    fallos = []
    for c, p in zip(cands, pix):
        motivos = list(c["prob"])
        if c["op"] < 0.05: motivos.append(f"opacity efectiva {c['op']:.2f}")
        if c["w"] < 2 or c["h"] < 2: motivos.append(f"tamaño {c['w']:.0f}x{c['h']:.0f}")
        if p.get("fuera"):
            if c["x"] < ANCHO_ACTUAL[0]: motivos.append("fuera de la captura")   # a la derecha del viewport = dentro de una fila que se desplaza: no se evalúa
        elif p["dif"] < max(3, p["tot"] * 0.002): motivos.append(f"sin píxeles propios ({p['dif']}/{p['tot']} distintos del fondo)")
        if motivos: fallos.append({"vista": etiqueta, "elemento": c["nom"], "tipo": c["tipo"], "caja": [round(c[k]) for k in "xywh"], "motivos": motivos})
    return len(cands), fallos


def main():
    total, todos = 0, []
    with sync_playwright() as p:
      for nombre_nav in NAVEGADORES:
        nav = getattr(p, nombre_nav).launch(); aux = nav.new_context().new_page(); aux.goto("about:blank")
        for w in ANCHOS:
            ANCHO_ACTUAL[0] = w
            ctx = nav.new_context(viewport={"width": w, "height": 850 if w > 600 else 800}, **({"is_mobile": w < 600} if nombre_nav != "firefox" else {}), has_touch=w < 600); pg = ctx.new_page()
            pg.goto(BASE + "/acceso"); pg.fill("input[name=clave]", CLAVE); pg.click("button[type=submit]"); pg.wait_for_load_state("networkidle")
            assert "/panel" in pg.url, f"el login no entró al panel ({pg.url})"
            for nom, ruta, tabs, _ in VISTAS:
                pg.goto(BASE + ruta, wait_until="load"); pg.wait_for_load_state("networkidle"); pg.wait_for_timeout(1000)
                hay = [(nom, None)] + ([(f"{nom}-{t}", t) for t in PESTANAS] if tabs else [])
                for et, tab in hay:
                    if tab:
                        pg.evaluate("t => document.getElementById('t-'+t)?.click()", tab); pg.wait_for_timeout(1500)
                    n, f = revisar(pg, aux, f"{nombre_nav[:2]}:{et}@{w}")
                    total += n; todos += f
                    print(f"{nombre_nav[:2]}:{et + '@' + str(w):28} {n:4} íconos/logos revisados, {len(f)} con falla", flush=True)
                    if f: pg.screenshot(path=f"{SALIDA}/iconos-{nombre_nav}-{et}-{w}.png", full_page=True)
            ctx.close()
        nav.close()
    json.dump(todos, open(f"{SALIDA}/iconos-fallos.json", "w"), ensure_ascii=False, indent=1)
    print(f"\n{total} elementos revisados, {len(todos)} fallos")
    for f in todos: print(" -", f["vista"], f["tipo"], f["elemento"], f["caja"], "; ".join(f["motivos"]))
    sys.exit(1 if todos else 0)


main()
