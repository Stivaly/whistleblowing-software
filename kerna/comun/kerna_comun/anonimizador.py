"""Anonimizador por reglas. Versión mínima provisional: correos y RUT."""
from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class Resultado:
    texto: str
    conteos: dict = field(default_factory=dict)


_REGLAS = [("CORREO", re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")),
           ("RUT", re.compile(r"\b\d{1,2}\.?\d{3}\.?\d{3}-[\dkK]\b"))]


def anonimizar(texto: str) -> Resultado:
    conteos: dict = {}
    for tipo, patron in _REGLAS:
        vistos: dict = {}

        def _sustituir(m, tipo=tipo, vistos=vistos):
            return vistos.setdefault(m.group(0).lower(), f"[{tipo}_{len(vistos) + 1}]")

        texto = patron.sub(_sustituir, texto)
        if vistos:
            conteos[tipo] = len(vistos)
    return Resultado(texto=texto, conteos=conteos)
