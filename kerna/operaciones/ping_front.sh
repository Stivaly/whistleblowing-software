#!/usr/bin/env bash
# Historial de ejecuciones del ping al front (Logic App de consumo, cada 15 min). Solo lectura.
# Uso: kerna/operaciones/ping_front.sh [N]   (últimas N ejecuciones, por defecto 12)
set -euo pipefail
. "$(dirname "$0")/_comun.sh"
N="${1:-12}"
SUB="$(az account show --query id -o tsv --only-show-errors)"
NOMBRE="$(tf_kerna ping_front_nombre)"
az rest --only-show-errors --method get \
  --url "https://management.azure.com/subscriptions/$SUB/resourceGroups/$RG/providers/Microsoft.Logic/workflows/$NOMBRE/runs?api-version=2016-06-01&\$top=$N" \
  --query "value[].{inicio:properties.startTime,fin:properties.endTime,estado:properties.status}" -o table
