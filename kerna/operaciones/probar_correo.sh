#!/usr/bin/env bash
# Envía UN correo «cuenta_creada» con datos de prueba a la dirección del remitente (la misma cuenta SMTP) para confirmar que el
# SMTP copiado de Veridy funciona. Lee los secretos smtp-* del Key Vault de Kerna a variables de entorno del proceso (nunca se
# imprimen ni se escriben). Imprime solo el resultado (True/False) y el código SMTP.
# Uso: kerna/operaciones/probar_correo.sh
set -euo pipefail
. "$(dirname "$0")/_comun.sh"
for par in servidor:SERVIDOR puerto:PUERTO usuario:USUARIO clave:CLAVE remitente:REMITENTE seguridad:SEGURIDAD; do
  export "SMTP_${par#*:}=$(az keyvault secret show --vault-name "$KV" -n "smtp-${par%%:*}" --query value -o tsv --only-show-errors)"
done
PYTHONPATH="$RAIZ/kerna/front" python3 - <<'PY'
import os
from app import correo
ok = correo.enviar("cuenta_creada", os.environ["SMTP_REMITENTE"], dict(
    usuario="prueba.correo", nombre="Prueba de correo", rol="Analista", clave_temporal="Prb-0000-Tmp-0000", url="https://kerna.ai/acceso"))
print("enviado: %s, código SMTP: %s" % (ok, correo.ultimo_codigo))
PY
