#!/usr/bin/env bash
# Regenera las capturas dentro de la imagen oficial de Playwright (no instala nada en el host).
# El paquete Python de Playwright se instala en el contenedor, que es desechable; los navegadores ya vienen en la imagen.
set -euo pipefail
cd "$(dirname "$0")"
IMAGEN="mcr.microsoft.com/playwright/python:v1.49.0-noble"
docker run --rm --ipc=host -v "$PWD:/trabajo" -w /trabajo "$IMAGEN" bash -c '
  pip install -q --break-system-packages playwright==1.49.0 >/dev/null 2>&1
  python generar_capturas.py
  chown -R '"$(id -u):$(id -g)"' /trabajo
'
