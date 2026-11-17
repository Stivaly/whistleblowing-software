#!/usr/bin/env bash
# Crea (o repara) las cuentas receptoras de los equipos de «Compartir con» en Veridy: kerna-equipo-comite,
# kerna-equipo-auditoria y kerna-equipo-legal. Sin canales: no reciben denuncias nuevas por sí solas, solo lo que el
# conector les comparte. El nombre público es la etiqueta del equipo. La clave se genera aquí, se guarda en Key Vault de
# Veridy como `veridy-kerna-equipo-<id>-password` (por stdin; nunca se imprime) y el contenedor de Veridy la lee de ahí.
# Uso: kerna/operaciones/crear_equipos.sh          (idempotente; no cambia una clave ya guardada)
# Veridy debe estar encendido. Imprime solo CREADA / EXISTE por equipo.
set -euo pipefail
. "$(dirname "$0")/_veridy_remoto.sh"
veridy_encendido
T="$(mktemp)"; trap 'rm -f "$T"' EXIT
for par in "comite|Comité de ética" "auditoria|Auditoría interna" "legal|Fiscalía legal"; do
  ID="${par%%|*}"; NOMBRE="${par#*|}"; USUARIO="kerna-equipo-$ID"; SECRETO="veridy-kerna-equipo-$ID-password"
  if ! az keyvault secret show --vault-name "$KV_V" -n "$SECRETO" --query name -o tsv --only-show-errors >/dev/null 2>&1; then
    openssl rand -base64 36 | tr -d '/+=\n' | head -c 40 \
      | az keyvault secret set --vault-name "$KV_V" -n "$SECRETO" --file /dev/stdin --encoding utf-8 -o none --only-show-errors
  fi
  { echo "USUARIO = '$USUARIO'"; echo "SECRETO = '$SECRETO'"; echo "NOMBRE = '$NOMBRE'"; echo "CANALES = False"; cat "$(dirname "$0")/veridy_crear_usuario.py"; } > "$T"
  echo "$ID: $(remoto_py "$T" | tail -1)"
done
