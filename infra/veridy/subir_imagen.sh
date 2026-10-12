#!/usr/bin/env bash
# Construye la imagen de Veridy (docker/Dockerfile) y la sube al Container Registry.
#
# Uso (desde cualquier carpeta del repo):
#   infra/veridy/subir_imagen.sh --tag v1
#
# Construye en local porque ACR Tasks (az acr build) está bloqueado en Azure for Students.
# La primera vez también importa socat (contenedor "puertos") al registro.
set -euo pipefail

RAIZ="$(git -C "$(dirname "$0")" rev-parse --show-toplevel)"
TF="$RAIZ/infra/veridy/terraform"

TAG=""
while [ $# -gt 0 ]; do
  case "$1" in
    --tag)     TAG="${2:?falta el tag}"; shift ;;
    -h|--help) sed -n '2,9p' "$0"; exit 0 ;;
    *) echo "opción desconocida: $1" >&2; exit 2 ;;
  esac
  shift
done
[ -n "$TAG" ] || { echo "indicar --tag (el imagen_tag de terraform.tfvars)" >&2; exit 2; }

IMAGEN="$(terraform -chdir="$TF" output -raw imagen)"
REPO="${IMAGEN%:*}"
ACR="${REPO%%.*}"

echo "==> Imagen: $REPO:$TAG"
az acr login --name "$ACR" --only-show-errors
docker build -f "$RAIZ/docker/Dockerfile" -t "$REPO:$TAG" "$RAIZ"
docker push "$REPO:$TAG"

if ! az acr repository show-tags -n "$ACR" --repository socat -o tsv --only-show-errors 2>/dev/null | grep -qx "1.8"; then
  echo "==> Importando socat al registro"
  az acr import -n "$ACR" --source docker.io/alpine/socat:1.8.0.3 --image socat:1.8 --only-show-errors
fi

echo "==> Subida: $REPO:$TAG ($(docker images --format '{{.Size}}' "$REPO:$TAG"))"
