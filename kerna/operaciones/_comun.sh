#!/usr/bin/env bash
# Funciones compartidas por los scripts de kerna/operaciones (se carga con `source`, no se ejecuta).
# Los nombres salen de Terraform (infra/terraform) y la clave del front de Key Vault; nada queda escrito en disco.
RAIZ="$(git -C "$(dirname "${BASH_SOURCE[0]}")" rev-parse --show-toplevel)"
TF_KERNA="$RAIZ/infra/terraform"
tf_kerna() { terraform -chdir="$TF_KERNA" output -raw "$1"; }
RG="${RG:-$(tf_kerna grupo_recursos)}"                         # rg-kerna-dev
KV="${KV:-$(tf_kerna key_vault_nombre)}"
FRONT_URL="${FRONT_URL:-$(tf_kerna front_url)}"
FRONT_APP="${FRONT_APP:-$(tf_kerna front_nombre)}"

# clave_front [anterior]: clave del panel (Key Vault front-clave-panel). "anterior" = la versión previa a la vigente.
clave_front() {
  if [ "${1:-}" = "anterior" ]; then
    local id; id="$(az keyvault secret list-versions --vault-name "$KV" -n front-clave-panel --only-show-errors \
      --query "sort_by([], &attributes.created)[-2].id" -o tsv)"
    [ -n "$id" ] || { echo "No hay una versión anterior de la clave." >&2; return 1; }
    az keyvault secret show --id "$id" --query value -o tsv --only-show-errors
  else
    az keyvault secret show --vault-name "$KV" -n front-clave-panel --query value -o tsv --only-show-errors
  fi
}
