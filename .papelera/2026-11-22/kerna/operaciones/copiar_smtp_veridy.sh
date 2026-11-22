#!/usr/bin/env bash
# Copia la cuenta SMTP de Veridy (tabla config) al Key Vault de Kerna: smtp-servidor, smtp-puerto, smtp-usuario,
# smtp-clave, smtp-remitente y smtp-seguridad. El correo del panel (kerna/front/app/correo.py) los lee de ahí.
# Enciende Veridy (necesita su PostgreSQL), lee la tabla config con el rol veridy_app, copia sin imprimir valores ni dejarlos
# en disco, y apaga Veridy al terminar. La IP pública de este equipo debe estar en postgres_ips_permitidas
# (infra/veridy/terraform/terraform.tfvars); si cambió, el script lo dice.
# Uso: kerna/operaciones/copiar_smtp_veridy.sh
set -euo pipefail
. "$(dirname "$0")/_comun.sh"
TFV="$RAIZ/infra/veridy/terraform"
VERIDY="$RAIZ/infra/veridy/veridy.sh"
trap '"$VERIDY" apagar >/dev/null' EXIT
"$VERIDY" encender >/dev/null
KV_VERIDY="$(terraform -chdir="$TFV" output -raw key_vault_nombre)" \
PG_HOST="$(terraform -chdir="$TFV" output -raw postgres_servidor)" \
KV_KERNA="$KV" python3 "$(dirname "$0")/copiar_smtp_veridy.py"
