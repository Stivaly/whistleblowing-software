#!/usr/bin/env python3
"""Contraste WCAG 2.2 de las 3 direcciones de identidad (paletas.json). Misma fórmula que ../calcular_contraste.py.
Uso: python3 calcular_contraste_v2.py [--verificar]   (con --verificar falla si algo no cumple o la maqueta usa otros colores)
Criterios: texto/fondo >=4,5 (1.4.3); acento/fondo >=3 y borde(acento o fondo)/página >=3 (1.4.11); elementos fijos con su mínimo."""
import json, pathlib, sys
AQUI = pathlib.Path(__file__).parent
def lum(h):
    h = h.lstrip("#"); c = [int(h[i:i+2], 16)/255 for i in (0, 2, 4)]
    c = [x/12.92 if x <= 0.03928 else ((x+0.055)/1.055)**2.4 for x in c]
    return 0.2126*c[0]+0.7152*c[1]+0.0722*c[2]
def razon(a, b):
    x, y = sorted((lum(a), lum(b)), reverse=True); return (x+0.05)/(y+0.05)
P = json.loads((AQUI/"paletas.json").read_text()); mal = []; out = []
for k, d in P.items():
    out.append(f"\n### Dirección {k}: {d['nombre']} (página/panel `{d['pagina']}`)\n\n| Estado | Fondo | Texto | Acento | Texto/fondo (>=4,5) | Acento/fondo (>=3) | Borde/página (>=3) |\n|---|---|---|---|---|---|---|")
    for e, (f, t, a) in d["estados"].items():
        # estados rellenos (valorada, sin-conexión sobre página clara): el borde es el propio fondo; el resto, el acento
        borde = f if e == "valorada" or (e == "sin-conexion" and k != "B") else a
        r1, r2, r3 = razon(t, f), razon(a, f), razon(borde, d["pagina"])
        out.append(f"| `{e}` | `{f}` | `{t}` | `{a}` | {r1:.2f} | {r2:.2f} | {r3:.2f} |")
        for n, r, m in (("texto/fondo", r1, 4.5), ("acento/fondo", r2, 3), ("borde/página", r3, 3)):
            if r < m: mal.append((k, e, n, round(r, 2)))
    out.append("\n| Elemento fijo | Primer plano | Fondo | Razón | Mínimo |\n|---|---|---|---|---|")
    for n, fg, bg, m in d["fijos"]:
        r = razon(fg, bg); out.append(f"| {n} | `{fg}` | `{bg}` | {r:.2f} | {m} |")
        if r < m: mal.append((k, n, "fijo", round(r, 2)))
print("\n".join(out))
if "--verificar" in sys.argv:
    html = (AQUI/"maqueta/maqueta.html").read_text().upper()
    for k, d in P.items():
        for e, cols in d["estados"].items():
            for h in cols:
                if h.upper() not in html: mal.append((k, e, f"maqueta no usa {h}", 0))
    if mal: print("\nFALLAS:", mal); sys.exit(1)
    print("\nTodo cumple.")
