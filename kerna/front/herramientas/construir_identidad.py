#!/usr/bin/env python3
"""Identidad Núcleo (kerna/diseno/identidad-v3, paleta B) adaptada a fondo claro, como sprite estático del front.

Genera app/estaticos/identidad.svg (un <symbol> por dibujo, sin animación) y reemplaza en app/estaticos/kerna.css el bloque entre
/* IDENTIDAD-INICIO */ y /* IDENTIDAD-FIN */ (colores por estado, por categoría y por ley). Comprueba el contraste (WCAG) de los colores derivados.

Símbolos del sprite (se usan con <use href="/estaticos/identidad.svg#id">):
  t-<estado>   baldosa grande 160x120 con corte de esquina y el dibujo orbital completo (14 estados de la identidad)
  e-<estado>   el mismo dibujo sin baldosa (recorte cuadrado), para tarjetas y filas (24 a 56 px)
  m-<estado>   simplificación del dibujo para listas densas (16 a 24 px): sin órbitas punteadas y con trazo más grueso
  l-karin | l-datos | l-penal   íconos de ley (Ley Karin: personas unidas; datos personales: nodo hexagonal; responsabilidad penal: edificio con columnas)
  n-<concepto> íconos nuevos con el mismo lenguaje (trazo, órbita, satélite, núcleo) para lo que la librería no tenía: ver NUEVOS
Uso: python3 kerna/front/herramientas/construir_identidad.py"""
import json, re, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from construir_iconos_estado import ICONOS, PAL, SVG, EST, estilizar, mezcla, razon, rgb  # noqa: E402

TINTA = "#0B1020"
MARCA = "#1C2A6B"
# Paleta B: ocho colores de categoría (nombre -> acento brillante de la identidad). Se oscurecen para fondo claro.
CATEGORIAS = {"lima": "#CFFF5E", "verde": PAL["verde"][2], "azul": PAL["azul"][2], "amarillo": PAL["ambar"][2], "naranja": PAL["naranja"][2],
              "coral": PAL["rojo"][2], "cian": PAL["cian"][2], "violeta": PAL["violeta"][2]}
LEYES = {"karin": "lima", "datos": "azul", "penal": "violeta"}

# ---------------------------------------------------------------- escenas de estado
def escena(n):
    t = (SVG / f"B-{n}.svg").read_text()
    c = t.split("</style>", 1)[1].rsplit("</svg>", 1)[0]
    c = re.sub(r'<circle class="ping"[^>]*/>', "", c)
    c = re.sub(r'<g class="spin[^"]*"[^>]*>(.*?)</g>', r"\1", c)
    c = re.sub(r'<g class="(?:late|chispa|blink|radar)"[^>]*>', "<g>", c)
    c = re.sub(r' (?:late|blink)"', '"', c)
    return estilizar(re.sub(r"(\d+\.\d)\d+", r"\1", c).replace(" />", "/>"))


def simplificar(c):
    """Versión para 16 a 24 px: quita lo punteado (no se lee) y engruesa el trazo."""
    c = re.sub(r"<(?:circle|path|ellipse)[^>]*stroke-dasharray[^>]*/>", "", c)
    c = re.sub(r"stroke-width:([\d.]+)", lambda m: f"stroke-width:{float(m.group(1)) * 1.8:.1f}", c)
    return c


# ---------------------------------------------------------------- íconos de ley (B, 48x48)
LEY = {
    "karin": '<circle class="o2" cx="15" cy="30" r="5"/><circle class="o2" cx="33" cy="30" r="5"/><path class="o2" d="M8,44 V38 q7,-6 14,0 V44 M26,44 V38 q7,-6 14,0 V44"/><path class="th2" d="M6,22 L24,4 L42,22"/><circle class="fa" cx="24" cy="4" r="3"/><circle class="fa" cx="6" cy="22" r="2.5"/><circle class="fa" cx="42" cy="22" r="2.5"/>',
    "datos": '<path class="o2" d="M24,3 L42,13.5 V34.5 L24,45 L6,34.5 V13.5 Z"/><circle class="o2" cx="24" cy="21" r="5"/><path class="o2" d="M24,26 V34"/><circle class="fa" cx="24" cy="3" r="2.8"/><circle class="fa" cx="42" cy="34.5" r="2.8"/><circle class="fa" cx="6" cy="34.5" r="2.8"/>',
    "penal": '<path class="o2" d="M24,4 L42,16 H6 Z"/><path class="o2" d="M12,20 V38 M24,20 V38 M36,20 V38 M5,42 H43"/><circle class="fa" cx="24" cy="4" r="3"/><circle class="fa" cx="12" cy="38" r="2.4"/><circle class="fa" cx="36" cy="38" r="2.4"/>',
}

# ---------------------------------------------------------------- íconos nuevos (48x48), mismo lenguaje: O trazo, Z órbita punteada, K trazo de acento, F satélite, C núcleo
def _s(*partes): return "".join(partes)
def p(cls, d): return f'<path class="{cls}" d="{d}"/>'
def c(cls, x, y, r): return f'<circle class="{cls}" cx="{x}" cy="{y}" r="{r}"/>'
O, Z, K, F, C = "O", "Z", "K", "F", "C"
NUEVOS = {
    "resumen": _s(c(O, 24, 24, 17), c(Z, 24, 24, 10), c(C, 24, 24, 4), c(F, 36, 12, 3.4), c(F, 10, 31, 2.8)),
    "informe": _s(p(O, "M12,6 H28 L36,14 V42 H12 Z"), p(O, "M28,6 V14 H36"), p(K, "M17,24 H30 M17,30 H30 M17,36 H25"), c(F, 36, 14, 3.2)),
    "negocio": _s(p(O, "M9,42 H41"), p(O, "M11,42 V32 H19 V42 M21,42 V24 H29 V42 M31,42 V16 H39 V42"), p(Z, "M8,22 A18,18 0 0 1 26,8"), c(F, 26, 8, 3.2)),
    "ajustes": _s(p(O, "M8,12 H40 M8,24 H40 M8,36 H40"), c(F, 17, 12, 4.2), c(F, 31, 24, 4.2), c(F, 21, 36, 4.2)),
    "portada": _s(c(O, 24, 24, 16), f'<ellipse class="{Z}" cx="24" cy="24" rx="7" ry="16"/>', p(K, "M8,24 H40"), c(F, 37, 9, 3.2)),
    "denuncias": _s(p(O, "M8,28 H15 L18,34 H30 L33,28 H40 V40 H8 Z"), p(Z, "M24,5 V19"), p(K, "M18,19 L24,25 L30,19"), c(F, 24, 6, 3)),
    "acierto": _s(c(O, 24, 24, 17), c(O, 24, 24, 9), c(C, 24, 24, 3.4), p(K, "M24,24 L37,11"), c(F, 38, 10, 3.3)),
    "tiempo": _s(c(O, 24, 24, 15), c(Z, 24, 24, 20), p(K, "M24,14 V24 L31,28"), c(C, 24, 24, 2.4), c(F, 37, 9, 3.2)),
    "costo": _s(c(O, 24, 24, 14), c(Z, 24, 24, 8.5), c(C, 24, 24, 3.4), p(K, "M13,41 H35"), c(F, 38, 11, 3.2)),
    "ingresos": _s(p(O, "M7,42 H41"), p(K, "M8,34 L18,25 L25,30 L38,14"), c(C, 18, 25, 2.2), c(C, 25, 30, 2.2), c(F, 38, 14, 3.4), p(Z, "M10,16 A18,18 0 0 1 28,8")),
    "utilidad": _s(p(K, "M7,16 H41"), c(C, 24, 16, 3), p(O, "M24,19 V38 M16,41 H32"), p(O, "M10,16 V24 M38,16 V24"), c(F, 10, 29, 5), c(F, 38, 29, 5)),
    "margen": _s(c(O, 24, 24, 16), p(K, "M24,24 L24,8"), '<path class="K" d="M24,24 L24,8 A16,16 0 0 1 38,32 Z" style="fill:var(--ac2);fill-opacity:.22"/>', c(C, 24, 24, 3), c(F, 38, 32, 3.2)),
    "clientes": _s(p(O, "M7,42 H41"), p(O, "M10,42 V14 H28 V42 M28,22 H38 V42"), c(C, 15, 21, 1.5), c(C, 22, 21, 1.5), c(C, 15, 28, 1.5), c(C, 22, 28, 1.5), c(C, 15, 35, 1.5), c(C, 22, 35, 1.5), c(F, 37, 10, 3.2)),
    "modelo": _s(p(O, "M12,12 H36 V36 H12 Z"), p(K, "M18,6 V12 M30,6 V12 M18,36 V42 M30,36 V42 M6,18 H12 M6,30 H12 M36,18 H42 M36,30 H42"), c(Z, 24, 24, 7), c(C, 24, 24, 3), c(F, 31, 24, 2.4)),
    "ayuda": _s(c(Z, 24, 24, 19), p(K, "M18.5,19 A5.5,5.5 0 1 1 26.5,24 C24.5,25.2 24,26.4 24,29"), c(C, 24, 34.5, 1.8), c(F, 39, 11, 3)),
    "descargar": _s(p(K, "M24,8 V28 M16,21 L24,29 L32,21"), p(O, "M9,40 H39"), c(F, 38, 40, 3), c(F, 10, 40, 3)),
    "reintentar": _s(p(K, "M36,24 A12,12 0 1 1 29,13"), p(K, "M31,6 V14 H39"), c(C, 24, 24, 3), c(F, 12, 24, 3)),
    "restaurar": _s(p(K, "M12,24 A12,12 0 1 0 19,13"), p(K, "M17,6 V14 H9"), c(C, 24, 24, 3), c(F, 36, 24, 3)),
    "calendario": _s(p(O, "M8,12 H40 V40 H8 Z M8,20 H40"), c(F, 16, 10, 3), c(F, 32, 10, 3), c(C, 16, 28, 1.6), c(C, 24, 28, 1.6), c(C, 32, 28, 1.6), c(C, 16, 34, 1.6), c(C, 24, 34, 1.6)),
    "tabla": _s(p(O, "M8,10 H40 V38 H8 Z M8,19 H40 M8,28 H40 M21,10 V38"), c(F, 31, 23.5, 3.2)),
    "editar": _s(p(O, "M31,9 L39,17 L18,38 L9,39 L10,30 Z"), p(K, "M26,14 L34,22"), c(F, 9, 39, 3)),
    "guardar": _s(p(O, "M10,10 H34 L38,14 V38 H10 Z M16,10 V19 H30 V10"), c(O, 24, 30, 4.5), c(F, 38, 10, 3)),
    "persona": _s(c(O, 24, 16, 6), p(O, "M10,41 Q24,21 38,41"), c(F, 38, 10, 3)),
    "flujo": _s(p(K, "M14,12 H24 V24 H34 M24,24 V36 H14"), c(F, 10, 12, 4), c(F, 38, 24, 4), c(F, 10, 36, 4)),
    "ia": _s(p(K, "M24,6 V14 M24,34 V42 M6,24 H14 M34,24 H42"), c(Z, 24, 24, 12), c(C, 24, 24, 4), c(F, 33, 15, 3)),
    "plazos": _s(c(O, 24, 26, 14), p(K, "M24,18 V26 L29,29"), p(O, "M20,6 H28"), c(F, 38, 12, 3)),
}
CLASES_N = {
    "O": "fill:none;stroke:var(--pi);stroke-width:2.4;stroke-linecap:round;stroke-linejoin:round",
    "Z": "fill:none;stroke:var(--pi);stroke-width:1.8;stroke-dasharray:2.5 3.5;stroke-linecap:round;opacity:.75",
    "K": "fill:none;stroke:var(--ac2);stroke-width:2.8;stroke-linecap:round;stroke-linejoin:round",
    "F": "fill:var(--sat);stroke:var(--pi);stroke-width:1.8",
    "C": "fill:var(--pi);stroke:none",
}


def estilo_n(cuerpo):
    return re.sub(r'class="([OZKFC])"', lambda m: f'style="{CLASES_N[m.group(1)]}"', cuerpo)


# ---------------------------------------------------------------- colores de estado para fondo claro
def vars_estado(tono):
    f, x, a = PAL[tono]
    if tono == "fin":
        return dict(fondo="#CFFF5E", borde="#7C9E1F", acc="#0B1020", pi=TINTA, pf="#CFFF5E")
    return dict(fondo=mezcla(a, "#FFFFFF", .88), borde=mezcla(a, f, .45), acc=mezcla(a, f, .42), pi=TINTA, pf="#FFFFFF")


def simbolos():
    out = ['<svg xmlns="http://www.w3.org/2000/svg" style="display:none">']
    for n in ICONOS:
        esc = escena(n)
        out.append(f'<symbol id="e-{n}" viewBox="26 6 108 108">{esc}</symbol>')
        out.append(f'<symbol id="m-{n}" viewBox="26 6 108 108">{simplificar(esc)}</symbol>')
        out.append(f'<symbol id="t-{n}" viewBox="0 0 160 120"><polygon points="20,1 159,1 159,100 140,119 1,119 1,20" style="fill:var(--fondo);stroke:var(--borde);stroke-width:2;stroke-linejoin:round"/>{esc}</symbol>')
    for n, g in LEY.items():
        out.append(f'<symbol id="l-{n}" viewBox="0 0 48 48">{estilizar(g)}</symbol>')
    for n, g in NUEVOS.items():
        out.append(f'<symbol id="n-{n}" viewBox="0 0 48 48">{estilo_n(g)}</symbol>')
    out.append("</svg>")
    (EST / "identidad.svg").write_text("\n".join(out) + "\n")


def css():
    r = ["/* IDENTIDAD-INICIO (generado por herramientas/construir_identidad.py; Núcleo, paleta B, fondo claro) */"]
    mal = []
    for n, t in ICONOS.items():
        v = vars_estado(t)
        r.append(f'k-st[data-e="{n}"],.ti[data-e="{n}"]{{--fondo:{v["fondo"]};--borde:{v["borde"]};--acc:{v["acc"]};--pi:{v["pi"]};--pf:{v["pf"]}}}')
        if t != "fin" and razon(v["acc"], v["fondo"]) < 3: mal.append((n, "acc/fondo", round(razon(v["acc"], v["fondo"]), 2)))
        if razon(v["pi"], v["fondo"]) < 7: mal.append((n, "tinta/fondo", round(razon(v["pi"], v["fondo"]), 2)))
    r.append("/* categorías (gráficos y leyes): relleno = mezcla del color B con la tinta; tinte = color B sobre blanco */")
    cat = []
    for nom, a in CATEGORIAS.items():
        bar = mezcla(a, TINTA, .42 if nom != "lima" else .5)
        tinte = mezcla(a, "#FFFFFF", .85)
        cat.append(f"--c-{nom}:{bar};--c-{nom}-bg:{tinte};--c-{nom}-ac:{a}")
        rz = razon(bar, "#FFFFFF")
        print(f"cat {nom:9} barra/blanco {rz:4.2f}")
        if rz < 3: mal.append((nom, "barra/blanco", round(rz, 2)))
    r.append(":root{" + ";".join(cat) + f";--sat:#CFFF5E;--ac2:#3B4FB4}}")
    for l, nom in LEYES.items():
        r.append(f'.lx[data-l="{l}"]{{--acc:var(--c-{nom});--pi:{TINTA};--pf:#fff;--fondo:var(--c-{nom}-bg);--borde:var(--c-{nom})}}')
    r.append("k-n,k-lx{--pi:#1C2A6B;--ac2:#3B4FB4;--sat:#CFFF5E}")
    r.append("/* IDENTIDAD-FIN */")
    return "\n".join(r), mal


if __name__ == "__main__":
    simbolos()
    bloque, mal = css()
    pth = EST / "kerna.css"; s = pth.read_text()
    if "/* IDENTIDAD-INICIO" in s:
        s = re.sub(r"/\* IDENTIDAD-INICIO.*?/\* IDENTIDAD-FIN \*/", lambda m: bloque, s, flags=re.S)
    else:
        s += "\n" + bloque + "\n"
    pth.write_text(s)
    print("FALLAS:", mal or "ninguna"); sys.exit(1 if mal else 0)
