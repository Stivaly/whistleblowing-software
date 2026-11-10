#!/usr/bin/env bash
# Construye y sube la imagen de un componente de Kerna AI, y opcionalmente la despliega.
#
# Uso (desde cualquier carpeta del repo):
#   infra/scripts/subir_imagen_kerna.sh nucleo                 # construye y sube (tag = commit de git)
#   infra/scripts/subir_imagen_kerna.sh nucleo --desplegar     # + actualiza la Container App a esa imagen
#   infra/scripts/subir_imagen_kerna.sh conector --tag v1      # tag manual
#
# Componentes: nucleo | conector | servicio_local. El contexto de build es kerna/ y el Dockerfile,
# kerna/<componente>/Dockerfile. Se construye en este equipo porque ACR Tasks está bloqueado en
# suscripciones con créditos gratuitos. Requiere Docker, `az login` y Terraform aplicado.
set -euo pipefail

RAIZ="$(git -C "$(dirname "$0")" rev-parse --show-toplevel)"
TF="$RAIZ/infra/terraform"

COMP="${1:?falta el componente: nucleo | conector | servicio_local}"; shift
case "$COMP" in nucleo|conector|servicio_local) ;; *) echo "componente desconocido: $COMP" >&2; exit 2 ;; esac
DESPLEGAR=0
TAG=""
while [ $# -gt 0 ]; do
  case "$1" in
    --desplegar) DESPLEGAR=1 ;;
    --tag)       TAG="${2:?falta el tag}"; shift ;;
    -h|--help)   sed -n '2,11p' "$0"; exit 0 ;;
    *) echo "opción desconocida: $1" >&2; exit 2 ;;
  esac
  shift
done

salida() { terraform -chdir="$TF" output -raw "$1"; }
ACR="$(salida acr_nombre)"
SERVIDOR="$(salida acr_servidor)"
RG="$(salida grupo_recursos)"
NOMBRE="kerna-${COMP//_/-}"

if [ -z "$TAG" ]; then
  TAG="$(git -C "$RAIZ" rev-parse --short HEAD)"
  git -C "$RAIZ" diff --quiet HEAD -- kerna/comun "kerna/$COMP" || TAG="$TAG-sucio"
fi
IMAGEN="$SERVIDOR/$NOMBRE:$TAG"

echo "Construyendo $IMAGEN"
docker build -q -f "$RAIZ/kerna/$COMP/Dockerfile" -t "$IMAGEN" "$RAIZ/kerna" >/dev/null
az acr login --name "$ACR" -o none
docker push -q "$IMAGEN" >/dev/null
echo "Subida: $IMAGEN"

if [ "$DESPLEGAR" = 1 ]; then
  [ "$COMP" = conector ] && { echo "El conector corre en el grupo de Veridy: se despliega con infra/veridy/terraform" >&2; exit 2; }
  APP="ca-${RG#rg-}-${COMP//_/-}"
  az containerapp update --name "$APP" --resource-group "$RG" --image "$IMAGEN" -o none
  echo "Desplegada en $APP"
fi
