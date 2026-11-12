#!/usr/bin/env python3
"""Siembra las tablas `clientes` y `usodiario` del núcleo. Idempotente (upsert).

- Veridy (cliente real `veridy-dev`): su uso diario se calcula desde las tablas reales solicitud, valoracion y clasificacion.
- Clientes de demostración: 90 días de uso verosímil, determinista por (cliente, día), con días hábiles.
- Tarifas en UF por año de contrato: el precio anual del plan del capítulo 25 del informe de Kerna (kerna/front/app/finanzas.py),
  convertido con la UF de los parámetros. Los costos y la proyección los calcula el front con esos mismos parámetros.
Requiere az login con Storage Table Data Contributor. Uso: python3 kerna/front/sembrar_negocio.py [--url URL]
"""
from __future__ import annotations

import argparse
import random
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from app import finanzas  # noqa: E402
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone

VERIDY = "veridy-dev"
CLIENTES = [  # id, nombre, rubro, plan/mes, plan comercial, alta, base diaria (hábil), comportamiento
    ("veridy-dev", "Veridy", "Plataforma de denuncias", 200, "plataforma", "2026-10-01", 0, "real"),
    ("minera-altos-maipo", "Minera Altos del Maipo SpA", "Minería", 400, "pro", "2026-06-15", 17, "normal"),
    ("coop-valle-central", "Cooperativa Agrícola Valle Central", "Agroindustria", 150, "basico", "2026-07-20", 9, "sobre"),
    ("retail-austral", "Retail Austral S.A.", "Retail", 250, "pro", "2026-08-03", 11, "riesgo"),
    ("clinica-los-andes", "Clínica Los Andes Salud", "Salud", 100, "basico", "2026-09-10", 4, "normal"),
]
DIAS = 90


def _url(arg):
    return arg or subprocess.check_output(["terraform", "-chdir=" + str(Path(__file__).resolve().parents[2] / "infra/terraform"), "output", "-raw", "nucleo_tablas_url"], text=True).strip()


def uso_demo(cid: str, base: float, modo: str, hoy: date) -> list[dict]:
    filas = []
    for i in range(DIAS):
        d = hoy - timedelta(days=DIAS - 1 - i)
        r = random.Random(f"{cid}|{d}")
        f = 1.0 if d.weekday() < 5 else 0.08          # días hábiles
        f *= 0.8 + 0.4 * (i / DIAS)                    # crecimiento suave
        if modo == "sobre":
            f *= 1.3
        n = int(round(base * f * r.uniform(0.6, 1.4))) if r.random() < (0.97 if d.weekday() < 5 else 0.25) else 0
        if modo == "riesgo" and d > hoy - timedelta(days=12):
            n = 0
        sug = sum(r.random() < 0.88 for _ in range(n))
        val = sum(r.random() < 0.2 for _ in range(sug))
        uti = sum(r.random() < 0.75 for _ in range(val))
        mini = sum(r.random() < 0.4 for _ in range(sug))
        filas.append({"dia": d.isoformat(), "denuncias": n, "con_sugerencia": sug, "valoradas": val, "utiles": uti,
                      "nano_in": sug * r.randint(5500, 7500), "nano_out": sug * r.randint(1200, 1800),
                      "mini_in": mini * r.randint(2500, 3800), "mini_out": mini * r.randint(700, 1100)})
    return filas


def uso_real(svc) -> list[dict]:
    """Veridy: agrega solicitud, valoracion y clasificacion reales por día UTC. Sin textos."""
    sol = [dict(e) for e in svc.get_table_client("solicitud").query_entities(f"PartitionKey eq '{VERIDY}'")]
    por_id = {s["id_solicitud"]: s for s in sol}
    util = defaultdict(set)
    for e in svc.get_table_client("valoracion").list_entities():
        if e["PartitionKey"] in por_id:
            util[e["PartitionKey"]].add(e.get("valoracion"))
    dias: dict[str, dict] = defaultdict(lambda: defaultdict(int))
    for s in sol:
        d = datetime.fromtimestamp(float(s["creada_en"]), timezone.utc).date().isoformat()
        x = dias[d]
        x["denuncias"] += 1
        if s.get("estado") == "completada":
            x["con_sugerencia"] += 1
            m = str(s.get("modelo") or "")
            k = "mini" if "mini" in m else "nano"
            x[k + "_in"] += int(s.get("tokens_entrada") or 0)
            x[k + "_out"] += int(s.get("tokens_salida") or 0)
        v = util.get(s["id_solicitud"])
        if v:
            x["valoradas"] += 1
            x["utiles"] += int("arriba" in v)
    return [{"dia": d, **dict(v)} for d, v in sorted(dias.items())]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="")
    a = ap.parse_args()
    from azure.data.tables import TableServiceClient
    from azure.identity import DefaultAzureCredential
    svc = TableServiceClient(endpoint=_url(a.url), credential=DefaultAzureCredential())
    cl, uso = svc.get_table_client("clientes"), svc.get_table_client("usodiario")
    hoy = datetime.now(timezone.utc).date()
    for cid, nombre, rubro, plan, plan_tipo, alta, base, modo in CLIENTES:
        tarifa = round(finanzas.a_uf(finanzas.precio_anual_clp(plan_tipo, 1)), 2)
        cl.upsert_entity({"PartitionKey": cid, "RowKey": "perfil", "nombre": nombre, "rubro": rubro, "plan_denuncias_mes": plan,
                          "plan_tipo": plan_tipo, "precio_anual_uf": tarifa, "origen_veridy": True, "fecha_alta": alta, "estado": "activo"})
        filas = uso_real(svc) if modo == "real" else uso_demo(cid, base, modo, hoy)
        for f in filas:
            dia = f.pop("dia")
            uso.upsert_entity({"PartitionKey": cid, "RowKey": dia, **{k: int(v) for k, v in f.items()}})
        print(f"{nombre}: {len(filas)} días")


if __name__ == "__main__":
    main()
