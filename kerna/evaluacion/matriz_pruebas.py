#!/usr/bin/env python3
"""Genera kerna/evaluacion/matriz-pruebas.md: ID del informe (PR-01..PR-39) -> pruebas que lo llevan -> último resultado.

Lee los marcas-<capa>.json de reportes/pruebas/*/ (para cada capa, la corrida más reciente que la incluye) y el
alcance de kerna/pruebas/datos/alcance_pr.json. Uso: python3 kerna/evaluacion/matriz_pruebas.py [--reportes DIR]
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re

AQUI = pathlib.Path(__file__).resolve().parent
RAIZ_REPO = AQUI.parents[1]
ALCANCE = AQUI.parent / "pruebas" / "datos" / "alcance_pr.json"
SALIDA = AQUI / "matriz-pruebas.md"
ETIQUETA = {"pasada": "pasada", "fallida": "FALLIDA", "omitida": "omitida"}


def ultimos_resultados(reportes: pathlib.Path) -> dict[str, dict]:
    """nodeid -> {capa, resultado, corrida}; por capa manda la corrida más reciente que la incluye."""
    por_capa: dict[str, tuple[str, dict]] = {}
    for carpeta in sorted(p for p in reportes.glob("*") if p.is_dir()):
        for f in carpeta.glob("marcas-*.json"):
            capa = re.sub(r"^marcas-", "", f.stem).split("-")[0]
            por_capa[f"{capa}|{f.stem}"] = (carpeta.name, json.loads(f.read_text(encoding="utf-8")).get("pruebas", {}))
    # si una capa tiene varias partes, cada parte conserva su corrida más reciente
    salida = {}
    for clave, (corrida, pruebas) in por_capa.items():
        capa = clave.split("|")[0]
        for nodeid, d in pruebas.items():
            salida[nodeid] = {"capa": capa, "resultado": d["resultado"], "corrida": corrida, "marcas": d["marcas"]}
    return salida


def generar(reportes: pathlib.Path) -> str:
    alcance = json.loads(ALCANCE.read_text(encoding="utf-8"))["pr"]
    resultados = ultimos_resultados(reportes)
    por_pr: dict[str, list[tuple[str, dict]]] = {}
    for nodeid, d in resultados.items():
        for pr in d["marcas"].get("pr", []):
            por_pr.setdefault(pr, []).append((nodeid, d))
    lineas = [
        "# Matriz de pruebas del informe",
        "",
        "Generada por `kerna/evaluacion/matriz_pruebas.py` con el último resultado de cada capa en `reportes/pruebas/`.",
        "Las pruebas declaran su caso con `@pytest.mark.pr(\"PR-xx\")`; el alcance está en `kerna/pruebas/datos/alcance_pr.json`.",
        "",
        "| PR | Caso | Alcance | Pruebas | Último resultado |",
        "| --- | --- | --- | --- | --- |",
    ]
    resumen = {"pasada": 0, "fallida": 0, "sin": 0, "fuera": 0}
    for pr in sorted(alcance):
        info = alcance[pr]
        pruebas = sorted(por_pr.get(pr, []))
        if info["alcance"] != "va":
            fuera = "no va" if info["alcance"] == "no_va" else "después del MVP"
            lineas.append(f"| {pr} | {info['titulo']} | fuera del MVP ({fuera}) | - | {info['motivo']} |")
            resumen["fuera"] += 1
            continue
        if not pruebas:
            lineas.append(f"| {pr} | {info['titulo']} | va | - | sin pruebas |")
            resumen["sin"] += 1
            continue
        estados = {d["resultado"] for _, d in pruebas}
        global_ = "fallida" if "fallida" in estados else ("pasada" if "pasada" in estados else "omitida")
        resumen["fallida" if global_ == "fallida" else "pasada" if global_ == "pasada" else "sin"] += 1
        nombres = "<br>".join(f"`{n.split('/')[-1]}` ({ETIQUETA[d['resultado']]}, {d['capa']})" for n, d in pruebas)
        corrida = max(d["corrida"] for _, d in pruebas)
        lineas.append(f"| {pr} | {info['titulo']} | va | {nombres} | {ETIQUETA[global_]} ({corrida}) |")
    desconocidos = sorted(set(por_pr) - set(alcance))
    lineas += ["", f"Dentro del MVP: {resumen['pasada']} con pruebas pasando, {resumen['fallida']} con fallas, "
               f"{resumen['sin']} sin pruebas o solo omitidas; {resumen['fuera']} fuera del MVP."]
    if desconocidos:
        lineas += ["", "Marcas `pr` que no están en `alcance_pr.json`: " + ", ".join(desconocidos)]
    return "\n".join(lineas) + "\n"


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--reportes", default=str(RAIZ_REPO / "reportes" / "pruebas"))
    a = p.parse_args()
    SALIDA.write_text(generar(pathlib.Path(a.reportes)), encoding="utf-8")
    print(f"Matriz escrita en {SALIDA.relative_to(RAIZ_REPO)}")


if __name__ == "__main__":
    main()
