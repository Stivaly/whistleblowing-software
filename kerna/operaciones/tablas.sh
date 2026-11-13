#!/usr/bin/env bash
# Lee o escribe las tablas de Azure del núcleo (reintentosmanuales, ajustes, clientes, usodiario, ...) con tu sesión de az.
# Uso: kerna/operaciones/tablas.sh <comando>
#   ver <tabla> [filtro_odata]            filas de la tabla (ej.: ver clientes "PartitionKey eq 'kerna'")
#   solicitud                             atajo: la fila del pedido de reintento (estado solicitado/atendido, reintentados)
#   ajustes                               atajo: los ajustes guardados (fila kerna/actual)
#   escribir <tabla> <PK> <RK> campo=valor...   crea o reemplaza una fila; exige CONFIRMAR=si en el entorno
# Leer pide el rol "Storage Table Data Reader" y escribir "Contributor" sobre la cuenta; sin él responde 403.
set -euo pipefail
. "$(dirname "$0")/_comun.sh"
CMD="${1:-}"; [ -n "$CMD" ] || { sed -n 2,9p "$0"; exit 2; }; shift
CUENTA="$(tf_kerna nucleo_tablas_url | sed -E 's#https://([^.]+)\..*#\1#')"
base=(--account-name "$CUENTA" --auth-mode login --only-show-errors)
ver() { az storage entity query "${base[@]}" --table-name "$1" ${2:+--filter "$2"} -o json --query "items"; }
case "$CMD" in
  ver)       ver "${1:?falta la tabla}" "${2:-}" ;;
  solicitud) ver reintentosmanuales "PartitionKey eq 'kerna' and RowKey eq 'solicitud'" ;;
  ajustes)   ver ajustes "PartitionKey eq 'kerna' and RowKey eq 'actual'" ;;
  escribir)
    T="${1:?falta la tabla}"; PK="${2:?falta PartitionKey}"; RK="${3:?falta RowKey}"; shift 3
    [ "${CONFIRMAR:-}" = si ] || { echo "Escribe en la tabla real. Repite con CONFIRMAR=si para confirmar." >&2; exit 1; }
    az storage entity insert "${base[@]}" --table-name "$T" --if-exists replace --entity "PartitionKey=$PK" "RowKey=$RK" "$@" -o none
    echo "Fila $PK/$RK escrita en $T." ;;
  *) echo "comando desconocido: $CMD" >&2; exit 2 ;;
esac
