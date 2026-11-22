#!/usr/bin/env bash
# Empaqueta el front (con las consultas KQL del Workbook) y lo despliega en el App Service F1.
# Uso: kerna/front/desplegar.sh [--ref <commit|rama>] [--sin-pruebas]
#   sin --ref: despliega la carpeta de trabajo tal como está.
#   --ref HEAD: despliega exactamente ese commit (ignora cambios sin commitear de otros agentes).
#   Antes de subir corre las pruebas del front sobre lo que se va a desplegar; si fallan, no despliega.
# Requiere az con sesión y terraform aplicado (infra/aplicar.sh kerna).
set -euo pipefail
AQUI="$(cd "$(dirname "$0")" && pwd)"; RAIZ="$(git -C "$AQUI" rev-parse --show-toplevel)"
REF=""; PRUEBAS=1
while [ $# -gt 0 ]; do case "$1" in --ref) REF="$2"; shift 2;; --sin-pruebas) PRUEBAS=0; shift;; *) echo "opción desconocida: $1" >&2; exit 2;; esac; done
APP="$(terraform -chdir="$RAIZ/infra/terraform" output -raw front_nombre)"
TMP="$(mktemp -d)"; FUENTE="$(mktemp -d)"; trap 'rm -rf "$TMP" "$FUENTE"' EXIT; mkdir -p "$TMP/app/kql"
if [ -n "$REF" ]; then
  git -C "$RAIZ" archive "$REF" kerna/pytest.ini kerna/front kerna/comun kerna/docs/observabilidad/consultas kerna/pruebas kerna/diseno/identidad-v3 | tar -x -C "$FUENTE"
  AQUI="$FUENTE/kerna/front"; RAIZ_PRUEBAS="$FUENTE"; RAIZ_KQL="$FUENTE"; COMUN="$FUENTE/kerna/comun/kerna_comun"
  echo "Desplegando $(git -C "$RAIZ" rev-parse --short "$REF")"
else
  RAIZ_PRUEBAS="$RAIZ"; RAIZ_KQL="$RAIZ"; COMUN="$RAIZ/kerna/comun/kerna_comun"
fi
if [ "$PRUEBAS" = 1 ]; then
  (cd "$RAIZ_PRUEBAS" && python3 -m pytest -q kerna/pruebas/unitarias/test_front*.py -p no:cacheprovider) || { echo "Pruebas del front fallaron: no se despliega." >&2; exit 1; }
fi
cp -r "$AQUI/app/." "$TMP/app/"; cp "$AQUI/requirements.txt" "$TMP/"
# solo los esquemas de ajustes y de clientes y el anonimizador (solo biblioteca estándar, para la Demo) de kerna_comun (el resto trae dependencias de Azure que el front no necesita)
mkdir -p "$TMP/kerna_comun"; cp "$COMUN/ajustes_esquema.py" "$COMUN/clientes_esquema.py" "$COMUN/anonimizador.py" "$COMUN/__init__.py" "$TMP/kerna_comun/"
rm -rf "$TMP/app/__pycache__" "$TMP/app/kql"; mkdir "$TMP/app/kql"
for k in informe_revision_manual latencia_por_etapa disponibilidad_efectiva errores_por_proveedor solicitudes_por_modo tokens_por_solicitud front_casos_por_dia front_articulos_por_ley front_valoraciones front_latencia front_reintentos front_tokens_por_modelo front_pendientes_motivos front_reintentos_resumen front_horarios; do
  cp "$RAIZ_KQL/kerna/docs/observabilidad/consultas/$k.kql" "$TMP/app/kql/"
done
(cd "$TMP" && python3 -c "import shutil;shutil.make_archive('front','zip','.')")
az webapp deploy -g rg-kerna-dev -n "$APP" --src-path "$TMP/front.zip" --type zip --clean true
echo "https://$(terraform -chdir="$RAIZ/infra/terraform" output -raw front_url | sed 's#https://##')"
