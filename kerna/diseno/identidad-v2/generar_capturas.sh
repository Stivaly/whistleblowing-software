#!/usr/bin/env bash
# Regenera capturas y lámina dentro de la imagen oficial de Playwright (nada se instala en el host).
set -euo pipefail
cd "$(dirname "$0")"
docker run --rm --ipc=host -v "$PWD:/trabajo" -w /trabajo mcr.microsoft.com/playwright/python:v1.49.0-noble bash -c '
  pip install -q --break-system-packages playwright==1.49.0 >/dev/null 2>&1
  python generar_capturas.py
  chown -R '"$(id -u):$(id -g)"' /trabajo'
