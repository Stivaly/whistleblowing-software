#!/bin/sh
# Punto de entrada del contenedor. Uso: run.sh diario | semanal | vigencia-21719 | extraer [args] | embed [args]
#
# Regla de disparo (diario, semanal y vigencia-21719): extraer_bcn.py deja en $KERNA_RESULTADO cuántos
# fragmentos cambiaron; embed_sync.py --todas --si-cambios vectoriza todas las colecciones activas solo si
# hubo cambios o quedaron pendientes de una corrida fallida. Sin cambios imprime "sin cambios" y no llama
# a ningún proveedor. Si la extracción falla (set -e) no se vectoriza.
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

RESULTADO="${KERNA_RESULTADO:-salida/resultado_extraccion.json}"

# pipeline [args de extraer_bcn.py]
pipeline() {
  mkdir -p "$(dirname "$RESULTADO")"
  # Un resultado viejo no puede disparar la vectorización: se vacía antes de extraer.
  : > "$RESULTADO"
  python extraer_bcn.py "$@" --resultado "$RESULTADO"
  python embed_sync.py --todas --si-cambios "$RESULTADO"
}

case "$modo" in
  diario)          pipeline ;;
  semanal)         pipeline --forzar ;;
  # 1 de diciembre: la Ley 19.628 reformada deja de estar marcada como vigencia anticipada.
  vigencia-21719)  pipeline --normas 141599 ;;
  extraer)         python extraer_bcn.py "$@" ;;
  embed)           python embed_sync.py "$@" ;;
  crear-bd)        python crear_bd.py "$@" ;;
  *) echo "modo desconocido: $modo" >&2; exit 2 ;;
esac
