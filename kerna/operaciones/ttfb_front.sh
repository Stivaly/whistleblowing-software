#!/usr/bin/env bash
# Mide el TTFB de /salud y de la portada: primera visita (frío, sin descartar) y 3 siguientes (caliente).
# Uso: kerna/operaciones/ttfb_front.sh   (no despierta el front antes: es para comprobar el ping)
set -euo pipefail
. "$(dirname "$0")/_comun.sh"
for ruta in /salud /; do
  for i in 1 2 3 4; do
    printf '%s visita %s (%s): ' "$ruta" "$i" "$([ "$i" = 1 ] && echo frío || echo caliente)"
    curl -s -o /dev/null --max-time 60 -w 'HTTP %{http_code}  TTFB %{time_starttransfer}s\n' "$FRONT_URL$ruta"
  done
done
