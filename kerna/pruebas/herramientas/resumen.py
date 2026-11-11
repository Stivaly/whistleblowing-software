#!/usr/bin/env python3
"""Arma resumen.json de una corrida de scripts/probar.sh a partir de los junit-*.xml y marcas-*.json del reporte.

Uso: resumen.py <carpeta_reporte> --commit <hash> [--commit-completo <hash+cambios>] [--registro <carpeta>]
Imprime pocas líneas (una por capa más las fallidas) y sale con 1 si algo falla.
"""
from __future__ import annotations

import argparse
import datetime
import json
import pathlib
import shutil
import sys
import xml.etree.ElementTree as ET

from datos_hash import hash_datos

CAPAS = ("unitarias", "integracion", "e2e", "carga", "veridy")
RAIZ = pathlib.Path(__file__).resolve().parents[1]


def _suites(ruta: pathlib.Path):
    arbol = ET.parse(ruta).getroot()
    return [arbol] if arbol.tag == "testsuite" else list(arbol.iter("testsuite"))


def _leer_capa(carpeta: pathlib.Path, capa: str, base: dict) -> dict | None:
    junits = sorted(carpeta.glob(f"junit-{capa}*.xml"))
    errores = sorted(carpeta.glob(f"error-{capa}*.txt"))
    rcs = sorted(carpeta.glob(f"rc-{capa}*.txt"))
    if not junits and not errores and not rcs:
        return None
    r = {"total": 0, "pasadas": 0, "fallidas": 0, "omitidas": 0, "duracion_s": 0.0, "lista_fallidas": [],
         "conocidas": 0}
    marcas: dict[str, dict] = {}
    for m in carpeta.glob(f"marcas-{capa}*.json"):
        marcas.update(json.loads(m.read_text(encoding="utf-8")).get("pruebas", {}))
    fallidas: dict[str, dict] = {
        nodeid: {"nodeid": nodeid, "ids": d["marcas"], "duracion_s": d["duracion_s"]}
        for nodeid, d in marcas.items() if d["resultado"] == "fallida"}
    for j in junits:
        fallos_archivo: list[dict] = []
        for s in _suites(j):
            r["total"] += int(s.get("tests", 0))
            r["omitidas"] += int(s.get("skipped", 0))
            r["duracion_s"] += float(s.get("time", 0))
            for caso in s.iter("testcase"):
                if caso.find("failure") is None and caso.find("error") is None:
                    continue
                nombre = caso.get("name", "")
                clase = caso.get("classname", "")
                if capa == "veridy":
                    nodeid = f"{clase}.{nombre}"
                else:
                    nodeid = f"{clase}::{nombre}" if clase else nombre
                    if any(n.endswith("::" + nombre) for n in fallidas):
                        r["fallidas"] += 1
                        continue
                fallos_archivo.append({"nodeid": nodeid, "ids": {}, "duracion_s": float(caso.get("time", 0))})
        if capa == "veridy":
            # fallos previos conocidos (también en stable): no cuentan como regresión hasta el máximo acordado
            conocidas = [f for f in fallos_archivo
                         if any(f["nodeid"].startswith(p) for p in base.get("prefijos_conocidos", []))]
            if len(conocidas) <= base.get("maximo_conocidos", 0):
                r["conocidas"] += len(conocidas)
                fallos_archivo = [f for f in fallos_archivo if f not in conocidas]
        r["fallidas"] += len(fallos_archivo)
        for f in fallos_archivo:
            fallidas.setdefault(f["nodeid"] if capa != "veridy" else f"{j.stem}:{f['nodeid']}", f)
    r["pasadas"] = max(r["total"] - r["fallidas"] - r["omitidas"] - r["conocidas"], 0)
    r["duracion_s"] = round(r["duracion_s"], 1)
    r["lista_fallidas"] = sorted(fallidas.values(), key=lambda x: x["nodeid"])
    # la lista puede quedar con menos entradas que el contador (nombres repetidos): el contador manda
    r["error"] = None
    for e in errores:
        r["error"] = e.read_text(encoding="utf-8").strip()[:300]
    if r["error"] is None:
        for rc in rcs:
            codigo = rc.read_text().strip()
            if codigo not in ("0", "1"):
                r["error"] = f"pytest/herramienta terminó con código {codigo} ({rc.stem})"
            elif codigo == "1" and r["total"] == 0:   # falló antes de producir resultados: no es un «ok» vacío
                r["error"] = f"la herramienta terminó con código 1 sin resultados ({rc.stem}); ver su salida"
    r["estado"] = "error" if r["error"] else ("falla" if r["fallidas"] else "ok")
    return r


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("carpeta")
    p.add_argument("--commit", required=True)
    p.add_argument("--commit-completo")
    p.add_argument("--registro")
    a = p.parse_args()
    carpeta = pathlib.Path(a.carpeta)
    base = json.loads((RAIZ / "datos" / "base_veridy.json").read_text(encoding="utf-8"))
    capas = {c: r for c in CAPAS if (r := _leer_capa(carpeta, c, base)) is not None}
    ahora = datetime.datetime.now(datetime.timezone.utc)
    resumen = {
        "commit": a.commit_completo or a.commit,
        "fecha_utc": ahora.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "sha256_datos": hash_datos(RAIZ / "datos"),
        "capas": capas,
        "ok": bool(capas) and all(c["estado"] == "ok" for c in capas.values()),
    }
    (carpeta / "resumen.json").write_text(json.dumps(resumen, ensure_ascii=False, indent=2), encoding="utf-8")
    if a.registro:
        destino = pathlib.Path(a.registro)
        destino.mkdir(parents=True, exist_ok=True)
        shutil.copy(carpeta / "resumen.json", destino / f"pruebas-{carpeta.name}.json")

    for nombre, c in capas.items():
        extra = f", {c['conocidas']} conocidas" if c["conocidas"] else ""
        linea = (f"{nombre:<11} {c['estado'].upper():<5} {c['total']} pruebas: {c['pasadas']} pasadas, "
                 f"{c['fallidas']} fallidas, {c['omitidas']} omitidas{extra} ({c['duracion_s']} s)")
        print(linea + (f" - {c['error']}" if c["error"] else ""))
        for f in c["lista_fallidas"][:10]:
            ids = ",".join(i for v in f["ids"].values() for i in v)
            print(f"  FALLA {f['nodeid']}" + (f" [{ids}]" if ids else ""))
        if len(c["lista_fallidas"]) > 10:
            print(f"  ... y {len(c['lista_fallidas']) - 10} más en resumen.json")
    if not capas:
        print("Sin resultados de ninguna capa.")
    print(f"Reporte: {carpeta}")
    return 0 if resumen["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
