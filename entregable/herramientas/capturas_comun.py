"""Ayudas para las capturas del manual: recuadros numerados sobre la pantalla real y capturas con nombre."""
import os

COLOR = "#E5262A"

JS_MARCAR = """([caja, n, color, texto, izquierda]) => {
  const d = document.createElement('div');
  d.className = '__marca';
  const x = caja.x + window.scrollX - 6, y = caja.y + window.scrollY - 6;
  Object.assign(d.style, {position:'absolute', left:x+'px', top:y+'px', width:(caja.width+12)+'px', height:(caja.height+12)+'px',
    border:'4px solid '+color, borderRadius:'10px', zIndex:2147483646, pointerEvents:'none', boxSizing:'border-box',
    boxShadow:'0 0 0 3px rgba(255,255,255,.85)'});
  document.body.appendChild(d);
  if (n) {
    const b = document.createElement('div');
    b.className = '__marca';
    b.textContent = n;
    const ancho = document.documentElement.clientWidth;
    const izq = izquierda ? Math.max(x - 20, 2) : Math.min(x + caja.width - 8, ancho - 40);
    Object.assign(b.style, {position:'absolute', left:izq+'px', top:Math.max(y - 22, 2)+'px', width:'36px', height:'36px', borderRadius:'50%',
      background:color, color:'#fff', font:'700 20px/36px Arial, sans-serif', textAlign:'center', zIndex:2147483647,
      pointerEvents:'none', boxShadow:'0 0 0 3px #fff'});
    document.body.appendChild(b);
  }
  if (texto) {
    const t = document.createElement('div');
    t.className = '__marca';
    t.textContent = texto;
    Object.assign(t.style, {position:'absolute', left:(x)+'px', top:(y+caja.height+18)+'px', maxWidth:'380px', padding:'6px 10px',
      background:color, color:'#fff', font:'600 15px/1.3 Arial, sans-serif', borderRadius:'6px', zIndex:2147483647, pointerEvents:'none'});
    document.body.appendChild(t);
  }
}"""


async def marcar(pg, objetivo, n=None, texto=None, color=COLOR, izquierda=False):
    """Dibuja un recuadro (y un número) sobre un selector o locator. Devuelve False si no está visible."""
    loc = pg.locator(objetivo).first if isinstance(objetivo, str) else objetivo
    try:
        await loc.scroll_into_view_if_needed(timeout=3000)
        caja = await loc.bounding_box()
    except Exception:
        caja = None
    if not caja:
        print("   (sin recuadro: no visible)", objetivo if isinstance(objetivo, str) else "locator")
        return False
    await pg.evaluate(JS_MARCAR, [caja, str(n) if n else "", color, texto or "", izquierda])
    return True


async def limpiar(pg):
    await pg.evaluate("document.querySelectorAll('.__marca').forEach(e => e.remove())")


async def capturar(pg, nombre, completa=False, recorte=None):
    """Guarda /out/<nombre>.png y quita los recuadros. recorte = locator/selector para capturar solo esa zona (con margen)."""
    ruta = os.path.join("/out", nombre + ".png")
    if recorte is not None:
        cajas = []
        for r in (recorte if isinstance(recorte, (list, tuple)) else [recorte]):
            loc = pg.locator(r).first if isinstance(r, str) else r
            cajas.append(await loc.bounding_box())
        sx, sy = await pg.evaluate("[window.scrollX, window.scrollY]")
        ancho = await pg.evaluate("document.documentElement.scrollWidth")
        x0 = max(min(c["x"] for c in cajas) + sx - 40, 0)
        y0 = max(min(c["y"] for c in cajas) + sy - 50, 0)
        x1 = min(max(c["x"] + c["width"] for c in cajas) + sx + 70, ancho)
        y1 = max(c["y"] + c["height"] for c in cajas) + sy + 60
        await pg.screenshot(path=ruta, full_page=True, clip={"x": x0, "y": y0, "width": x1 - x0, "height": y1 - y0})
    else:
        await pg.screenshot(path=ruta, full_page=completa)
    await limpiar(pg)
    print("captura", nombre)
