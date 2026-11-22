#!/usr/bin/env bash
# Genera las vistas previas de los correos del panel y las captura a 600 y 375 px con Playwright (contenedor, sin tocar nada más).
# Salida: kerna/operaciones/salida/correos/*.html y *-600.png / *-375.png (ignorada por git).
set -euo pipefail
AQUI="$(cd "$(dirname "$0")" && pwd)"
python3 "$AQUI/generar_vistas_correo.py"
docker run --rm --ipc=host -v "$AQUI/salida:/out" -v "$AQUI/capturar_correos.py:/s/c.py:ro" \
  mcr.microsoft.com/playwright/python:v1.64.0-noble \
  bash -c "pip install -q --break-system-packages playwright==1.64.0 2>&1 | tail -1; python /s/c.py; chown -R $(id -u):$(id -g) /out"
