#!/usr/bin/env bash
# Empaqueta el front (con las consultas KQL del Workbook) y lo despliega en el App Service F1.
# Uso: kerna/front/desplegar.sh      (requiere az con sesión y terraform aplicado: infra/aplicar.sh kerna)
set -euo pipefail
AQUI="$(cd "$(dirname "$0")" && pwd)"; RAIZ="$(git -C "$AQUI" rev-parse --show-toplevel)"
APP="$(terraform -chdir="$RAIZ/infra/terraform" output -raw front_nombre)"
TMP="$(mktemp -d)"; mkdir -p "$TMP/app/kql"
cp -r "$AQUI/app/." "$TMP/app/"; cp "$AQUI/requirements.txt" "$TMP/"
rm -rf "$TMP/app/__pycache__" "$TMP/app/kql"; mkdir "$TMP/app/kql"
for k in informe_revision_manual latencia_por_etapa disponibilidad_efectiva errores_por_proveedor solicitudes_por_modo tokens_por_solicitud front_casos_por_dia front_articulos_por_ley front_valoraciones front_latencia front_reintentos front_tokens_por_modelo front_pendientes_motivos front_reintentos_resumen front_horarios; do
  cp "$RAIZ/kerna/docs/observabilidad/consultas/$k.kql" "$TMP/app/kql/"
done
(cd "$TMP" && python3 -c "import shutil;shutil.make_archive('front','zip','.')")
az webapp deploy -g rg-kerna-dev -n "$APP" --src-path "$TMP/front.zip" --type zip --clean true
echo "https://$(terraform -chdir="$RAIZ/infra/terraform" output -raw front_url | sed 's#https://##')"
