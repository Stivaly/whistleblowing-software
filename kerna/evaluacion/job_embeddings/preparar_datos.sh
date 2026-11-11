#!/usr/bin/env bash
# Exporta fragmentos (Mongo) y dataset a datos/ para construir la imagen. Abre el acceso temporal a
# Atlas (vence solo en 2 h) y lo cierra al salir, también si falla.
set -euo pipefail
AQUI="$(cd "$(dirname "$0")" && pwd)"
cd "$AQUI/../../pipeline_bcn"
(
  set -a; . ./.env; set +a
  export ATLAS_PROJECT_ID="${ATLAS_PROJECT_ID:-6abfe35c3b197494864646bb}" ATLAS_ACCESO_HORAS="${ATLAS_ACCESO_HORAS:-2}"
  trap '.venv/bin/python atlas_acceso.py cerrar' EXIT
  .venv/bin/python atlas_acceso.py abrir
  .venv/bin/python "$AQUI/preparar_datos.py"
)
