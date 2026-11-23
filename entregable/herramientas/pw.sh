#!/usr/bin/env bash
# Corre un script de Playwright (Python) contra la instalación local, en el contenedor oficial de Playwright.
# Uso: entregable/herramientas/pw.sh <script.py> [args]   — /out = entregable/manuales/capturas
set -euo pipefail
AQUI="$(cd "$(dirname "$0")" && pwd)"; OUT="${OUT:-$AQUI/../manuales/capturas}"; mkdir -p "$OUT"
PY="$(realpath "$1")"; shift
docker run --rm --ipc=host --network host -e VERIDY_AUDITOR_CLAVE -e KERNA_PANEL_CLAVE -e PYTHONPATH=/h \
  -v "$PY:/s/script.py:ro" -v "$AQUI:/h:ro" -v "$OUT:/out" mcr.microsoft.com/playwright/python:v1.64.0-noble \
  bash -c "pip install -q --break-system-packages playwright==1.64.0 2>&1 | tail -1; cd /h && python /s/script.py $*; chown -R $(id -u):$(id -g) /out"
