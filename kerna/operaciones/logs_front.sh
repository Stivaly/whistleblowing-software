#!/usr/bin/env bash
# Últimos errores (traceback) de los registros de aplicación del front (App Service). Uso: kerna/operaciones/logs_front.sh [líneas=80]
# Descarga el zip de registros a un temporal y muestra el final de cada archivo de aplicación; no deja nada en disco.
set -euo pipefail
. "$(dirname "$0")/_comun.sh"
N="${1:-80}"; T="$(mktemp -d)"; trap 'rm -rf "$T"' EXIT
az webapp log download -g "$RG" -n "$FRONT_APP" --log-file "$T/l.zip" --only-show-errors >/dev/null
python3 -c "import zipfile,sys;zipfile.ZipFile(sys.argv[1]).extractall(sys.argv[2])" "$T/l.zip" "$T/x"
find "$T/x" -type f | sed "s#$T/x/##" >&2
for f in $(find "$T/x" -type f \( -name '*default_docker.log' \) | sort | tail -2); do echo "== ${f#$T/x/}"; grep -n -B2 -A"$N" -E "Traceback|Error|Exception" "$f" | tail -n "$N" || true; done
