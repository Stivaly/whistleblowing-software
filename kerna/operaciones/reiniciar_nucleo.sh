#!/usr/bin/env bash
# Reinicia la revisión activa del núcleo (Container App) para que relea secretos como kerna-clientes.
set -euo pipefail
source "$(dirname "$0")/_comun.sh"
APP="$(az containerapp list -g "$RG" --query "[?contains(name,'nucleo')].name | [0]" -o tsv --only-show-errors)"
REV="$(az containerapp revision list -g "$RG" -n "$APP" --query "[?properties.active].name | [0]" -o tsv --only-show-errors)"
echo "Reiniciando $APP / $REV"
az containerapp revision restart -g "$RG" -n "$APP" --revision "$REV" --only-show-errors -o none
echo "Listo"
