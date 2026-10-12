#!/usr/bin/env bash
# Enciende y apaga el PostgreSQL de Veridy en Azure según el uso real de Veridy.
#
# Uso:
#   infra/scripts/veridy_bd.sh estado          estado del servidor (Ready, Stopped, Starting, Stopping...)
#   infra/scripts/veridy_bd.sh encender        lo enciende y espera a que quede Ready (1-5 min)
#   infra/scripts/veridy_bd.sh apagar          lo apaga (sigue cobrando solo el almacenamiento)
#   infra/scripts/veridy_bd.sh inactividad     minutos desde la última petición real a Veridy
#   infra/scripts/veridy_bd.sh cron            lo que corre cron cada minuto (ver abajo)
#   infra/scripts/veridy_bd.sh instalar-cron   agrega la línea al crontab del usuario (idempotente)
#
# Regla del cron:
#   - Apaga el servidor si Veridy lleva VERIDY_BD_INACTIVIDAD_MIN minutos (60) sin peticiones.
#   - Lo enciende si hubo una petición en los últimos VERIDY_BD_DESPERTAR_MIN minutos (3) y está apagado:
#     quien entra a Veridy con la base apagada ve un error, y al minuto siguiente la base ya está arrancando.
#   - Azure vuelve a encender solo un servidor detenido 7 días; el cron lo apaga de nuevo si sigue sin uso.
#
# "Petición real" = una línea de access.log de Veridy que no sea el healthcheck (/api/health).
# La actividad de la base no sirve como señal: los jobs de Veridy la consultan cada 5 segundos.
#
# Requisitos: Azure CLI con sesión iniciada (si pide MFA, AADSTS50076: repetir az login) y Docker.
# Configuración (variables de entorno o ~/.config/veridy-bd.env, que el script crea la primera vez):
#   VERIDY_PG_SERVIDOR, VERIDY_PG_GRUPO   nombre y grupo del servidor (se leen de terraform output)
#   VERIDY_CONTENEDOR                     contenedor de Veridy (veridy)
#   VERIDY_ACCESS_LOG                     ruta del access.log dentro del contenedor
set -euo pipefail

RAIZ="$(git -C "$(dirname "$0")" rev-parse --show-toplevel)"
CONF="${XDG_CONFIG_HOME:-$HOME/.config}/veridy-bd.env"
ESTADO_DIR="${XDG_STATE_HOME:-$HOME/.local/state}/veridy-bd"
LOG="$ESTADO_DIR/veridy-bd.log"
mkdir -p "$ESTADO_DIR"

[ -f "$CONF" ] && . "$CONF"
VERIDY_CONTENEDOR="${VERIDY_CONTENEDOR:-veridy}"
VERIDY_ACCESS_LOG="${VERIDY_ACCESS_LOG:-/var/globaleaks/log/access.log}"
VERIDY_BD_INACTIVIDAD_MIN="${VERIDY_BD_INACTIVIDAD_MIN:-60}"
VERIDY_BD_DESPERTAR_MIN="${VERIDY_BD_DESPERTAR_MIN:-3}"

registrar() { echo "$(date -u +%FT%TZ) $*" >> "$LOG"; }

configurar() {
  if [ -z "${VERIDY_PG_SERVIDOR:-}" ] || [ -z "${VERIDY_PG_GRUPO:-}" ]; then
    local fqdn
    fqdn="$(terraform -chdir="$RAIZ/infra/terraform" output -raw postgres_servidor)"
    VERIDY_PG_SERVIDOR="${fqdn%%.*}"
    VERIDY_PG_GRUPO="$(terraform -chdir="$RAIZ/infra/terraform" output -raw grupo_recursos)"
    mkdir -p "$(dirname "$CONF")"
    printf 'VERIDY_PG_SERVIDOR=%s\nVERIDY_PG_GRUPO=%s\n' "$VERIDY_PG_SERVIDOR" "$VERIDY_PG_GRUPO" > "$CONF"
  fi
}

estado() {
  configurar
  az postgres flexible-server show -g "$VERIDY_PG_GRUPO" -n "$VERIDY_PG_SERVIDOR" \
    --query state -o tsv --only-show-errors
}

# Minutos desde la última petición real; vacío si no se puede leer el log
# (contenedor detenido o sin peticiones registradas).
inactividad() {
  local linea fecha
  linea="$(docker exec "$VERIDY_CONTENEDOR" tail -n 20000 "$VERIDY_ACCESS_LOG" 2>/dev/null \
           | grep -v '"GET /api/health ' | tail -n 1)" || true
  fecha="$(sed -n 's/^[^[]*\[\([^]]*\)\].*/\1/p' <<< "$linea")"
  [ -n "$fecha" ] || return 0
  # 12/Oct/2026:22:12:00 +0000  ->  12 Oct 2026 22:12:00 +0000
  fecha="$(sed 's#/# #g; s#:# #' <<< "$fecha")"
  echo $(( ( $(date +%s) - $(date -d "$fecha" +%s) ) / 60 ))
}

# Último estado conocido, para no consultar Azure cada minuto.
cache_leer() {  # $1 = estado esperado, $2 = vigencia en minutos
  local f="$ESTADO_DIR/estado"
  [ -f "$f" ] && [ "$(cat "$f")" = "$1" ] && [ -n "$(find "$f" -mmin "-$2")" ]
}
cache_guardar() { echo "$1" > "$ESTADO_DIR/estado"; }

cron() {
  exec 9> "$ESTADO_DIR/lock"
  flock -n 9 || exit 0

  local min st
  min="$(inactividad)"

  if [ -n "$min" ] && [ "$min" -lt "$VERIDY_BD_DESPERTAR_MIN" ]; then
    cache_leer Ready 10 && return 0
    st="$(estado)" || { registrar "ERROR al consultar el estado (¿az login?)"; return 1; }
    case "$st" in
      Stopped)
        registrar "encendiendo: petición hace $min min con la base detenida"
        az postgres flexible-server start -g "$VERIDY_PG_GRUPO" -n "$VERIDY_PG_SERVIDOR" \
          --no-wait --only-show-errors >> "$LOG" 2>&1 || registrar "ERROR al encender"
        cache_guardar Starting ;;
      *) cache_guardar "$st" ;;
    esac
  elif [ -z "$min" ] || [ "$min" -ge "$VERIDY_BD_INACTIVIDAD_MIN" ]; then
    cache_leer Stopped 60 && return 0
    st="$(estado)" || { registrar "ERROR al consultar el estado (¿az login?)"; return 1; }
    case "$st" in
      Ready)
        if [ -n "$min" ]; then registrar "apagando: $min minutos sin peticiones a Veridy"
        else registrar "apagando: Veridy sin peticiones registradas o detenido"; fi
        az postgres flexible-server stop -g "$VERIDY_PG_GRUPO" -n "$VERIDY_PG_SERVIDOR" \
          --no-wait --only-show-errors >> "$LOG" 2>&1 || registrar "ERROR al apagar"
        cache_guardar Stopping ;;
      *) cache_guardar "$st" ;;
    esac
  fi
}

instalar_cron() {
  local linea="* * * * * $RAIZ/infra/scripts/veridy_bd.sh cron >/dev/null 2>&1"
  if crontab -l 2>/dev/null | grep -qF "veridy_bd.sh cron"; then
    echo "Ya estaba en el crontab."
  else
    { crontab -l 2>/dev/null || true; echo "$linea"; } | crontab -
    echo "Agregado: $linea"
  fi
  echo "Registro: $LOG"
}

case "${1:-}" in
  estado)        estado ;;
  encender)      configurar
                 az postgres flexible-server start -g "$VERIDY_PG_GRUPO" -n "$VERIDY_PG_SERVIDOR" --only-show-errors -o none
                 registrar "encendido a mano"; cache_guardar Ready; estado ;;
  apagar)        configurar
                 az postgres flexible-server stop -g "$VERIDY_PG_GRUPO" -n "$VERIDY_PG_SERVIDOR" --only-show-errors -o none
                 registrar "apagado a mano"; cache_guardar Stopped; estado ;;
  inactividad)   m="$(inactividad)"; echo "${m:-sin peticiones registradas (o contenedor $VERIDY_CONTENEDOR detenido)}" ;;
  cron)          cron ;;
  instalar-cron) instalar_cron ;;
  *)             sed -n '2,10p' "$0"; exit 2 ;;
esac
