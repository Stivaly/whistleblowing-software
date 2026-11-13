#!/usr/bin/env bash
# Despierta el front (App Service F1 duerme a los 20 min) antes de medir; opcionalmente lo reinicia.
# Uso: kerna/operaciones/despertar_front.sh [--reiniciar]
#   sin opción: ping repetido a /salud hasta 200 (máx. 3 min), más dos pings de calentamiento
#   --reiniciar: antes hace az webapp restart
# Tras despertarlo, la primera visita se descarta: mide a partir de la segunda.
set -euo pipefail
. "$(dirname "$0")/_comun.sh"
if [ "${1:-}" = --reiniciar ]; then echo "==> az webapp restart $FRONT_APP"; az webapp restart -g "$RG" -n "$FRONT_APP" --only-show-errors; fi
fin=$(( $(date +%s) + 180 ))
until [ "$(curl -s -o /dev/null -w '%{http_code}' --max-time 20 "$FRONT_URL/salud" || true)" = 200 ]; do
  [ "$(date +%s)" -lt "$fin" ] || { echo "El front no respondió en 3 min." >&2; exit 1; }
  echo "   esperando..."; sleep 8
done
for i in 1 2; do curl -s -o /dev/null --max-time 20 "$FRONT_URL/salud"; done
echo "Front despierto: $FRONT_URL"
