"""
Acceso temporal a MongoDB Atlas para los jobs del pipeline.

Container Apps no tiene IP de salida fija, así que cada ejecución autoriza la suya en la
lista de acceso del proyecto de Atlas (API de administración) y la quita al terminar:

  python3 atlas_acceso.py abrir    # agrega la IP de salida, con vencimiento, y espera a que esté activa
  python3 atlas_acceso.py cerrar   # quita la entrada que agregó "abrir"

La entrada lleva deleteAfterDate (ATLAS_ACCESO_HORAS, por defecto 2 h, más que el tiempo
máximo del job): si el job muere sin cerrar, Atlas la borra igual. Si la IP ya tiene una
entrada permanente, no se agrega ni se quita nada.

Variables: ATLAS_PUBLIC_KEY, ATLAS_PRIVATE_KEY (clave de API del proyecto, rol Project
Owner o Network Access Manager), ATLAS_PROJECT_ID. Solo biblioteca estándar.
"""
from __future__ import annotations

import json
import os
import socket
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

API = "https://cloud.mongodb.com/api/atlas/v2"
ACEPTA = "application/vnd.atlas.2023-01-01+json"
ESTADO = os.environ.get("ATLAS_ACCESO_ARCHIVO", "/tmp/atlas_acceso.json")
ESPERA_MAX = 120  # segundos hasta que la entrada quede ACTIVE


def _abridor() -> urllib.request.OpenerDirector:
    claves = urllib.request.HTTPPasswordMgrWithDefaultRealm()
    claves.add_password(None, "https://cloud.mongodb.com/",
                        os.environ["ATLAS_PUBLIC_KEY"], os.environ["ATLAS_PRIVATE_KEY"])
    return urllib.request.build_opener(urllib.request.HTTPDigestAuthHandler(claves))


def _pedir(metodo: str, ruta: str, cuerpo=None):
    """Devuelve (código HTTP, JSON). 404 no es error: la entrada no existe."""
    req = urllib.request.Request(f"{API}/groups/{os.environ['ATLAS_PROJECT_ID']}{ruta}", method=metodo,
                                 data=json.dumps(cuerpo).encode() if cuerpo is not None else None,
                                 headers={"Accept": ACEPTA, "Content-Type": ACEPTA})
    try:
        with _abridor().open(req, timeout=30) as r:
            texto = r.read()
            return r.status, json.loads(texto) if texto else {}
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return 404, {}
        detalle = e.read().decode(errors="replace")[:300]
        raise RuntimeError(f"Atlas {metodo} {ruta}: HTTP {e.code} {detalle}") from None


def ip_salida() -> str:
    with urllib.request.urlopen("https://api.ipify.org", timeout=15) as r:
        return r.read().decode().strip()


def _entrada(ip: str) -> str:
    return "/accessList/" + urllib.parse.quote(ip, safe="")


def abrir(ip: str | None = None) -> None:
    ip = ip or ip_salida()
    codigo, actual = _pedir("GET", _entrada(ip))
    if codigo == 200 and not actual.get("deleteAfterDate"):
        print(f"Atlas: {ip} ya tiene acceso permanente; no se agrega entrada temporal", flush=True)
        _guardar({"ip": ip, "temporal": False})
        return

    horas = float(os.environ.get("ATLAS_ACCESO_HORAS", "2"))
    vence = (datetime.now(timezone.utc) + timedelta(hours=horas)).strftime("%Y-%m-%dT%H:%M:%SZ")
    # El nombre del contenedor identifica la ejecución del job en el comentario.
    comentario = f"kerna job {os.environ.get('CONTAINER_APP_JOB_EXECUTION_NAME', socket.gethostname())}"[:80]
    _pedir("POST", "/accessList", [{"ipAddress": ip, "comment": comentario, "deleteAfterDate": vence}])
    _guardar({"ip": ip, "temporal": True})
    print(f"Atlas: acceso temporal para {ip} hasta {vence}", flush=True)

    limite = time.monotonic() + ESPERA_MAX
    while True:
        _, estado = _pedir("GET", _entrada(ip) + "/status")
        if estado.get("STATUS") == "ACTIVE":
            print("Atlas: entrada activa", flush=True)
            return
        if estado.get("STATUS") == "FAILED" or time.monotonic() > limite:
            raise RuntimeError(f"Atlas: la entrada de {ip} no quedó activa ({estado.get('STATUS')})")
        time.sleep(5)


def cerrar() -> None:
    try:
        with open(ESTADO) as f:
            estado = json.load(f)
    except FileNotFoundError:
        print("Atlas: no hay entrada temporal que quitar", flush=True)
        return
    if estado["temporal"]:
        codigo, _ = _pedir("DELETE", _entrada(estado["ip"]))
        print(f"Atlas: acceso temporal de {estado['ip']} quitado" if codigo != 404
              else f"Atlas: la entrada de {estado['ip']} ya no estaba", flush=True)
        _guardar({**estado, "temporal": False})  # un segundo "cerrar" no hace nada


def _guardar(estado: dict) -> None:
    with open(ESTADO, "w") as f:
        json.dump(estado, f)


if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in ("abrir", "cerrar"):
        sys.exit("uso: atlas_acceso.py abrir [--ip IP] | cerrar")
    if sys.argv[1] == "abrir":
        abrir(sys.argv[3] if sys.argv[2:3] == ["--ip"] else None)
    else:
        cerrar()
