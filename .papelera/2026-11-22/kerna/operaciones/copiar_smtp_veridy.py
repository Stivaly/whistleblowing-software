"""
Copia la configuración SMTP de Veridy (tabla config, tid 1) al Key Vault de Kerna como secretos.
Los valores pasan de la base al Key Vault por stdin de `az`: nunca se imprimen ni se escriben en disco.

Entorno (lo pone copiar_smtp_veridy.sh): PG_HOST, KV_VERIDY, KV_KERNA. Imprime solo los nombres copiados.
"""
import json
import os
import subprocess
import sys
import time

import psycopg2

# variable de Veridy -> secreto de Kerna
SECRETOS = {
    "smtp_server": "smtp-servidor",
    "smtp_port": "smtp-puerto",
    "smtp_username": "smtp-usuario",
    "smtp_password": "smtp-clave",
    "smtp_source_email": "smtp-remitente",
    "smtp_security": "smtp-seguridad",
}
FABRICA = {"smtp_server": "mail.globaleaks.org", "smtp_password": "globaleaks"}  # SMTP sin configurar en Veridy


def az(*args, entrada=None):
    r = subprocess.run(["az", *args, "--only-show-errors"], input=entrada, capture_output=True, text=True)
    if r.returncode:
        sys.exit("az falló (%s): no se muestra su salida porque podría traer valores." % " ".join(args[:3]))
    return r.stdout


def conectar(clave):
    # PostgreSQL tarda en aceptar conexiones tras encenderse: se reintenta hasta ~3 min
    fin = time.time() + 180
    while True:
        try:
            return psycopg2.connect(host=os.environ["PG_HOST"], dbname="veridy", user="veridy_app", password=clave,
                                    sslmode="require", connect_timeout=15)
        except psycopg2.OperationalError:
            if time.time() > fin:
                sys.exit("No hay conexión con la base de Veridy: ¿PostgreSQL encendido y la IP de este equipo en "
                         "postgres_ips_permitidas (infra/veridy/terraform/terraform.tfvars)?")
            time.sleep(10)


def leer_veridy():
    clave = az("keyvault", "secret", "show", "--vault-name", os.environ["KV_VERIDY"],
               "-n", "veridy-db-app-password", "--query", "value", "-o", "tsv").strip()
    con = conectar(clave)
    with con, con.cursor() as cur:
        cur.execute("select var_name, value from config where tid = 1 and var_name like 'smtp\\_%'")
        filas = cur.fetchall()
    con.close()
    datos = {}
    for var, v in filas:
        if isinstance(v, str):
            try:
                v = json.loads(v)
            except ValueError:
                pass
        datos[var] = v
    return datos


def main():
    datos = leer_veridy()
    faltan = [n for v, n in SECRETOS.items() if datos.get(v) in (None, "")]
    if faltan:
        sys.exit("Veridy no tiene guardado: %s" % ", ".join(faltan))
    if any(datos[v] == d for v, d in FABRICA.items()):
        sys.exit("Veridy tiene el SMTP de fábrica (sin configurar): nada que copiar.")
    for var, nombre in SECRETOS.items():
        az("keyvault", "secret", "set", "--vault-name", os.environ["KV_KERNA"], "-n", nombre,
           "--file", "/dev/stdin", "--encoding", "utf-8", "-o", "none", entrada=str(datos[var]))
    print("copiado: " + ", ".join(SECRETOS.values()))


main()
