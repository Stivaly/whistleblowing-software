#!/usr/bin/env bash
# Crea en Qdrant las colecciones del experimento de enriquecimiento (<base>_p, _e, _pe, _eonly) desde normativa_cl
# y pipeline_bcn/enriquecimiento_articulos.json. No modifica normativa_cl. Uso: operaciones/indexar_enriquecido.sh [--base X] [--modos p,e,pe,eonly]
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
F=/tmp/fragmentos_normativa_cl.json
operaciones/volcar_fragmentos.sh normativa_cl "$F" >/dev/null
operaciones/correr_evaluacion.sh python3 pipeline_bcn/indexar_enriquecido.py --fragmentos "$F" "$@"
