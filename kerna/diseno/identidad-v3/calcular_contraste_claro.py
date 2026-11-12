#!/usr/bin/env python3
"""Contraste WCAG 2.2 del tema claro de Kerna: lee los acentos por estado de client/app/css/components/kerna.css.
Sobre blanco: acento >=4,5 (se usa también como texto y trazo), tinta/secundario >=4,5, borde de control >=3 (1.4.11),
lima solo como relleno: tinta oscura sobre lima >=4,5 y borde oscuro sobre blanco >=3. Sale con error si algo no cumple."""
import pathlib, re, sys
CSS = pathlib.Path(__file__).resolve().parents[3] / "client/app/css/components/kerna.css"
def lum(h):
    h = h.lstrip("#"); c = [int(h[i:i+2], 16)/255 for i in (0, 2, 4)]
    c = [x/12.92 if x <= .03928 else ((x+.055)/1.055)**2.4 for x in c]; return .2126*c[0]+.7152*c[1]+.0722*c[2]
def r(a, b):
    x, y = sorted((lum(a), lum(b)), reverse=True); return (x+.05)/(y+.05)
s = CSS.read_text(); B = "#ffffff"; mal = []
def fila(n, a, b, m):
    v = r(a, b); print(f"| {n} | {a} | {b} | {v:.2f} | {m} |")
    if v < m: mal.append((n, round(v, 2)))
print("| Elemento | Primer plano | Fondo | Razón | Mínimo |\n|---|---|---|---|---|")
v = lambda k: re.search(rf"--{k}: (#[0-9a-f]{{6}})", s).group(1)
fila("acento base", v("acc"), B, 4.5)
for est, c in re.findall(r'data-estado="([a-z-]+)"\] \{ --acc: (#[0-9a-f]{6})', s): fila(f"acento {est}", c, B, 4.5)
for k, m in (("txt", 4.5), ("k-sec", 4.5), ("k-borde", 3), ("k-verde", 4.5), ("k-verde-txt", 4.5)): fila(k, v(k), B, m)
fila("tinta sobre lima (botón, voto, marca)", v("k-tinta"), v("k-lima"), 4.5)
fila("borde tinta sobre lima (relleno lima)", v("k-tinta"), v("k-lima"), 3)
fila("lima sobre blanco (solo relleno, no se evalúa como texto)", v("k-lima"), B, 1)
print("\nFALLAS:", mal if mal else "ninguna"); sys.exit(1 if mal else 0)
