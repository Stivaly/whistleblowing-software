#!/usr/bin/env bash
# Carga un lote de denuncias sintéticas en Veridy por su API de envío (kerna/pruebas/herramientas/crear_denuncias.py).
# Uso: kerna/operaciones/cargar_denuncias.sh [N=10] [opciones de crear_denuncias.py: --dry-run | --verificar | --casos DEN-0001 ...]
# Veridy debe estar encendido (infra/veridy/veridy.sh encender). Es idempotente: los casos ya cargados no se repiten.
# Si Veridy limita los envíos por hora, se detiene con código 3: repetir el comando más tarde continúa.
set -euo pipefail
RAIZ="$(git -C "$(dirname "$0")" rev-parse --show-toplevel)"
URL="$(terraform -chdir="$RAIZ/infra/veridy/terraform" output -raw url)"; URL="${URL%/}"
if [ "$(curl -s -o /dev/null -w '%{http_code}' --max-time 10 "$URL/api/health" || true)" != 200 ]; then
  echo "Veridy no responde. Enciéndelo con: infra/veridy/veridy.sh encender" >&2; exit 1
fi
N=10; [[ "${1:-}" =~ ^[0-9]+$ ]] && { N="$1"; shift; }
[ $# -gt 0 ] && ARGS=("$@") || ARGS=(--lote "$N")
cd "$RAIZ/kerna"
VERIDY_URL="$URL" /usr/bin/python3 pruebas/herramientas/crear_denuncias.py "${ARGS[@]}"
