#!/usr/bin/env python3
"""Convierte la salida de `twisted.trial --reporter=bwverbose` (suite del backend de Veridy) a JUnit XML."""
import argparse
import re
import xml.etree.ElementTree as ET

LINEA = re.compile(r"^(\S+) \.\.\. \[(\w+)\]\s*$")
TOTAL = re.compile(r"^Ran (\d+) tests? in ([\d.]+)s")


def convertir(texto: str, nombre: str) -> ET.Element:
    suite = ET.Element("testsuite", name=nombre)
    cuentas = {"failures": 0, "errors": 0, "skipped": 0}
    tiempo = 0.0
    n = 0
    for linea in texto.splitlines():
        m = LINEA.match(linea)
        if m:
            completo, resultado = m.groups()
            modulo_clase, _, prueba = completo.rpartition(".")
            caso = ET.SubElement(suite, "testcase", classname=modulo_clase, name=prueba, time="0")
            n += 1
            if resultado in ("FAIL", "FAILURE"):
                ET.SubElement(caso, "failure", message="ver salida completa en el reporte")
                cuentas["failures"] += 1
            elif resultado == "ERROR":
                ET.SubElement(caso, "error", message="ver salida completa en el reporte")
                cuentas["errors"] += 1
            elif resultado in ("SKIPPED", "TODO"):
                ET.SubElement(caso, "skipped", message=resultado)
                cuentas["skipped"] += 1
            elif resultado not in ("OK", "SUCCESS"):   # resultado desconocido: nunca cuenta como aprobado
                ET.SubElement(caso, "error", message=f"resultado no reconocido: {resultado}")
                cuentas["errors"] += 1
            continue
        t = TOTAL.match(linea)
        if t:
            tiempo = float(t.group(2))
    suite.set("tests", str(n))
    suite.set("time", f"{tiempo:.2f}")
    for k, v in cuentas.items():
        suite.set(k, str(v))
    return suite


def main():
    p = argparse.ArgumentParser()
    p.add_argument("entrada")
    p.add_argument("salida")
    p.add_argument("--nombre", default="veridy")
    a = p.parse_args()
    with open(a.entrada, encoding="utf-8", errors="replace") as f:
        suite = convertir(f.read(), a.nombre)
    ET.ElementTree(ET.Element("testsuites")).write(a.salida)
    raiz = ET.Element("testsuites")
    raiz.append(suite)
    ET.ElementTree(raiz).write(a.salida, encoding="utf-8", xml_declaration=True)


if __name__ == "__main__":
    main()
