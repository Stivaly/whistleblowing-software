#!/usr/bin/env bash
# Crea en Key Vault los secretos propios del núcleo y la credencial del conector, si faltan.
# Los valores se generan aquí y nunca se muestran. Idempotente: no cambia los que ya existen
# (para rotar uno, bórralo antes en Key Vault o usa --rotar-cliente).
#
#   kv de Kerna:  kerna-jwt-secreto, kerna-local-token, kerna-clientes (JSON con el sha256 del secreto del cliente)
#   kv de Veridy: kerna-client-secret (lo usa el conector), kerna-client-id
#
# Uso: infra/scripts/secretos_nucleo.sh [--rotar-cliente]
set -euo pipefail
RAIZ="$(git -C "$(dirname "$0")" rev-parse --show-toplevel)"
KV="$(terraform -chdir="$RAIZ/infra/terraform" output -raw key_vault_nombre)"
KVV="${KV_VERIDY:-$(terraform -chdir="$RAIZ/infra/veridy/terraform" output -raw key_vault_nombre)}"
CLIENT_ID="conector-veridy-dev"
CLIENTE="veridy-dev"
PY=/usr/bin/python3

existe() { az keyvault secret show --vault-name "$1" --name "$2" --query id -o tsv >/dev/null 2>&1; }
aleatorio() { $PY -c "import secrets,sys;print(secrets.token_urlsafe(int(sys.argv[1])),end='')" "$1"; }
guardar() { az keyvault secret set --vault-name "$1" --name "$2" --file "$3" -o none; echo "$2: creado en $1"; }

existe "$KV" kerna-jwt-secreto || guardar "$KV" kerna-jwt-secreto <(aleatorio 48)
existe "$KV" kerna-local-token || guardar "$KV" kerna-local-token <(aleatorio 32)

if [ "${1:-}" = "--rotar-cliente" ] || ! existe "$KVV" kerna-client-secret || ! existe "$KV" kerna-clientes; then
  S="$(aleatorio 40)"
  guardar "$KVV" kerna-client-secret <(printf %s "$S")
  guardar "$KVV" kerna-client-id <(printf %s "$CLIENT_ID")
  guardar "$KV" kerna-clientes <(S="$S" CLIENT_ID="$CLIENT_ID" CLIENTE="$CLIENTE" $PY -c "
import hashlib, json, os
print(json.dumps({os.environ['CLIENT_ID']: {'secreto_sha256': hashlib.sha256(os.environ['S'].encode()).hexdigest(),
                                            'cliente': os.environ['CLIENTE']}}), end='')")
  unset S
fi
echo "Secretos del núcleo y del conector: listos."
