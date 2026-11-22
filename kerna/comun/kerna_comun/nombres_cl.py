"""Diccionarios del anonimizador, generados desde fuentes públicas por kerna/comun/herramientas/generar_diccionarios.py.

- NOMBRES / APELLIDOS: frecuentes en Chile (Registro Civil vía «guaguas», forebears.io), España (INE, ≥ 100 personas) y Argentina.
- APELLIDOS_FRECUENTES: los más frecuentes de Chile y España; base de la coincidencia aproximada.
- OTROS: nombres y apellidos de otros países (NameDatabases) y los menos frecuentes de Chile.
- PALABRAS / VERBOS: nombres o apellidos que también son palabra o forma verbal del español.
- LEMARIO: todas las palabras y formas verbales del español (olea/lemarios).
- CALLES: nombres de vías de Chile en OpenStreetMap (© colaboradores de OSM, ODbL).
- LUGARES: países y ciudades de más de 15.000 habitantes (GeoNames, CC BY 4.0).
Todo en minúsculas y sin tildes. Fuentes y licencias en diccionarios/FUENTES.md.

Coincidencia aproximada: `parecido(t)` dice si una palabra que no es del español suena como un nombre o apellido frecuente
(«karlos» → carlos, «gonsales» → gonzalez) o se diferencia de uno en una sola letra («carlso», «gonzalz»).
"""
from __future__ import annotations

import gzip
import re
from pathlib import Path

_DIR = Path(__file__).with_name("diccionarios")


def _leer(nombre: str) -> frozenset:
    return frozenset(x for x in (_DIR / f"{nombre}.txt").read_text(encoding="utf-8").split("\n") if x)


NOMBRES = _leer("nombres")
APELLIDOS = _leer("apellidos")
APELLIDOS_FRECUENTES = _leer("apellidos_frecuentes")
OTROS = _leer("otros")
PALABRAS = _leer("palabras")
VERBOS = _leer("verbos")
CALLES = _leer("calles")
LUGARES = _leer("lugares")
with gzip.open(_DIR / "lemario.txt.gz", "rt", encoding="utf-8") as _f:
    LEMARIO = frozenset(x for x in _f.read().split("\n") if x)


_CLITICOS = ("selos", "selas", "melo", "mela", "telo", "tela", "les", "los", "las", "nos", "le", "lo", "la", "se", "me", "te")


def es_palabra(t: str) -> bool:
    """t o su forma base (sin plural, en masculino o sin pronombre pegado) está en el lemario del español."""
    if t in LEMARIO:
        return True
    cand = set()
    if t.endswith("es"):
        cand |= {t[:-2], t[:-1]}
    if t.endswith("s"):
        cand.add(t[:-1])
    for c in list(cand) + [t]:
        if c.endswith("a"):
            cand.add(c[:-1] + "o")
            cand.add(c[:-1])
    for cl in _CLITICOS:
        if t.endswith(cl) and len(t) - len(cl) >= 3:
            cand.add(t[:-len(cl)])
    return any(c in LEMARIO for c in cand)


def fonetica(w: str) -> str:
    """Clave fonética del español de Chile para palabras ya en minúscula y sin tildes."""
    w = re.sub(r"[^a-z]", "", w)
    w = w.replace("ch", "X").replace("ll", "y").replace("ph", "f").replace("qu", "k").replace("h", "")
    w = re.sub(r"c(?=[ei])", "s", w).replace("c", "k").replace("q", "k").replace("z", "s").replace("x", "ks")
    w = re.sub(r"g(?=[ei])", "j", w).replace("gue", "ge").replace("gui", "gi")
    w = w.replace("v", "b").replace("w", "u").replace("y", "i")
    return re.sub(r"(.)\1+", r"\1", w)


def _borrados(w: str) -> set:
    return {w[:i] + w[i + 1:] for i in range(len(w))}


def _indice(base: frozenset) -> tuple:
    borr: dict = {}
    for w in base:
        if len(w) >= 5:
            for b in _borrados(w):
                borr.setdefault(b, set()).add(w)
    return base, {fonetica(w) for w in base if len(w) >= 4}, borr


# El parecido se mide contra lo más frecuente (minúscula) o contra todos los nombres y apellidos (con mayúscula).
_FRECUENTE = _indice((NOMBRES | APELLIDOS_FRECUENTES) - LEMARIO)
_AMPLIO = _indice((NOMBRES | APELLIDOS) - LEMARIO)
_FON = _FRECUENTE[1]


def parecido(t: str, amplio: bool = False) -> bool:
    """t (minúscula, sin tildes) no es del español y suena como un nombre o apellido o difiere de uno en una letra.
    amplio=True compara con todos los apellidos (para palabras con mayúscula); si no, solo con los más frecuentes."""
    if len(t) < 4 or es_palabra(t):
        return False
    base, fon, borr = _AMPLIO if amplio else _FRECUENTE
    if fonetica(t) in fon:
        return True
    if len(t) < 5:
        return False
    if t in borr:
        return True
    b = _borrados(t)
    return any(x in base for x in b) or any(x in borr for x in b)
