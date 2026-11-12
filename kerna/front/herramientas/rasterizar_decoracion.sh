#!/usr/bin/env bash
# Exporta la decoración SVG a WebP en la imagen oficial de Playwright (nada se instala en el host).
set -euo pipefail
AQUI="$(cd "$(dirname "$0")/.." && pwd)"
docker run --rm --ipc=host -v "$AQUI:/front" mcr.microsoft.com/playwright/python:v1.64.0-noble bash -c '
  pip install -q --break-system-packages playwright==1.64.0 pillow 2>&1 | tail -1
  python3 /front/herramientas/rasterizar_decoracion.py /front
  chown -R '"$(id -u):$(id -g)"' /front/app/estaticos/img'
