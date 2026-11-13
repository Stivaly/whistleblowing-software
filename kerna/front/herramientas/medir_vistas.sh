#!/usr/bin/env bash
# Uso: medir_vistas.sh <url_base> <prefijo_capturas|-> <salida.json> [anchos...] [--nav=chromium|firefox|webkit]   (la clave se lee de Key Vault)
set -euo pipefail
AQUI="$(cd "$(dirname "$0")" && pwd)"; BASE="$1"; PREF="$2"; SAL="$3"; shift 3
CLAVE="$(az keyvault secret show --vault-name kv-kerna-dev-g6mzy -n front-clave-panel --query value -o tsv)"
DIR="$(dirname "$(realpath -m "$SAL")")"; mkdir -p "$DIR"
[ "$PREF" = "-" ] && P="-" || P="/out/$(basename "$PREF")"
docker run --rm --ipc=host --network host -v "$AQUI:/h:ro" -v "$DIR:/out" mcr.microsoft.com/playwright/python:v1.64.0-noble bash -c "
  pip install -q --break-system-packages playwright==1.64.0 2>&1 | tail -1
  python /h/medir_vistas.py '$BASE' '$CLAVE' '$P' /out/$(basename "$SAL") $* ; chown -R $(id -u):$(id -g) /out"
