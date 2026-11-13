#!/usr/bin/env bash
# Borra de Veridy los casos que Kerna no puede procesar (criterio en veridy_borrar_invalidos.py: sin acceso para la cuenta
# de servicio, sin texto o ilegibles, tras el reintento de todos). Se ejecuta dentro del contenedor de Veridy y borra en la
# base (cascada de GlobaLeaks: tip, accesos, comentarios, respuestas, archivos) dejando una entrada en el registro de auditoría.
# El conector marca como archivados los casos que ya no existen en Veridy y deja de contarlos.
# Uso: kerna/operaciones/borrar_casos_invalidos.sh [--aplicar] [--max N]     (sin --aplicar solo cuenta)
# Imprime solo conteos por motivo y los agrega a kerna/evaluacion/registro/borrar_casos_invalidos.log. Veridy debe estar encendido.
set -euo pipefail
. "$(dirname "$0")/_veridy_remoto.sh"
MODO=dry; MAX=10
while [ $# -gt 0 ]; do case "$1" in --aplicar) MODO=aplicar ;; --max) MAX="${2:?falta N}"; shift ;; *) echo "opción desconocida: $1" >&2; exit 2 ;; esac; shift; done
veridy_encendido
T="$(mktemp)"; trap 'rm -f "$T"' EXIT
{ echo "MODO = '$MODO'"; echo "TOPE_MAX = $MAX"; cat "$(dirname "$0")/veridy_borrar_invalidos.py"; } > "$T"
SAL="$(remoto_py "$T")"; echo "$SAL"
LINEA="$(echo "$SAL" | grep '^RESUMEN ' || true)"
[ -n "$LINEA" ] || { echo "El script remoto no entregó resumen." >&2; exit 1; }
echo "$(date -u +%FT%TZ) ${LINEA#RESUMEN }" >> "$RAIZ/kerna/evaluacion/registro/borrar_casos_invalidos.log"
