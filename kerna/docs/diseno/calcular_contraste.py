#!/usr/bin/env python3
"""Calcula las razones de contraste WCAG 2.2 de la paleta de estados del indicador de Kerna.

Uso: python3 calcular_contraste.py            (imprime la tabla en Markdown)
     python3 calcular_contraste.py --verificar (falla si algo no cumple o si la maqueta usa otros colores)
Criterios: texto/fondo >= 4,5:1 (1.4.3); acento (borde y glifo) contra el fondo de la etiqueta y contra la
página (blanco) >= 3:1 (1.4.11). La fórmula es la de WCAG (luminancia relativa, sin redondear).
"""
import pathlib
import sys

PAGINA = "#FFFFFF"
# estado: (fondo, texto, acento = glifo y borde; en los estados oscuros el borde es el fondo)
PALETA = {
    "sin-info":            ("#F5F7FA", "#434A54", "#707A8A"),
    "generando":           ("#DCEBF8", "#12324F", "#2A6496"),
    "lista":               ("#DDF3E4", "#11432A", "#2E7D4F"),
    "contingencia":        ("#FFF2BF", "#4D3A00", "#8F6B00"),
    "revision-tiempo":     ("#FFE2C4", "#5C2C05", "#A85400"),
    "revision-citas":      ("#EAE4F7", "#2E1F63", "#6A4FB3"),
    "sin-normativa":       ("#DDEFF0", "#0F4249", "#2C7C86"),
    "cadena-agotada":      ("#FDE0DD", "#7A1212", "#C62828"),
    "nucleo-no-disponible": ("#FBDCEA", "#6B0F3B", "#B02A6B"),
    "conector-inactivo":   ("#E7E2D6", "#433818", "#7D6D45"),
    "sin-conexion":        ("#323A49", "#FFFFFF", "#FFFFFF"),
    "valorada":            ("#205782", "#FFFFFF", "#FFFFFF"),
}
# Tooltip y otros elementos fijos: (nombre, primer plano, fondo, mínimo)
FIJOS = [
    ("tooltip: texto / fondo", "#FFFFFF", "#1D1F24", 4.5),
    ("aviso permanente: texto / fondo", "#1D1F24", "#EBEFF5", 4.5),
    ("aviso de contingencia: texto / fondo", "#4D3A00", "#FFF2BF", 4.5),
    ("enlace (azul Veridy) / blanco", "#205782", "#FFFFFF", 4.5),
    ("anillo de foco / blanco", "#205782", "#FFFFFF", 3.0),
]


def lum(h):
    h = h.lstrip("#")
    c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    c = [x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4 for x in c]
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]


def razon(a, b):
    la, lb = lum(a), lum(b)
    if la < lb:
        la, lb = lb, la
    return (la + 0.05) / (lb + 0.05)


def borde(e):
    """Borde de la etiqueta: el acento en los estados claros; el propio fondo en los oscuros."""
    f, t, a = PALETA[e]
    return f if lum(f) < 0.2 else a


def filas():
    for e, (fondo, texto, acento) in PALETA.items():
        yield e, fondo, texto, acento, razon(texto, fondo), razon(acento, fondo), razon(borde(e), PAGINA), razon(fondo, PAGINA)


def main():
    verificar = "--verificar" in sys.argv
    mal = []
    print("| Estado | Fondo | Texto | Acento | Texto/fondo (>=4,5) | Acento/fondo (>=3) | Borde/página (>=3) | Fondo/página (informativo) |")
    print("|---|---|---|---|---|---|---|---|")
    for e, f, t, a, r1, r2, r3, r4 in filas():
        print(f"| `{e}` | `{f}` | `{t}` | `{a}` | {r1:.2f} | {r2:.2f} | {r3:.2f} | {r4:.2f} |")
        if r1 < 4.5:
            mal.append((e, "texto/fondo", r1))
        if r2 < 3:
            mal.append((e, "acento/fondo", r2))
        if r3 < 3:
            mal.append((e, "borde/página", r3))
    print()
    print("| Elemento fijo | Primer plano | Fondo | Razón | Mínimo |")
    print("|---|---|---|---|---|")
    for n, fg, bg, mn in FIJOS:
        r = razon(fg, bg)
        print(f"| {n} | `{fg}` | `{bg}` | {r:.2f} | {mn} |")
        if r < mn:
            mal.append((n, "fijo", r))
    if verificar:
        html = (pathlib.Path(__file__).parent / "opciones-icono/maqueta/maqueta.html").read_text().upper()
        for e, (f, t, a) in PALETA.items():
            for h in (f, t, a):
                if h.upper() not in html:
                    mal.append((e, f"la maqueta no usa {h}", 0))
        if mal:
            print("\nFALLAS:", mal)
            sys.exit(1)
        print("\nTodo cumple.")


if __name__ == "__main__":
    main()
