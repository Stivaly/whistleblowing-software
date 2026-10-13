"""
Paso de arranque del contenedor de Veridy en Azure Container Instances.

Corre justo antes de Veridy, en el mismo contenedor, con la identidad administrada del grupo:
  1. Lee la contraseña de veridy_app desde Key Vault y la deja en un .pgpass (modo 600)
     dentro del contenedor, que se pierde al apagarlo. Así la contraseña no queda ni en
     el estado de Terraform ni en variables de entorno.
  2. Autoriza en el firewall de PostgreSQL la IP de salida actual del grupo: cambia
     cada vez que el grupo se enciende.

Solo usa la biblioteca estándar de Python. Variables: ver el bloque de abajo.
"""
import json
import os
import sys
import time
import urllib.parse
import urllib.request

CLIENT_ID = os.environ["AZURE_CLIENT_ID"]
KV_URL = os.environ["VERIDY_KV_URL"].rstrip("/")
PG_FQDN = os.environ["VERIDY_PG_FQDN"]
PG_ID = os.environ["VERIDY_PG_ID"]  # /subscriptions/.../flexibleServers/<nombre>
PGPASS = os.environ.get("VERIDY_PGPASS", "/tmp/pgpass")
REGLA = "aci-veridy"


def token(recurso: str) -> str:
    q = urllib.parse.urlencode({"api-version": "2018-02-01", "resource": recurso, "client_id": CLIENT_ID})
    req = urllib.request.Request(f"http://169.254.169.254/metadata/identity/oauth2/token?{q}",
                                 headers={"Metadata": "true"})
    for intento in range(10):
        try:
            with urllib.request.urlopen(req, timeout=10) as r:
                return json.load(r)["access_token"]
        except OSError as e:
            print(f"identidad no disponible aún ({e}); reintento", flush=True)
            time.sleep(3 * (intento + 1))
    sys.exit("no se obtuvo token de la identidad administrada")


def pedir(metodo: str, url: str, tok: str, cuerpo: dict | None = None) -> dict:
    datos = json.dumps(cuerpo).encode() if cuerpo is not None else None
    req = urllib.request.Request(url, data=datos, method=metodo,
                                 headers={"Authorization": f"Bearer {tok}",
                                          "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        texto = r.read()
        return json.loads(texto) if texto else {}


def escribir_pgpass():
    tok = token("https://vault.azure.net")
    clave = pedir("GET", f"{KV_URL}/secrets/veridy-db-app-password?api-version=7.4", tok)["value"]
    os.makedirs(os.path.dirname(PGPASS), exist_ok=True)
    fd = os.open(PGPASS, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write(f"{PG_FQDN}:5432:veridy:veridy_app:{clave}\n")
    if os.geteuid() == 0:  # con la imagen de Veridy ya corre como uid 1000
        os.chown(PGPASS, 1000, 1000)
    print("pgpass listo", flush=True)


def autorizar_ip():
    with urllib.request.urlopen("https://api.ipify.org", timeout=15) as r:
        ip = r.read().decode().strip()
    tok = token("https://management.azure.com/")
    url = f"https://management.azure.com{PG_ID}/firewallRules/{REGLA}?api-version=2022-12-01"
    pedir("PUT", url, tok, {"properties": {"startIpAddress": ip, "endIpAddress": ip}})
    print(f"firewall de PostgreSQL: {REGLA} = {ip}", flush=True)


if __name__ == "__main__":
    escribir_pgpass()
    try:
        autorizar_ip()
    except Exception as e:  # Veridy reintenta la conexión; el log deja la causa a la vista
        print(f"ERROR al autorizar la IP en el firewall: {e}", flush=True)
