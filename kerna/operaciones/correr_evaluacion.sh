#!/usr/bin/env bash
# Corre un comando de evaluación (python3 evaluacion/...) con las credenciales de Qdrant, Voyage y Azure OpenAI.
# Las claves se leen de Key Vault y quedan solo en el entorno del proceso; nunca se imprimen ni se escriben.
# Uso: kerna/operaciones/correr_evaluacion.sh [VAR=valor ...] python3 evaluacion/recall_retriever.py ...
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/_comun.sh"
cd "$RAIZ/kerna"
set -a; . pipeline_bcn/.env; set +a
export QDRANT_URL="${QDRANT_URL:-$(az keyvault secret show --vault-name "$KV" -n qdrant-url --query value -o tsv --only-show-errors)}"
export QDRANT_API_KEY="${QDRANT_API_KEY:-$(az keyvault secret show --vault-name "$KV" -n qdrant-api-key --query value -o tsv --only-show-errors)}"
export VOYAGE_API_KEY="${VOYAGE_API_KEY:-$(az keyvault secret show --vault-name "$KV" -n voyage-api-key --query value -o tsv --only-show-errors)}"
export AZURE_OPENAI_ENDPOINT="$(az keyvault secret show --vault-name "$KV" -n azure-openai-endpoint --query value -o tsv --only-show-errors)"
export AZURE_OPENAI_KEY="$(az keyvault secret show --vault-name "$KV" -n azure-openai-key --query value -o tsv --only-show-errors)"
export PYTHONPATH="nucleo:comun:pipeline_bcn${PYTHONPATH:+:$PYTHONPATH}"
exec env "$@"
