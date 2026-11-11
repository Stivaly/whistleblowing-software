#!/usr/bin/env bash
# Construye y sube la imagen del job de evaluación de embeddings (kerna/evaluacion/job_embeddings).
# No lanza el job. Primero hay que exportar los datos: kerna/evaluacion/job_embeddings/preparar_datos.sh
#
# Uso:
#   infra/scripts/subir_imagen_eval.sh                 # construye y sube (tag = commit, -sucio si hay cambios)
#   infra/scripts/subir_imagen_eval.sh --desplegar     # + az containerapp job update (el job ya debe existir)
#   infra/scripts/subir_imagen_eval.sh --tag v1        # tag manual (el de var.imagen_eval_tag la primera vez)
set -euo pipefail

RAIZ="$(git -C "$(dirname "$0")" rev-parse --show-toplevel)"
TF="$RAIZ/infra/terraform"
CONTEXTO="$RAIZ/kerna/evaluacion/job_embeddings"

DESPLEGAR=0
TAG=""
while [ $# -gt 0 ]; do
  case "$1" in
    --desplegar) DESPLEGAR=1 ;;
    --tag)       TAG="${2:?falta el tag}"; shift ;;
    -h|--help)   sed -n '2,9p' "$0"; exit 0 ;;
    *) echo "opción desconocida: $1" >&2; exit 2 ;;
  esac
  shift
done

[ -s "$CONTEXTO/datos/fragmentos.json" ] || { echo "Faltan los datos: ejecutar $CONTEXTO/preparar_datos.sh" >&2; exit 1; }

salida() { terraform -chdir="$TF" output -raw "$1"; }
ACR="$(salida acr_nombre)"
REPO="$(salida repositorio_eval_embeddings)"
RG="$(salida grupo_recursos)"

if [ -z "$TAG" ]; then
  TAG="$(git -C "$RAIZ" rev-parse --short HEAD)"
  if [ -n "$(git -C "$RAIZ" status --porcelain -- kerna/evaluacion/job_embeddings)" ]; then
    TAG="$TAG-sucio-$(date +%Y%m%d%H%M)"
  fi
fi
IMAGEN="$REPO:$TAG"

echo "==> Imagen: $IMAGEN"
az acr login --name "$ACR" --only-show-errors
docker build -t "$IMAGEN" "$CONTEXTO"
docker push "$IMAGEN"
echo "==> Subida: $IMAGEN"

if [ "$DESPLEGAR" = 1 ]; then
  JOB="$(terraform -chdir="$TF" output -json job_eval_embeddings | python3 -c 'import json,sys; print((json.load(sys.stdin) or [""])[0])')"
  [ -n "$JOB" ] || { echo "El job no existe todavía (crear_job_eval = true y terraform apply)." >&2; exit 1; }
  echo "==> Actualizando $JOB"
  az containerapp job update -n "$JOB" -g "$RG" --image "$IMAGEN" --only-show-errors -o none
fi
