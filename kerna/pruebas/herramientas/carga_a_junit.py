#!/usr/bin/env python3
"""Convierte el CSV de locust (--csv <prefijo>) en un JUnit y un marcas-carga.json con los criterios del MVP.

PR-30: P95 de "caso -> sugerencia lista" <= KERNA_P95_MAX_MS (15000). PR-31: sin fallas ni excepciones.
"""
import argparse
import csv
import json
import os
import xml.etree.ElementTree as ET


def main():
    p = argparse.ArgumentParser()
    p.add_argument("prefijo")
    p.add_argument("junit")
    p.add_argument("marcas")
    p.add_argument("--duracion", type=float, default=0.0)
    a = p.parse_args()
    filas = list(csv.DictReader(open(a.prefijo + "_stats.csv", encoding="utf-8")))
    por_nombre = {f["Name"]: f for f in filas}
    total = por_nombre.get("Aggregated", {})
    meta = por_nombre.get("caso -> sugerencia lista")
    p95_max = float(os.environ.get("KERNA_P95_MAX_MS", "15000"))
    resultados = []
    if meta is None or int(meta["Request Count"]) == 0:
        resultados.append(("p95_sugerencia_lista", "PR-30", f"sin sugerencias completadas para medir P95"))
    else:
        p95 = float(meta["95%"])
        resultados.append(("p95_sugerencia_lista", "PR-30", None if p95 <= p95_max else f"P95 {p95:.0f} ms > {p95_max:.0f} ms"))
    fallas = int(total.get("Failure Count", 0)) if total else 1
    resultados.append(("sin_fallas", "PR-31", None if fallas == 0 else f"{fallas} solicitudes fallidas"))
    suite = ET.Element("testsuite", name="carga", tests=str(len(resultados)),
                       failures=str(sum(1 for r in resultados if r[2])), skipped="0", time=f"{a.duracion:.1f}")
    marcas = {}
    for nombre, pr, error in resultados:
        caso = ET.SubElement(suite, "testcase", classname="carga", name=nombre, time="0")
        if error:
            ET.SubElement(caso, "failure", message=error)
        marcas[f"carga::{nombre}"] = {"marcas": {"pr": [pr]}, "resultado": "fallida" if error else "pasada",
                                       "duracion_s": 0.0}
    raiz = ET.Element("testsuites"); raiz.append(suite)
    ET.ElementTree(raiz).write(a.junit, encoding="utf-8", xml_declaration=True)
    json.dump({"pruebas": marcas}, open(a.marcas, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
