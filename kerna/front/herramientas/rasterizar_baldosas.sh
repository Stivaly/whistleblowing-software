#!/usr/bin/env bash
# Exporta las baldosas de estado del veredicto a PNG en la imagen oficial de Playwright (nada se instala en el host).
set -euo pipefail
AQUI="$(cd "$(dirname "$0")/.." && pwd)"
docker run --rm --ipc=host -v "$AQUI:/front" mcr.microsoft.com/playwright/python:v1.64.0-noble bash -c '
  pip install -q --break-system-packages playwright==1.64.0 2>&1 | tail -1
  python3 /front/herramientas/rasterizar_baldosas.py /front
  chown -R '"$(id -u):$(id -g)"' /front/app/estaticos/img'
