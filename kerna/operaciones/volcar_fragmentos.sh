#!/usr/bin/env bash
# Vuelca a un JSON los payloads vigentes (texto legal público, sin denuncias) de una colección de Qdrant.
# Uso: kerna/operaciones/volcar_fragmentos.sh [colección] [salida.json]   (por defecto normativa_cl, /tmp/fragmentos_<col>.json)
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
COL="${1:-normativa_cl}"; OUT="${2:-/tmp/fragmentos_${COL}.json}"
exec operaciones/correr_evaluacion.sh python3 pipeline_bcn/volcar_fragmentos.py "$COL" "$OUT"
