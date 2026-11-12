#!/usr/bin/env bash
# Aplica los cambios de Terraform de Veridy o de Kerna con un solo comando.
#
# Uso (desde cualquier carpeta del repo):
#   infra/aplicar.sh veridy        init + plan; muestra el plan y pide confirmación antes de aplicar
#   infra/aplicar.sh kerna         igual, para infra/terraform
#   infra/aplicar.sh veridy -y     aplica sin preguntar
#
# Requisitos: Azure CLI con sesión iniciada (si responde AADSTS50076, repetir az login).
set -euo pipefail

RAIZ="$(git -C "$(dirname "$0")" rev-parse --show-toplevel)"
case "${1:-}" in
  veridy) TF="$RAIZ/infra/veridy/terraform" ;;
  kerna)  TF="$RAIZ/infra/terraform" ;;
  *) echo "Uso: infra/aplicar.sh veridy|kerna [-y]" >&2; exit 1 ;;
esac

if [ -f "$TF/backend.hcl" ]; then
  terraform -chdir="$TF" init -input=false -backend-config=backend.hcl >/dev/null
else
  terraform -chdir="$TF" init -input=false >/dev/null
fi

# Veridy: la contraseña del admin de PostgreSQL (write-only) se lee de Key Vault solo para este proceso.
if [ "$1" = "veridy" ] && [ -z "${TF_VAR_postgres_admin_password:-}" ]; then
  KV="$(terraform -chdir="$TF" output -raw key_vault_name 2>/dev/null || az keyvault list -g rg-veridy-dev --query '[0].name' -o tsv)"
  export TF_VAR_postgres_admin_password="$(az keyvault secret show --vault-name "$KV" --name veridy-db-admin-password --query value -o tsv)"
fi

# Veridy: telemetría del conector hacia el Application Insights de Kerna (si existe). Sin esto, el apply la vaciaría.
if [ "$1" = "veridy" ] && [ -z "${TF_VAR_kerna_appinsights_conexion:-}" ]; then
  export TF_VAR_kerna_appinsights_conexion="$(az monitor app-insights component show -g rg-kerna-dev -a appi-kerna-dev --query connectionString -o tsv 2>/dev/null || true)"
fi

PLAN="aplicar.tfplan"
set +e
terraform -chdir="$TF" plan -input=false -detailed-exitcode -out="$PLAN"
codigo=$?
set -e
case $codigo in
  0) echo "Sin cambios: nada que aplicar."; exit 0 ;;
  2) ;;
  *) echo "El plan falló." >&2; exit 1 ;;
esac

if [ "${2:-}" != "-y" ]; then
  read -r -p "¿Aplicar este plan? [s/N] " r
  [ "$r" = "s" ] || [ "$r" = "S" ] || { echo "Cancelado."; exit 0; }
fi
terraform -chdir="$TF" apply -input=false "$PLAN"
