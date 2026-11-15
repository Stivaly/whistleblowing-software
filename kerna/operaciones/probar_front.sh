#!/usr/bin/env bash
# Prueba el front en producción con curl: portada, acceso (clave buena y mala), panel, pedido de reintento y PDF.
# Uso: kerna/operaciones/probar_front.sh [--clave-anterior] [--reintento]
#   --clave-anterior   usa la versión anterior de la clave en Key Vault (por defecto, la vigente)
#   --reintento        además envía el pedido de reintento REAL (escribe en la tabla reintentosmanuales)
# Sale con código 1 si algo falla. La clave nunca se imprime.
set -uo pipefail
. "$(dirname "$0")/_comun.sh"
VERSION=vigente; REINTENTO=0
for a in "$@"; do case "$a" in --clave-anterior) VERSION=anterior;; --reintento) REINTENTO=1;; *) echo "opción desconocida: $a" >&2; exit 2;; esac; done
CLAVE="$(clave_front "$VERSION")" || exit 1
JAR="$(mktemp)"; PDF="$(mktemp)"; trap 'rm -f "$JAR" "$PDF"' EXIT; FALLAS=0
c() { curl -sS --max-time 90 "$@"; }
ok() { echo "OK     $1"; }; mal() { echo "FALLA  $1"; FALLAS=$((FALLAS+1)); }
codigo() { c -o /dev/null -w '%{http_code}' "$@"; }

[ "$(codigo "$FRONT_URL/salud")" = 200 ] && ok "/salud responde 200" || mal "/salud no responde 200 (¿dormido? usa despertar_front.sh)"
[ "$(codigo -X POST -d clave=incorrecta "$FRONT_URL/acceso")" = 401 ] && ok "clave incorrecta rechazada (401)" || mal "clave incorrecta no dio 401"
[ "$(codigo "$FRONT_URL/panel")" = 303 ] && ok "/panel sin sesión redirige al acceso" || mal "/panel sin sesión no redirige"
R="$(codigo -c "$JAR" --data-urlencode "clave=$CLAVE" "$FRONT_URL/acceso")"
[ "$R" = 303 ] && grep -q kerna_panel "$JAR" && ok "login con la clave $VERSION (cookie de sesión)" || { mal "login con la clave $VERSION dio $R"; echo "Sin sesión no se puede seguir."; exit 1; }
HTML="$(c -b "$JAR" "$FRONT_URL/panel")"
[ -n "$HTML" ] && echo "$HTML" | grep -q 'id="rei"' && ok "/panel carga con la cola de reintentos" || mal "/panel no muestra la cola de reintentos"
CSRF="$(echo "$HTML" | sed -n 's/.*id="rei"[^>]*data-csrf="\([^"]*\)".*/\1/p' | head -1)"
if [ "$REINTENTO" = 1 ]; then
  if [ -z "$CSRF" ]; then mal "no se encontró el token del pedido de reintento"; else
    RESP="$(c -b "$JAR" -X POST -H 'Accept: application/json' -H "Origin: $FRONT_URL" --data-urlencode "csrf=$CSRF" "$FRONT_URL/panel/reintentar")"
    echo "$RESP" | grep -qE '"estado": ?"(solicitado|ya_solicitado)"' && ok "pedido de reintento: $RESP" || mal "pedido de reintento: $RESP"
  fi
else echo "OMITIDO pedido de reintento (usa --reintento para enviarlo de verdad)"; fi
T="$(c -b "$JAR" -o "$PDF" -w '%{http_code} %{content_type}' "$FRONT_URL/panel/informe/descargar.pdf?dias=7")"
[ "${T%% *}" = 200 ] && head -c4 "$PDF" | grep -q '%PDF' && ok "PDF descargado ($(wc -c <"$PDF") bytes, ${T#* })" || mal "descarga del PDF: $T $(head -c 300 "$PDF" | tr -d '\0' | tr '\n' ' ')"
[ "$FALLAS" = 0 ] && echo "Todo bien." || { echo "$FALLAS prueba(s) fallaron."; exit 1; }
