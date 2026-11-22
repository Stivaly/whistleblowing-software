#!/usr/bin/env bash
# Envía UN correo «cuenta_creada» con datos de prueba a la dirección indicada, por el correo propio de Kerna (Azure
# Communication Services, infra/terraform/correo.tf). La cadena de conexión se lee del Key Vault a una variable del proceso
# (nunca se imprime). Imprime solo el resultado (True/False) y el código de entrega.
# Uso: kerna/operaciones/probar_correo.sh destinatario@dominio
set -euo pipefail
. "$(dirname "$0")/_comun.sh"
PARA="${1:?indica el destinatario: probar_correo.sh destinatario@dominio}"
export CORREO_ACS_CONEXION="$(az keyvault secret show --vault-name "$KV" -n correo-acs-conexion --query value -o tsv --only-show-errors)"
export CORREO_REMITENTE="$(tf_kerna correo_remitente)"
PARA="$PARA" PYTHONPATH="$RAIZ/kerna/front:$RAIZ/kerna/comun" python3 - <<'PY'
import os
from app import correo
ok = correo.enviar("cuenta_creada", os.environ["PARA"], dict(
    usuario="prueba.correo", nombre="Prueba de correo", rol="Invitado", clave_temporal="Prb-0000-Tmp-0000", url="https://app-kerna-dev-front-g6mzy.azurewebsites.net/acceso"))
print("enviado: %s, código: %s" % (ok, correo.ultimo_codigo))
PY
