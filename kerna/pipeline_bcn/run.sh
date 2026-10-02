#!/bin/sh
# Punto de entrada del contenedor. Uso: run.sh diario | semanal | vigencia-21719 | extraer [args] | embed [args]
set -e
modo="${1:-diario}"
[ $# -gt 0 ] && shift

case "$modo" in
  diario)          python extraer_bcn.py && python embed_sync.py ;;
  semanal)         python extraer_bcn.py --forzar && python embed_sync.py ;;
  # 1 de diciembre: la Ley 19.628 reformada deja de estar marcada como vigencia anticipada.
  vigencia-21719)  python extraer_bcn.py --normas 141599 && python embed_sync.py ;;
  extraer)         python extraer_bcn.py "$@" ;;
  embed)           python embed_sync.py "$@" ;;
  crear-bd)        python crear_bd.py "$@" ;;
  *) echo "modo desconocido: $modo" >&2; exit 2 ;;
esac
