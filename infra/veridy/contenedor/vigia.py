"""
Vigía de inactividad del grupo de Veridy en Azure Container Instances.

Lee el access.log de Veridy (volumen compartido) y, tras VERIDY_INACTIVIDAD_MIN minutos
sin uso, apaga el PostgreSQL y el propio grupo de contenedores con la identidad
administrada. Encender es manual (infra/veridy/veridy.sh encender).

"Uso" = una petición exitosa (2xx/3xx) a /api/ distinta de /api/health. Los bots que
recorren IPs públicas piden páginas sueltas o rutas inexistentes, pero no ejecutan la
aplicación, así que no la mantienen encendida.

Si existe /control/mantener_hasta con una fecha ISO futura (veridy.sh mantener), no apaga.
Solo usa la biblioteca estándar de Python.
"""
import json
import os
import re
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone

CLIENT_ID = os.environ["AZURE_CLIENT_ID"]
GRUPO_ID = os.environ["VERIDY_GRUPO_ID"]  # /subscriptions/.../containerGroups/<nombre>
PG_ID = os.environ["VERIDY_PG_ID"]        # /subscriptions/.../flexibleServers/<nombre>
LOG = os.environ.get("VERIDY_ACCESS_LOG", "/var/globaleaks/log/access.log")
MANTENER = os.environ.get("VERIDY_MANTENER", "/control/mantener_hasta")
INACTIVIDAD = int(os.environ.get("VERIDY_INACTIVIDAD_MIN", "60")) * 60
USO = re.compile(r'"[A-Z]+ /api/(?!health[ ?/])[^"]*" [23]\d\d ')


def decir(msg: str):
    print(f"{datetime.now(timezone.utc):%Y-%m-%dT%H:%M:%SZ} {msg}", flush=True)


def token() -> str:
    q = urllib.parse.urlencode({"api-version": "2018-02-01", "client_id": CLIENT_ID,
                                "resource": "https://management.azure.com/"})
    req = urllib.request.Request(f"http://169.254.169.254/metadata/identity/oauth2/token?{q}",
                                 headers={"Metadata": "true"})
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.load(r)["access_token"]


def detener(recurso_id: str, api: str):
    req = urllib.request.Request(f"https://management.azure.com{recurso_id}/stop?api-version={api}",
                                 data=b"", method="POST",
                                 headers={"Authorization": f"Bearer {token()}"})
    with urllib.request.urlopen(req, timeout=30) as r:
        decir(f"stop {recurso_id.rsplit('/', 1)[-1]}: HTTP {r.status}")


def mantener_activo() -> bool:
    try:
        with open(MANTENER) as f:
            hasta = datetime.fromisoformat(f.read().strip())
    except (OSError, ValueError):
        return False
    if hasta.tzinfo is None:
        hasta = hasta.replace(tzinfo=timezone.utc)
    return hasta > datetime.now(timezone.utc)


def main():
    ultimo_uso = time.time()  # el arranque cuenta como uso: quien lo enciende va a entrar
    posicion = 0
    decir(f"vigía activo: apaga tras {INACTIVIDAD // 60} min sin uso")
    while True:
        time.sleep(60)
        try:
            tam = os.path.getsize(LOG)
        except OSError:
            tam = 0
        if tam < posicion:  # el log se rotó
            posicion = 0
        if tam > posicion:
            with open(LOG, "rb") as f:
                f.seek(posicion)
                nuevo = f.read().decode(errors="replace")
                posicion = f.tell()
            if USO.search(nuevo):
                ultimo_uso = time.time()

        if mantener_activo():
            continue
        if time.time() - ultimo_uso >= INACTIVIDAD:
            decir(f"{INACTIVIDAD // 60} min sin uso: apagando PostgreSQL y el grupo")
            try:
                detener(PG_ID, "2022-12-01")
            except Exception as e:
                decir(f"ERROR al apagar PostgreSQL: {e}")
            try:
                detener(GRUPO_ID, "2023-05-01")  # detiene también a este contenedor
            except Exception as e:
                decir(f"ERROR al apagar el grupo: {e}")
            time.sleep(300)


if __name__ == "__main__":
    main()
