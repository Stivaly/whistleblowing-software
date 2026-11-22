"""Mide las denuncias de la demo del panel contra el código real del núcleo (lo lanza medir_demo_denuncias.sh, que pone las claves en el entorno).

Levanta el núcleo en 127.0.0.1 con la configuración KERNA_* del bloque `nucleo_entorno` de infra/terraform/terraform.tfvars y manda cada caso por HTTP con
el cliente del front (`app.demo_denuncias`): token OAuth, POST /v1/casos y GET /v1/casos/{ref}/sugerencia. Guarda ids, leyes, tiempos y la
comparación esperado/obtenido en evaluacion/registro/demo_denuncias_<fecha>.json. No guarda ni imprime el texto de las denuncias.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import socket
import subprocess
import sys
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
TFVARS = RAIZ.parent / "infra" / "terraform" / "terraform.tfvars"
SECRETO_LOCAL = "clave-local-de-medicion"
ID_CLIENTE = "demo-panel-dev"


def entorno_desplegado() -> dict:
    """Variables KERNA_* del núcleo desplegado: el bloque nucleo_entorno del tfvars (pares «NOMBRE = "valor"»)."""
    out, dentro = {}, False
    for linea in TFVARS.read_text().splitlines():
        if re.match(r"\s*nucleo_entorno\s*=\s*\{", linea):
            dentro = True
            continue
        if dentro and linea.strip() == "}":
            break
        m = re.match(r'\s*([A-Z0-9_]+)\s*=\s*"(.*)"\s*$', linea)
        if dentro and m:
            out[m.group(1)] = json.loads('"' + m.group(2) + '"')
    return out


def commit() -> str:
    c = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=RAIZ, capture_output=True, text=True).stdout.strip()
    sucio = subprocess.run(["git", "status", "--porcelain", "--", "nucleo", "comun"], cwd=RAIZ, capture_output=True, text=True).stdout.strip()
    return c + ("+cambios" if sucio else "")


def levantar_nucleo() -> str:
    import uvicorn
    from kerna_nucleo.api import crear_app
    from kerna_nucleo.config import Config
    os.environ["KERNA_CLIENTES"] = json.dumps({ID_CLIENTE: {"secreto_sha256": hashlib.sha256(SECRETO_LOCAL.encode()).hexdigest(), "cliente": "demo-panel"}})
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    puerto = s.getsockname()[1]
    s.close()
    srv = uvicorn.Server(uvicorn.Config(crear_app(Config.desde_entorno()), host="127.0.0.1", port=puerto, log_level="warning"))
    threading.Thread(target=srv.run, daemon=True).start()
    for _ in range(100):
        try:
            socket.create_connection(("127.0.0.1", puerto), timeout=0.2).close()
            break
        except OSError:
            time.sleep(0.1)
    return f"http://127.0.0.1:{puerto}"


def correr(caso: dict, dd, limite_s: float) -> dict:
    t0 = time.time()
    ref = str(uuid.uuid4())
    base = {"id": caso["id"], "tipo": caso["tipo"]}
    try:
        dd.enviar_caso(ref, caso["texto"])
        while True:
            resp = dd.consultar(ref)
            if resp is None or resp.get("estado") != "pendiente":
                break
            if time.time() - t0 > limite_s:
                return {**base, "estado": "sin_respuesta", "segundos": round(time.time() - t0, 1)}
            time.sleep(3)
    except dd.NucleoNoDisponible as e:
        return {**base, "estado": "sin_nucleo", "motivo": e.motivo, "segundos": round(time.time() - t0, 1)}
    v = dd.vista_resultado(resp or {"estado": "completada", "articulos": []}, caso)
    return {**base, "estado": v["estado"], "motivo": v["motivo"], "modo": v["modo"], "segundos": round(time.time() - t0, 1),
            "comparacion": v["comparacion"], "detalle": v["detalle"], "vetados": v["vetados"],
            "obtenidos": [{"id": a["id"], "ley": a["ley"], "coincide": a["coincide"], "veredicto": a["veredicto"], "confianza": a["confianza"]} for a in v["articulos"]],
            "esperados": [a["id"] for a in v["esperado"]["articulos"]], "fuera": v["esperado"]["fuera"]}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--concurrencia", type=int, default=3)
    ap.add_argument("--casos", nargs="*", default=[])
    ap.add_argument("--etiqueta", default="")
    ap.add_argument("--limite", type=float, default=480)
    a = ap.parse_args()
    env = entorno_desplegado()
    os.environ.update(env)
    url = levantar_nucleo()
    os.environ.update(KERNA_NUCLEO_URL=url, DEMO_CLIENT_ID=ID_CLIENTE, DEMO_CLIENT_SECRET=SECRETO_LOCAL)
    from app import demo_denuncias as dd
    from app.demo_denuncias_casos import CASOS
    casos = [c for c in CASOS if not a.casos or c["id"] in a.casos]
    t0 = time.time()
    with ThreadPoolExecutor(max(1, a.concurrencia)) as ex:
        res = list(ex.map(lambda c: correr(c, dd, a.limite), casos))
    ahora = datetime.now(timezone.utc)
    con = [r for r in res if r.get("comparacion")]
    resumen = {"casos": len(res), "coinciden": sum(r["comparacion"] == "coincide" for r in con), "difieren": sum(r["comparacion"] == "difiere" for r in con),
               "sin_respuesta": sum(r["estado"] in ("sin_respuesta", "sin_nucleo") for r in res)}
    salida = {"fecha": ahora.strftime("%Y-%m-%dT%H:%M:%SZ"), "commit": commit(), "etiqueta": a.etiqueta,
              "medicion": "denuncias de la demo del panel contra el núcleo (código local, configuración y APIs del desplegado)",
              "parametros": {"comando": "kerna/operaciones/medir_demo_denuncias.sh " + " ".join(sys.argv[1:]), "concurrencia": a.concurrencia,
                             "entorno_nucleo": {k: v for k, v in env.items() if k != "KERNA_LOCAL_URL"}, "texto": "relato completo con datos personales; el núcleo lo anonimiza",
                             "criterio_coincide": "al menos un artículo sugerido (sin vetar) está entre los esperados; en las de fuera del corpus, que no haya sugerencia"},
              "duracion_s": round(time.time() - t0, 1), "resumen": resumen, "casos": res}
    destino = RAIZ / "evaluacion" / "registro" / f"demo_denuncias_{ahora:%Y%m%d_%H%M}{('_' + a.etiqueta) if a.etiqueta else ''}.json"
    destino.write_text(json.dumps(salida, ensure_ascii=False, indent=1) + "\n")
    print(json.dumps(resumen, ensure_ascii=False), "->", destino.relative_to(RAIZ))
    for r in res:
        print(f"{r['id']:28} {r['estado']:14} {r.get('comparacion') or '-':9} {r['segundos']:6.1f}s", [(o["id"].split("-art-")[-1], o["ley"]) for o in r.get("obtenidos", [])])
    return 0


if __name__ == "__main__":
    sys.exit(main())
