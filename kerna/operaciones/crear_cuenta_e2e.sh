#!/usr/bin/env bash
# Crea la cuenta `kerna-e2e` en Veridy: destinatario (rol «receiver») sin permisos extra (no borra, no comparte, no redacta,
# sin avisos por correo), en los mismos canales que `kerna-conector`. Es la cuenta para las pruebas e2e del front y de
# «Probar Kerna»: distinta de la del conector porque Veridy cierra las sesiones anteriores de un usuario en cada ingreso.
# La clave se genera aquí, se guarda en Key Vault de Veridy como `veridy-kerna-e2e-password` (por stdin; nunca se imprime ni
# queda en archivos) y el contenedor de Veridy la lee de ahí para crear el usuario. Luego se verifica el inicio de sesión.
# Uso: kerna/operaciones/crear_cuenta_e2e.sh          (idempotente; no cambia una clave ya guardada)
# Veridy debe estar encendido. Para usar la clave en pruebas: VERIDY_USUARIO=kerna-e2e VERIDY_PASSWORD=$(az keyvault secret show ...)
set -euo pipefail
. "$(dirname "$0")/_veridy_remoto.sh"
USUARIO=kerna-e2e; SECRETO=veridy-kerna-e2e-password; NOMBRE="Kerna e2e (pruebas)"
veridy_encendido
if ! az keyvault secret show --vault-name "$KV_V" -n "$SECRETO" --query name -o tsv --only-show-errors >/dev/null 2>&1; then
  openssl rand -base64 36 | tr -d '/+=\n' | head -c 40 \
    | az keyvault secret set --vault-name "$KV_V" -n "$SECRETO" --file /dev/stdin --encoding utf-8 -o none --only-show-errors
  echo "Clave generada y guardada en Key Vault ($SECRETO)."
else
  echo "La clave ya estaba en Key Vault ($SECRETO)."
fi
T="$(mktemp)"; trap 'rm -f "$T"' EXIT
{ echo "USUARIO = '$USUARIO'"; echo "SECRETO = '$SECRETO'"; echo "NOMBRE = '$NOMBRE'"; cat "$(dirname "$0")/veridy_crear_usuario.py"; } > "$T"
SAL="$(remoto_py "$T")"; echo "$SAL" | tail -3
# Verificación: inicio de sesión como lo hace el conector (clave solo por entorno)
export VERIDY_URL_E2E="$URL_V" VERIDY_USUARIO_E2E="$USUARIO"
VERIDY_PASSWORD_E2E="$(az keyvault secret show --vault-name "$KV_V" -n "$SECRETO" --query value -o tsv --only-show-errors)" \
PYTHONPATH="$RAIZ/kerna/conector" /usr/bin/python3 - <<'PY'
import os
from kerna_conector.veridy import ClienteVeridy
c = ClienteVeridy(os.environ["VERIDY_URL_E2E"], os.environ["VERIDY_USUARIO_E2E"], os.environ["VERIDY_PASSWORD_E2E"])
c.iniciar_sesion(); n = len(c.listar_casos()); c.cerrar_sesion()
print("Inicio de sesión de %s: correcto (ve %d casos)." % (os.environ["VERIDY_USUARIO_E2E"], n))
PY
