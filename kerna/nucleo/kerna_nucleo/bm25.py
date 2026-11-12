"""Búsqueda léxica BM25 en español y fusión por Reciprocal Rank Fusion (RRF) con la búsqueda densa.

BM25 es un algoritmo (no un modelo): corre en el proceso, sin llamadas externas. Captura términos concretos del
relato que coinciden con el texto legal («licencia médica», «cotizaciones», «cámaras», «factura», «soborno») y que
el embedding diluye en relatos largos. El texto se normaliza: minúsculas, sin tildes, sin palabras vacías y, de forma
opcional, con un stemming liviano por sufijos.
"""
from __future__ import annotations

import heapq
import math
import re
import unicodedata
from collections import Counter, defaultdict
from typing import Iterable, Sequence

RRF_K = 60

PALABRAS_VACIAS = frozenset("""
a al algo algun alguna algunas alguno algunos ante antes aqui asi aun aunque bajo cada casi como con contra cual
cuales cuando cuanto de del desde donde dos e el ella ellas ellos en entre era eran es esa esas ese eso esos esta
estaba estaban estan estar estas este esto estos fue fueron ha haber habia han hasta hay hecho la las le les lo los
mas me mi mis mucho muy nada ni no nos nuestra nuestro o otra otras otro otros para pero poco por porque que quien
quienes se sea sean segun ser si sido sin sobre solo son su sus tambien tan tanto te tener tiene tienen todo todos
tras tu tus un una unas uno unos y ya yo
""".split())

_NO_ALNUM = re.compile(r"[^a-z0-9]+")
_SUFIJOS = ("amientos", "imientos", "amiento", "imiento", "aciones", "uciones", "adoras", "adores", "ancias",
            "acion", "ucion", "adora", "ador", "ancia", "mente", "ables", "ibles", "able", "ible",
            "idad", "ando", "iendo", "aron", "ieron", "ados", "adas", "idos", "idas", "ado", "ada", "ido", "ida",
            "ar", "er", "ir", "es", "s")
_MIN_RAIZ = 4


def sin_tildes(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def raiz(palabra: str) -> str:
    """Stemming liviano: quita un sufijo común del español dejando una raíz de al menos 4 letras."""
    for suf in _SUFIJOS:
        if palabra.endswith(suf) and len(palabra) - len(suf) >= _MIN_RAIZ:
            return palabra[: -len(suf)]
    return palabra


def tokenizar(texto: str, stemming: bool = True) -> list[str]:
    """Minúsculas, sin tildes (la ñ se conserva como n), sin palabras vacías; números y palabras de 2+ caracteres."""
    plano = sin_tildes((texto or "").casefold())
    out = []
    for t in _NO_ALNUM.split(plano):
        if len(t) < 2 or t in PALABRAS_VACIAS:
            continue
        out.append(raiz(t) if stemming and not t.isdigit() else t)
    return out


class IndiceBM25:
    """Índice invertido BM25 (Okapi) sobre una lista de documentos identificados por una clave."""

    def __init__(self, documentos: Iterable[tuple[str, str]], stemming: bool = True, k1: float = 1.5, b: float = 0.75):
        self.stemming, self.k1, self.b = stemming, k1, b
        self.ids: list[str] = []
        self._largo: list[int] = []
        self._post: dict[str, list[tuple[int, int]]] = defaultdict(list)
        for ident, texto in documentos:
            toks = tokenizar(texto, stemming)
            i = len(self.ids)
            self.ids.append(ident)
            self._largo.append(len(toks))
            for t, n in Counter(toks).items():
                self._post[t].append((i, n))
        self.n = len(self.ids)
        self._medio = (sum(self._largo) / self.n) if self.n else 0.0

    def buscar(self, consulta: str, k: int = 100) -> list[tuple[str, float]]:
        """Los k documentos con mayor puntaje BM25 (solo los que comparten algún término), de mayor a menor."""
        if not self.n:
            return []
        puntaje: dict[int, float] = defaultdict(float)
        for t in set(tokenizar(consulta, self.stemming)):
            lista = self._post.get(t)
            if not lista:
                continue
            idf = math.log(1 + (self.n - len(lista) + 0.5) / (len(lista) + 0.5))
            for i, tf in lista:
                norma = 1 - self.b + self.b * self._largo[i] / (self._medio or 1.0)
                puntaje[i] += idf * tf * (self.k1 + 1) / (tf + self.k1 * norma)
        mejores = heapq.nlargest(k, puntaje.items(), key=lambda x: (x[1], -x[0]))
        return [(self.ids[i], s) for i, s in mejores]


def rrf(rankings: Sequence[Sequence[str]], k: int = RRF_K,
        pesos: Sequence[float] | None = None) -> list[tuple[str, float]]:
    """Reciprocal Rank Fusion: suma 1/(k + rango) de cada lista (rango desde 1). Orden descendente; el empate lo
    decide la primera lista en que aparece el elemento (la de la consulta principal va primero). `pesos`: un factor
    por lista (por defecto 1)."""
    puntaje: dict[str, float] = {}
    primera: dict[str, tuple[int, int]] = {}
    for li, lista in enumerate(rankings):
        vistos = set()
        for r, ident in enumerate(lista, 1):
            if ident in vistos:
                continue
            vistos.add(ident)
            puntaje[ident] = puntaje.get(ident, 0.0) + (pesos[li] if pesos else 1.0) / (k + r)
            primera.setdefault(ident, (li, r))
    return sorted(puntaje.items(), key=lambda x: (-x[1], primera[x[0]]))
