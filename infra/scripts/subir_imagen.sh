#!/usr/bin/env bash
# Construye, sube y (opcionalmente) despliega la imagen del pipeline en un comando.
#
# Uso (desde cualquier carpeta del repo):
#   infra/scripts/subir_imagen.sh                     # construye y sube (tag = commit de git)
#   infra/scripts/subir_imagen.sh --desplegar         # + actualiza los 3 jobs a esa imagen
#   infra/scripts/subir_imagen.sh --desplegar --probar diario   # + lanza el job y muestra sus logs
#   infra/scripts/subir_imagen.sh --tag v1            # tag manual (el de terraform.tfvars, primera vez)
#
# Requisitos: Docker, Azure CLI con sesión iniciada (az login) y Terraform ya aplicado
# (lee los nombres de recursos con `terraform output`). Construye en local porque
# ACR Tasks (`az acr build`) está bloqueado en suscripciones con créditos gratuitos.
set -euo pipefail

RAIZ="$(git -C "$(dirname "$0")" rev-parse --show-toplevel)"
TF="$RAIZ/infra/terraform"
CONTEXTO="$RAIZ/kerna/pipeline_bcn"

DESPLEGAR=0
PROBAR=""
TAG=""
while [ $# -gt 0 ]; do
  case "$1" in
    --desplegar) DESPLEGAR=1 ;;
    --probar)    PROBAR="${2:?falta el nombre del job: diario | semanal | vigencia-21719}"; shift ;;
    --tag)       TAG="${2:?falta el tag}"; shift ;;
    -h|--help)   sed -n '2,12p' "$0"; exit 0 ;;
    *) echo "opción desconocida: $1" >&2; exit 2 ;;
  esac
  shift
done

salida() { terraform -chdir="$TF" output -raw "$1"; }
ACR="$(salida acr_nombre)"
REPO="$(salida repositorio_pipeline)"
RG="$(salida grupo_recursos)"

# Tag inmutable = commit actual; "-sucio" si hay cambios sin commitear en el pipeline.
if [ -z "$TAG" ]; then
  TAG="$(git -C "$RAIZ" rev-parse --short HEAD)"
  if [ -n "$(git -C "$RAIZ" status --porcelain -- kerna/pipeline_bcn)" ]; then
    TAG="$TAG-sucio-$(date +%Y%m%d%H%M)"
  fi
fi
IMAGEN="$REPO:$TAG"

echo "==> Imagen: $IMAGEN"
az acr login --name "$ACR" --only-show-errors
docker build -t "$IMAGEN" -t "$REPO:latest" "$CONTEXTO"
docker push "$IMAGEN"
docker push "$REPO:latest"
echo "==> Subida: $IMAGEN"

if [ "$DESPLEGAR" = 1 ]; then
  JOBS="$(terraform -chdir="$TF" output -json jobs | python3 -c 'import json,sys; print(" ".join(json.load(sys.stdin)))')"
  [ -n "$JOBS" ] || { echo "No hay jobs creados (crear_jobs = false en terraform.tfvars)." >&2; exit 1; }
  for JOB in $JOBS; do
    echo "==> Actualizando $JOB"
    az containerapp job update -n "$JOB" -g "$RG" --image "$IMAGEN" --only-show-errors -o none
  done
fi

if [ -n "$PROBAR" ]; then
  JOB="$(terraform -chdir="$TF" output -json jobs | python3 -c 'import json,sys; m=[j for j in json.load(sys.stdin) if j.endswith("-'"$PROBAR"'")]; print(m[0] if m else "")')"
  [ -n "$JOB" ] || { echo "No existe un job '$PROBAR' (crear_jobs = false o nombre mal escrito)." >&2; exit 1; }
  echo "==> Lanzando $JOB"
  EJEC="$(az containerapp job start -n "$JOB" -g "$RG" --query name -o tsv)"
  echo "    ejecución: $EJEC (los logs pueden tardar 1-2 minutos en aparecer)"
  echo "    estado:  az containerapp job execution show -n $JOB -g $RG --job-execution-name $EJEC --query properties.status -o tsv"
  echo "    logs:    az containerapp job logs show -n $JOB -g $RG --execution $EJEC --container pipeline --follow"
fi
