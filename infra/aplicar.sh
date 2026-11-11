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
