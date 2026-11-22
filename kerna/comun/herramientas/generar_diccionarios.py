"""Genera los diccionarios del anonimizador (kerna_comun/diccionarios/) desde fuentes públicas descargadas.

Fuentes (descargarlas en carpetas aparte y pasar las rutas; detalle y licencias en diccionarios/FUENTES.md):
  --guaguas         sysdata.rda del paquete R «guaguas» 0.3.0 (CRAN): nombres inscritos en el Registro Civil de Chile 1920-2021.
  --forebears       apellidos de Chile de https://forebears.io/chile/surnames (rangos 1-793, copiados tal cual).
  --olea            carpeta con apellidos-es.txt, nombres-propios-es.txt, nombres-propios-ar.txt, lemario-general-del-espanol.txt
                    y verbos-espanol-conjugaciones.txt de github.com/olea/lemarios (dominio público).
  --namedb          carpeta con nombres_all.txt y apellidos_all.txt de github.com/smashew/NameDatabases (dominio público;
                    nombres y apellidos de varios países y culturas).
  --calles          CSV de nombres de vías de Chile (OpenStreetMap vía Overpass; © colaboradores de OSM, ODbL).
  --geonames        carpeta con cities15000.zip y countryInfo.txt de download.geonames.org (CC BY 4.0).
Salida (minúsculas, sin tildes, una entrada por línea):
  nombres.txt     nombres de pila frecuentes en Chile (≥ --min-chile inscripciones) y de España y Argentina.
  apellidos.txt   apellidos frecuentes en Chile y en España.
  otros.txt       nombres y apellidos de otros países y los menos frecuentes de Chile (≥ --min-otros inscripciones).
  palabras.txt / verbos.txt  nombres o apellidos (de las tres listas) que también son palabra o forma verbal del español.
  lemario.txt.gz  todas las palabras y formas verbales del español (para no tomar una palabra por un nombre).
  calles.txt      nombres de calle de Chile sin el tipo de vía.
  lugares.txt     países y ciudades de más de 15.000 habitantes (una palabra), para no tomarlos por un apellido extranjero.
Requiere pyreadr y pandas solo para generar; el anonimizador usa solo biblioteca estándar.
"""
from __future__ import annotations

import argparse
import collections
import gzip
import re
import unicodedata
from pathlib import Path

SALIDA = Path(__file__).resolve().parents[1] / "kerna_comun" / "diccionarios"
TIPOS_VIA = (r"^(?:avenida|av|avda|calle|pasaje|psje|pje|camino|ruta|autopista|carretera|costanera|diagonal|paseo|callejon|"
             r"circunvalacion|bulevar|boulevard)\.?\s+")


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s.replace("﻿", "").strip().lower()).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", s)


def leer(ruta: Path) -> set[str]:
    return {norm(x) for x in ruta.read_text(encoding="utf-8", errors="ignore").splitlines() if x.strip()}


def simples(conjunto: set[str]) -> set[str]:
    """Solo palabras sueltas alfabéticas de 3 o más letras (los compuestos se reconocen palabra por palabra)."""
    return {w for x in conjunto for w in x.split() if w.isalpha() and len(w) >= 3}


def main() -> None:
    ap = argparse.ArgumentParser()
    for a in ("guaguas", "forebears", "olea", "namedb", "calles", "geonames"):
        ap.add_argument("--" + a, required=True)
    ap.add_argument("--min-chile", type=int, default=200)
    ap.add_argument("--min-otros", type=int, default=20)
    a = ap.parse_args()
    olea, namedb = Path(a.olea), Path(a.namedb)

    import pyreadr
    df = pyreadr.read_r(a.guaguas)["guaguas"]
    total = collections.Counter()
    for nombre, n in zip(df.nombre, df.n):
        for w in norm(str(nombre)).split():
            total[w] += n
    chile = {w for w, n in total.items() if n >= a.min_chile}
    chile_poco = {w for w, n in total.items() if a.min_otros <= n < a.min_chile}

    nombres = simples(chile | leer(olea / "nombres-propios-es.txt") | leer(olea / "nombres-propios-ar.txt"))
    apellidos = simples(leer(Path(a.forebears)) | leer(olea / "apellidos-es.txt"))
    otros = simples(chile_poco | leer(namedb / "nombres_all.txt") | leer(namedb / "apellidos_all.txt")) - nombres - apellidos

    lemas = leer(olea / "lemario-general-del-espanol.txt")
    formas = leer(olea / "verbos-espanol-conjugaciones.txt")
    todos = nombres | apellidos | otros
    verbos = todos & formas
    palabras = (todos & lemas) - verbos

    calles = set()
    for linea in Path(a.calles).read_text(encoding="utf-8").splitlines():
        c = re.sub(TIPOS_VIA, "", norm(linea))
        c = re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", " ", c)).strip()
        if len(c) >= 4 and not c.isdigit():
            calles.add(c)

    import zipfile
    geo = Path(a.geonames)
    lugares = set()
    with zipfile.ZipFile(geo / "cities15000.zip") as z:
        for linea in z.read("cities15000.txt").decode("utf-8").splitlines():
            c = linea.split("\t")
            for x in [c[1], c[2]] + c[3].split(","):
                x = norm(x)
                if x.isalpha() and len(x) >= 4:
                    lugares.add(x)
    for linea in (geo / "countryInfo.txt").read_text(encoding="utf-8").splitlines():
        if linea and not linea.startswith("#"):
            lugares |= {w for w in norm(linea.split("\t")[4]).split() if w.isalpha() and len(w) >= 4}

    SALIDA.mkdir(exist_ok=True)
    for nombre, datos in (("nombres", nombres), ("apellidos", apellidos), ("otros", otros), ("palabras", palabras),
                          ("verbos", verbos), ("calles", calles), ("lugares", lugares)):
        (SALIDA / f"{nombre}.txt").write_text("\n".join(sorted(datos)) + "\n", encoding="utf-8")
        print(nombre, len(datos))
    lemario = sorted(lemas | formas)
    with gzip.open(SALIDA / "lemario.txt.gz", "wt", encoding="utf-8", compresslevel=9) as f:
        f.write("\n".join(lemario) + "\n")
    print("lemario", len(lemario))


if __name__ == "__main__":
    main()
