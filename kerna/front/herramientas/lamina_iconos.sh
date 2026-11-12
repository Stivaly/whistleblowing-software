#!/usr/bin/env bash
# Captura kerna/front/diseno-v2/capturas/prod6-iconos.png (lámina de íconos de identidad) en la imagen oficial de Playwright; nada se instala en el host.
set -euo pipefail
AQUI="$(cd "$(dirname "$0")" && pwd)"; F="$(dirname "$AQUI")"
python3 "$AQUI/lamina_iconos.py" "$AQUI/_lamina_iconos.html"
docker run --rm --ipc=host -v "$F:/f" -w /f/herramientas mcr.microsoft.com/playwright/python:v1.64.0-noble bash -c '
 pip install -q --break-system-packages playwright==1.64.0 2>&1 | tail -1
 python - <<PY
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b = p.chromium.launch(args=["--allow-file-access-from-files"]); pg = b.new_page(viewport={"width": 1550, "height": 900})
    pg.goto("file:///f/herramientas/_lamina_iconos.html"); pg.wait_for_timeout(800)
    pg.screenshot(path="/f/diseno-v2/capturas/prod6-iconos.png", full_page=True)
PY
 chown -R '"$(id -u):$(id -g)"' /f/diseno-v2/capturas'
