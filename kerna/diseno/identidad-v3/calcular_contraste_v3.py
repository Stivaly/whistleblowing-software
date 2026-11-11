#!/usr/bin/env python3
"""Contraste WCAG 2.2 de los dos conceptos (paletas.json). Misma fórmula que ../calcular_contraste.py.
Texto/fondo >=4,5; acento/fondo >=3 (gráficos 1.4.11); tinta de ilustración/fondo >=3; elementos fijos con su mínimo.
Uso: python3 calcular_contraste_v3.py   (sale con error si algo no cumple)"""
import json, pathlib, sys
def lum(h):
    h=h.lstrip("#"); c=[int(h[i:i+2],16)/255 for i in (0,2,4)]
    c=[x/12.92 if x<=0.03928 else ((x+0.055)/1.055)**2.4 for x in c]; return .2126*c[0]+.7152*c[1]+.0722*c[2]
def r(a,b):
    x,y=sorted((lum(a),lum(b)),reverse=True); return (x+.05)/(y+.05)
P=json.loads((pathlib.Path(__file__).parent/"paletas.json").read_text()); mal=[]
for k,d in P.items():
    print(f"\n### Concepto {k}: {d['nombre']}\n\n| Estado | Fondo | Texto | Acento | Texto/fondo (4,5) | Acento/fondo (3) | Tinta/fondo (3) | Texto/panel (4,5)* |\n|---|---|---|---|---|---|---|---|")
    for t,(f,x,a) in d["tonos"].items():
        oscuro = (t in("gris","fin") if k=="A" else False)
        tinta = ("#FFFFFF" if oscuro else "#1E1B2E") if k=="A" else (x if t!="fin" else "#0B1020")
        v=[r(x,f),r(a,f),r(tinta,f)]
        # *en B el acento del chip también se lee sobre el panel oscuro (rombo y borde)
        pan=r(a,d["panel"]) if k=="B" and t!="fin" else None
        print(f"| {t} | {f} | {x} | {a} | {v[0]:.2f} | {v[1]:.2f} | {v[2]:.2f} | {('%.2f'%pan) if pan else '-'} |")
        for n,val,m in (("texto/fondo",v[0],4.5),("acento/fondo",v[1],3),("tinta/fondo",v[2],3)):
            if val<m: mal.append((k,t,n,round(val,2)))
        if pan and pan<3: mal.append((k,t,"acento/panel",round(pan,2)))
    print("\n| Elemento fijo | Primer plano | Fondo | Razón | Mínimo |\n|---|---|---|---|---|")
    for n,fg,bg,m in d["fijos"]:
        v=r(fg,bg); print(f"| {n} | {fg} | {bg} | {v:.2f} | {m} |")
        if v<m: mal.append((k,n,round(v,2)))
print("\nFALLAS:",mal if mal else "ninguna"); sys.exit(1 if mal else 0)
