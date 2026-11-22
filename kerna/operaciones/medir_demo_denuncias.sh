#!/usr/bin/env bash
# Verifica las 10 denuncias de la demo del panel («Denuncias») contra el núcleo real: levanta el código del núcleo en 127.0.0.1 con la misma
# configuración KERNA_* que el núcleo desplegado (infra/terraform/terraform.tfvars) y las mismas APIs (Azure OpenAI, Voyage, Qdrant, Gemini), y le
# envía cada caso con el MISMO cliente HTTP que usa el front (front/app/demo_denuncias.py). Escribe evaluacion/registro/demo_denuncias_<fecha>.json
# (solo ids, leyes, tiempos y la comparación; nunca el texto de las denuncias).
# Las claves se leen de Key Vault y quedan solo en el entorno del proceso; nunca se imprimen.
# Uso: kerna/operaciones/medir_demo_denuncias.sh [--concurrencia 3] [--casos id1 id2 ...] [--etiqueta texto]
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/_comun.sh"
cd "$RAIZ/kerna"
kv() { az keyvault secret show --vault-name "$KV" -n "$1" --query value -o tsv --only-show-errors; }
export GEMINI_API_KEY="$(kv gemini-api-key)" VOYAGE_API_KEY="$(kv voyage-api-key)" QDRANT_URL="$(kv qdrant-url)" QDRANT_API_KEY="$(kv qdrant-api-key)"
export AZURE_OPENAI_KEY="$(kv azure-openai-key)" AZURE_OPENAI_ENDPOINT="$(kv azure-openai-endpoint)" KERNA_LOCAL_TOKEN="$(kv kerna-local-token)"
export KERNA_JWT_SECRETO="$(python3 -c 'import secrets;print(secrets.token_hex(32))')"
export PYTHONPATH="nucleo:comun:front${PYTHONPATH:+:$PYTHONPATH}"
exec python3 operaciones/medir_demo_denuncias.py "$@"
