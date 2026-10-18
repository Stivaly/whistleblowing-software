#!/bin/sh
# Punto de entrada del contenedor. Uso: run.sh diario | semanal | vigencia-21719 | extraer [args] | embed [args]
#
# Con ATLAS_ACCESO_TEMPORAL=1 (lo define Terraform en los jobs) autoriza la IP de salida en la
# lista de acceso de MongoDB Atlas antes de empezar y la quita al terminar, también si falla.
set -e
modo="${1:-diario}"
[ $# -gt 0 ] && shift

if [ "${ATLAS_ACCESO_TEMPORAL:-0}" = 1 ]; then
  cerrar_atlas() {
    rc=$?
    trap - EXIT
    python atlas_acceso.py cerrar || echo "Atlas: no se pudo quitar la entrada; vence sola" >&2
    exit $rc
  }
  trap cerrar_atlas EXIT
  trap 'exit 143' TERM INT
  python atlas_acceso.py abrir
fi

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
