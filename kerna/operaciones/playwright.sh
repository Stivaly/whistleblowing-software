#!/usr/bin/env bash
# Usa el contenedor Playwright (el mismo de medir_vistas.sh) para probar el front fuera de las mediciones.
# Uso: kerna/operaciones/playwright.sh <comando> [--clave-anterior]
#   pdf                         descarga el informe PDF con navegador       -> <salida>/informe.pdf
#   modal [--confirmar]         abre y captura el modal de reintento; con --confirmar envía el pedido REAL
#   script <archivo.py> [args]  corre tu propio script Playwright (recibe FRONT_URL, FRONT_CLAVE y /out como carpeta de salida)
#   shell                       consola interactiva dentro del contenedor (docker run -it)
# Salida (capturas y PDF): kerna/operaciones/salida/ (ignorada por git); el contenedor se descarta al terminar (--rm).
set -euo pipefail
. "$(dirname "$0")/_comun.sh"
AQUI="$(cd "$(dirname "$0")" && pwd)"; OUT="$AQUI/salida"; mkdir -p "$OUT"
IMG=mcr.microsoft.com/playwright/python:v1.64.0-noble
CMD="${1:-}"; [ -n "$CMD" ] || { sed -n 2,9p "$0"; exit 2; }; shift
VERSION=vigente; EXTRA=()
if [ "$CMD" = script ]; then PY="$(realpath "${1:?falta el archivo .py}")"; shift; fi
for a in "$@"; do if [ "$a" = --clave-anterior ]; then VERSION=anterior; else EXTRA+=("$a"); fi; done
CLAVE="$(clave_front "$VERSION")"
RUN=(docker run --rm --ipc=host --network host -e FRONT_CLAVE="$CLAVE" -e FRONT_URL="$FRONT_URL" -v "$AQUI:/h:ro" -v "$OUT:/out")
PRE="pip install -q --break-system-packages playwright==1.64.0 2>&1 | tail -1"; POST="chown -R $(id -u):$(id -g) /out"
case "$CMD" in
  pdf|modal) "${RUN[@]}" "$IMG" bash -c "$PRE; python /h/playwright_front.py $CMD '$FRONT_URL' /out ${EXTRA[*]:-}; $POST" ;;
  script)    "${RUN[@]}" -v "$PY:/s/script.py:ro" "$IMG" bash -c "$PRE; python /s/script.py ${EXTRA[*]:-}; $POST" ;;
  shell)     "${RUN[@]}" -it "$IMG" bash ;;
  *) echo "comando desconocido: $CMD" >&2; exit 2 ;;
esac
echo "Salida en $OUT"
