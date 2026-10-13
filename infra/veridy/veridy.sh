#!/usr/bin/env bash
# Enciende, apaga y consulta Veridy en Azure (contenedor + PostgreSQL).
#
# Uso (desde cualquier carpeta del repo):
#   infra/veridy/veridy.sh encender          enciende PostgreSQL y luego Veridy; muestra el link (hasta 3 min)
#   infra/veridy/veridy.sh apagar            apaga Veridy y PostgreSQL
#   infra/veridy/veridy.sh estado            estado de ambos y el link
#   infra/veridy/veridy.sh mantener 3d       no apagar por inactividad durante 3 días (también 12h, 90m)
#   infra/veridy/veridy.sh mantener no       vuelve al apagado por inactividad
#   infra/veridy/veridy.sh logs [veridy|vigia|puertos]   registros del contenedor
#
# El apagado es automático: el vigía del grupo apaga todo tras 60 min sin uso
# (variable inactividad_min de Terraform). Encender es siempre manual.
#
# Requisitos: Azure CLI con sesión iniciada (si responde AADSTS50076, repetir az login)
# y Terraform aplicado en infra/veridy/terraform (de ahí se leen los nombres).
set -euo pipefail

TF="$(git -C "$(dirname "$0")" rev-parse --show-toplevel)/infra/veridy/terraform"
salida() { terraform -chdir="$TF" output -raw "$1"; }

RG="$(salida grupo_recursos)"
ACI="$(salida contenedor)"
PG="$(salida postgres_nombre)"

estado_pg()  { az postgres flexible-server show -g "$RG" -n "$PG" --query state -o tsv --only-show-errors; }
estado_aci() { az container show -g "$RG" -n "$ACI" --query "instanceView.state" -o tsv --only-show-errors 2>/dev/null || echo "NoCreado"; }
url()        { az container show -g "$RG" -n "$ACI" --query "ipAddress.fqdn" -o tsv --only-show-errors 2>/dev/null | sed 's#^#https://#'; }

# Encender y apagar no toman más de 3 minutos: la espera se corta ahí.
LIMITE=180

encender() {
  local fin=$(( $(date +%s) + LIMITE ))
  if [ "$(estado_pg)" != "Ready" ]; then
    echo "==> Encendiendo PostgreSQL"
    az postgres flexible-server start -g "$RG" -n "$PG" --only-show-errors -o none
  fi
  echo "==> Encendiendo Veridy"
  az container start -g "$RG" -n "$ACI" --only-show-errors -o none
  echo "==> Esperando que responda"
  local u; u="$(url)"
  until curl -s -o /dev/null -w '%{http_code}' --max-time 5 "$u/api/health" 2>/dev/null | grep -q 200; do
    [ "$(date +%s)" -ge "$fin" ] && { echo "Aún no responde tras 3 min: revisar con 'veridy.sh logs'."; break; }
    sleep 5
  done
  estado
}

apagar() {
  echo "==> Apagando Veridy"
  az container stop -g "$RG" -n "$ACI" --only-show-errors -o none || true
  echo "==> Apagando PostgreSQL"
  az postgres flexible-server stop -g "$RG" -n "$PG" --only-show-errors -o none || true
  estado
}

estado() {
  echo "Veridy:     $(estado_aci)"
  echo "PostgreSQL: $(estado_pg)"
  echo "Link:       $(url)"
  local h; h="$(leer_mantener)"
  [ -n "$h" ] && echo "Mantener encendido hasta: $h (UTC)"
  return 0
}

ST() { salida storage_nombre; }

leer_mantener() {
  az storage file download --account-name "$(ST)" --share-name control --path mantener_hasta \
    --dest /dev/stdout --only-show-errors 2>/dev/null | tr -d '\n' || true
}

mantener() {
  local arg="${1:?indicar duración (3d, 12h, 90m) o no}" hasta tmp
  tmp="$(mktemp)"
  if [ "$arg" = "no" ]; then
    hasta="1970-01-01T00:00:00+00:00"
  else
    local n="${arg%[dhm]}" u="${arg: -1}"
    case "$u" in d) u=days ;; h) u=hours ;; m) u=minutes ;; *) echo "duración inválida: $arg" >&2; exit 2 ;; esac
    hasta="$(date -u -d "+$n $u" +%Y-%m-%dT%H:%M:%S+00:00)"
  fi
  printf '%s' "$hasta" > "$tmp"
  az storage file upload --account-name "$(ST)" --share-name control --path mantener_hasta \
    --source "$tmp" --only-show-errors -o none
  : > "$tmp"
  [ "$arg" = "no" ] && echo "Vuelve el apagado por inactividad." || echo "No se apagará por inactividad hasta $hasta (UTC)."
}

case "${1:-}" in
  encender) encender ;;
  apagar)   apagar ;;
  estado)   estado ;;
  mantener) mantener "${2:-}" ;;
  logs)     az container logs -g "$RG" -n "$ACI" --container-name "${2:-veridy}" ;;
  *)        sed -n '2,13p' "$0"; exit 2 ;;
esac
