"""Formatos legibles en español de Chile: miles con punto, decimales con coma, segundos en vez de milisegundos."""
from __future__ import annotations


def miles(n) -> str:
    try:
        return f"{round(float(n)):,}".replace(",", ".")
    except (TypeError, ValueError):
        return "—"


def dec(x, d: int = 1) -> str:
    try:
        s = f"{float(x):,.{d}f}"
    except (TypeError, ValueError):
        return "—"
    return s.replace(",", "§").replace(".", ",").replace("§", ".")


def dec_corto(x, d: int = 1) -> str:
    """Sin ceros de relleno: 47,5 ; 80 ; 0,25."""
    t = dec(x, d)
    if "," in t:
        t = t.rstrip("0").rstrip(",")
    return t


def segundos(ms, d: int | None = None) -> str:
    """27141 -> «27» ; 4523 -> «4,5»."""
    try:
        s = float(ms) / 1000
    except (TypeError, ValueError):
        return "—"
    return dec(s, d if d is not None else (1 if s < 10 else 0))


def uf(v, d: int = 2) -> str:
    return dec(v, d)


def usd(v, d: int = 2) -> str:
    try:
        v = float(v)
    except (TypeError, ValueError):
        return "—"
    return dec(v, 3 if 0 < v < 0.005 else d)


def porcentaje(v, d: int = 0) -> str:
    return dec_corto(v, d) if d else miles(v)


def fecha_corta(iso: str | None) -> str:
    """'2026-11-12' o '2026-11-12T14:30:00Z' -> '12 nov'."""
    meses = ("ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic")
    try:
        return f"{int(iso[8:10])} {meses[int(iso[5:7]) - 1]}"
    except (TypeError, ValueError, IndexError):
        return iso or "—"


def fecha_hora(iso: str | None) -> str:
    try:
        return f"{fecha_corta(iso)} {iso[11:16]} UTC"
    except Exception:
        return iso or "—"


FUNCIONES = {"miles": miles, "dec": dec, "dec_corto": dec_corto, "segundos": segundos, "uf": uf, "usd": usd,
             "fecha_corta": fecha_corta, "fecha_hora": fecha_hora}
