"""Partición de artículos-lista por literal (experimento de enriquecimiento, KERNA_ENRIQUECIDO).

Un artículo que enumera muchas conductas (p. ej. las 13 prohibiciones del art. 84 del Estatuto Administrativo) se
embebe como un solo vector diluido. `partir_literales` devuelve la introducción y cada literal; cada literal se indexa
como fragmento propio con la introducción por delante y, al devolver resultados, se deduplica por artículo.
Solo se parte si hay al menos `MIN_LITERALES` literales y el texto mide `MIN_CARACTERES` o más.
"""
from __future__ import annotations

import re

MIN_LITERALES = 6
MIN_CARACTERES = 2000
_MARCA = re.compile(r"(?m)^\s*(?:([a-zñ])\)|(\d{1,2})\s*[.)\-°º]+)\s+(?=\S)")


def partir_literales(texto: str) -> tuple[str, list[tuple[str, str]]]:
    """-> (introducción, [(etiqueta, texto del literal)]). Sin lista suficiente: (texto, [])."""
    marcas = list(_MARCA.finditer(texto or ""))
    # Solo cuenta la serie que empieza en a) o 1 y sigue en orden (descarta incisos sueltos "1)" dentro de un literal).
    serie, esperado = [], None
    for m in marcas:
        etiqueta = m.group(1) or m.group(2)
        if esperado is None:
            if etiqueta not in ("a", "1"):
                continue
        elif etiqueta != esperado:
            continue
        serie.append(m)
        esperado = chr(ord(etiqueta) + 1) if etiqueta.isalpha() else str(int(etiqueta) + 1)
    if len(serie) < MIN_LITERALES or len(texto) < MIN_CARACTERES:
        return texto, []
    intro = texto[: serie[0].start()].strip()
    out = []
    for i, m in enumerate(serie):
        fin = serie[i + 1].start() if i + 1 < len(serie) else len(texto)
        out.append(((m.group(1) or m.group(2)), texto[m.start():fin].strip()))
    return intro, out
