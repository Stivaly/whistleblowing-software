#!/usr/bin/env python3
"""Sprite de íconos de estado de la identidad Núcleo (kerna/diseno/identidad-v3/svg/B-*.svg) y sus colores.

Genera app/estaticos/estados.svg (un <g> por ícono (se recorta con viewBox="26 6 108 108" en el svg que lo usa), sin animación) y reemplaza en app/estaticos/kerna.css el bloque
entre /* ESTADOS-INICIO */ y /* ESTADOS-FIN */ con los tonos de la paleta B. Comprueba el contraste (WCAG AA) de los colores derivados.
Uso: python3 kerna/front/herramientas/construir_iconos_estado.py"""
import json, re, sys
from pathlib import Path
AQUI = Path(__file__).resolve().parent
RAIZ = AQUI.parents[1]
SVG = RAIZ / "diseno/identidad-v3/svg"
PAL = json.loads((RAIZ / "diseno/identidad-v3/paletas.json").read_text())["B"]["tonos"]
EST = AQUI.parent / "app/estaticos"
# ícono -> tono de la paleta B
ICONOS = {"lista": "verde", "generando": "azul", "contingencia-modelo": "ambar", "contingencia-busqueda": "ambar", "revision-citas": "violeta",
          "revision-tiempo": "naranja", "cadena-agotada": "rojo", "nucleo-no-disponible": "magenta", "sin-info": "neutro", "sin-conexion": "gris",
          "sin-normativa": "cian", "conector-en-proceso": "arena", "conector-sin-nota": "arena", "valorada": "fin"}


def rgb(h): h = h.lstrip("#"); return [int(h[i:i + 2], 16) for i in (0, 2, 4)]
def hexa(c): return "#%02X%02X%02X" % tuple(round(x) for x in c)
def mezcla(a, b, t): return hexa([x * (1 - t) + y * t for x, y in zip(rgb(a), rgb(b))])
def lum(h):
    c = [x / 255 for x in rgb(h)]; c = [x / 12.92 if x <= .03928 else ((x + .055) / 1.055) ** 2.4 for x in c]; return .2126 * c[0] + .7152 * c[1] + .0722 * c[2]
def razon(a, b): x, y = sorted((lum(a), lum(b)), reverse=True); return (x + .05) / (y + .05)


# Clases de las escenas -> estilo en línea (el contenido de un <use> externo no recibe el CSS de la página; las variables sí se heredan)
BASE = "fill:none;stroke-linecap:round;stroke-linejoin:round;"
CLASES = {"o": BASE + "stroke:var(--pi);stroke-width:3", "o2": BASE + "stroke:var(--pi);stroke-width:2", "of": BASE + "stroke:var(--pi);stroke-width:3;fill:var(--pf)",
          "oz": BASE + "stroke:var(--pi);stroke-width:2;stroke-dasharray:4 4", "th": BASE + "stroke:var(--acc);stroke-width:4", "th2": BASE + "stroke:var(--acc);stroke-width:2.5",
          "thz": BASE + "stroke:var(--acc);stroke-width:3;stroke-dasharray:2 6", "err": BASE + "stroke:var(--acc);stroke-width:3", "fa": "fill:var(--acc)", "fi": "fill:var(--pi)",
          "chk": BASE + "stroke:var(--pf);stroke-width:3", "chk2": BASE + "stroke:var(--pf);stroke-width:4", "chk3": BASE + "stroke:var(--pf);stroke-width:7",
          "puntada": BASE + "stroke:var(--acc);stroke-width:3.2", "puntada vac": BASE + "stroke:var(--pi);stroke-width:1.6;stroke-dasharray:1.5 3;opacity:.7",
          "seg": BASE + "stroke:var(--acc);stroke-width:3.4;stroke-linecap:butt", "seg vac": BASE + "stroke:var(--pi);stroke-width:2;opacity:.35;stroke-linecap:butt;fill:none"}


def estilizar(cuerpo):
    def etiqueta(m):
        t = m.group(0)
        nombre = re.match(r"<(\w+)", t).group(1)
        attrs = dict(re.findall(r'([\w:-]+)="([^"]*)"', t))  # sin atributos repetidos (algunas escenas repiten cx; vale el último)
        t = f"<{nombre} " + " ".join(f'{k}="{v}"' for k, v in attrs.items()) + ">" if not t.endswith("/>") else f"<{nombre} " + " ".join(f'{k}="{v}"' for k, v in attrs.items()) + "/>"
        c = re.search(r'\bclass="([^"]+)"', t)
        if not c:
            return t
        k = " ".join(c.group(1).split())
        if k not in CLASES:
            raise SystemExit("clase sin estilo en línea: " + k)
        t = t.replace(c.group(0), "").replace("  ", " ")
        st = re.search(r'\bstyle="([^"]*)"', t)
        if st:
            return t.replace(st.group(0), f'style="{CLASES[k]};{st.group(1)}"')
        return re.sub(r"^<(\w+)", lambda x: f'<{x.group(1)} style="{CLASES[k]}"', t)
    return re.sub(r"<\w+ [^>]*>", etiqueta, cuerpo)


def sprite():
    out = ['<svg xmlns="http://www.w3.org/2000/svg" style="display:none">']
    for n in ICONOS:
        t = (SVG / f"B-{n}.svg").read_text()
        cuerpo = t.split("</style>", 1)[1].rsplit("</svg>", 1)[0]
        cuerpo = re.sub(r'<circle class="ping"[^>]*/>', "", cuerpo)  # estático: sin las animaciones de la escena original
        cuerpo = re.sub(r'<g class="spin[^"]*"[^>]*>(.*?)</g>', r"\1", cuerpo)
        cuerpo = re.sub(r'<g class="(?:late|chispa|blink|radar)"[^>]*>', "<g>", cuerpo)
        cuerpo = re.sub(r' (?:late|blink)"', '"', cuerpo)
        cuerpo = estilizar(re.sub(r"(\d+\.\d)\d+", r"\1", cuerpo).replace(" />", "/>"))
        out.append(f'<g id="e-{n}">{cuerpo}</g>')  # <g> (no <symbol>): el recorte 26 6 108 108 lo pone el viewBox del svg que lo usa
    out.append("</svg>")
    (EST / "estados.svg").write_text("\n".join(out) + "\n")


def css():
    r = ["/* ESTADOS-INICIO (generado por herramientas/construir_iconos_estado.py; paleta Núcleo, identidad v3) */",
         "k-st{display:inline-grid;place-items:center;flex:none;width:var(--s,1.5em);height:var(--s,1.5em);border-radius:22%;background:var(--fondo);vertical-align:middle;overflow:hidden}",
         "k-st svg{display:block;width:100%;height:100%;overflow:visible}"]
    for n, t in ICONOS.items():
        f, x, a = PAL[t]
        pf = f if t == "fin" else "#0B1020"
        pi = "#0B1020" if t == "fin" else x
        if t == "fin": f, a, pf = "#CFFF5E", "#0B1020", "#CFFF5E"
        r.append(f'k-st[data-e="{n}"]{{--fondo:{f};--acc:{a};--pi:{pi};--pf:{pf}}}')
    # estados semánticos en superficies claras: texto = acento muy oscurecido hacia el fondo del tono; barra = mezcla acento/fondo; tinte = acento sobre blanco
    r.append(":root{")
    mal = []
    for e, t in (("ok", "verde"), ("warn", "ambar"), ("bad", "rojo"), ("na", "neutro"), ("pro", "azul")):
        f, x, a = PAL[t]
        barra, tinte, tx = mezcla(a, f, .5), mezcla(a, "#FFFFFF", .86), mezcla(a, f, .68)
        r.append(f"--{e}:{tx};--{e}-bar:{barra};--{e}-bg:{tinte};--{e}-ac:{a};")
        for nombre, v, m in (("texto/tinte", razon(tx, tinte), 4.5), ("texto/blanco", razon(tx, "#FFFFFF"), 4.5), ("barra/blanco", razon(barra, "#FFFFFF"), 3.0)):
            print(f"{e:5} {t:8} {nombre:13} {v:5.2f} (mín {m})")
            if v < m: mal.append((e, nombre, round(v, 2)))
    r.append("}")
    r.append("/* ESTADOS-FIN */")
    return "\n".join(r), mal


if __name__ == "__main__":
    sprite()
    bloque, mal = css()
    p = EST / "kerna.css"; s = p.read_text()
    if "/* ESTADOS-INICIO" in s:
        s = re.sub(r"/\* ESTADOS-INICIO.*?/\* ESTADOS-FIN \*/", lambda m: bloque, s, flags=re.S)
    else:
        s += "\n" + bloque + "\n"
    p.write_text(s)
    print("FALLAS:", mal or "ninguna"); sys.exit(1 if mal else 0)
