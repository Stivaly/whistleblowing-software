#!/usr/bin/env bash
# Arma el paquete de instalación local (Veridy + Kerna) en entregable/dist/veridy-kerna-local/ y su .zip.
# Uso: entregable/construir.sh [--sin-semilla] [--sin-zip]
#   --sin-semilla  reutiliza entregable/dist/semilla-veridy.tar.gz
#   --sin-zip      deja la carpeta sin comprimir
# Requiere Docker, az con sesión (lee de Key Vault y de Terraform) y las imágenes desplegadas en Azure.
# Los secretos quedan solo en dist/ (ignorada por git); nunca en el repositorio.
set -euo pipefail
AQUI="$(cd "$(dirname "$0")" && pwd)"; RAIZ="$(git -C "$AQUI" rev-parse --show-toplevel)"
DIST="$AQUI/dist"; PAQ="$DIST/veridy-kerna-local"; TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
SEMILLA=1; ZIP=1
for a in "$@"; do case "$a" in --sin-semilla) SEMILLA=0;; --sin-zip) ZIP=0;; *) echo "opción desconocida: $a" >&2; exit 2;; esac; done
VERSION="${VERSION:-$(date +%Y%m%d%H%M)}"
TF="$RAIZ/infra/terraform"; TFV="$RAIZ/infra/veridy/terraform"
VERIDY_BASE="acrkernadevg6mzy.azurecr.io/veridy:$(sed -n 's/^imagen_tag *= *"\(.*\)"/\1/p' "$TFV/terraform.tfvars")"
CONECTOR_BASE="acrkernadevg6mzy.azurecr.io/kerna-conector:$(sed -n 's/^conector_tag *= *"\(.*\)"/\1/p' "$TFV/terraform.tfvars")"
VOL_ORIGEN="${VOL_ORIGEN:-docker_globaleaks}"   # instalación local con la personalización de Veridy (se lee, no se modifica)
mkdir -p "$DIST"; umask 077
[ -f "$DIST/secretos.env" ] || { echo "Falta $DIST/secretos.env (ver entregable/README.md, «Credenciales»)." >&2; exit 1; }
set -a; . "$DIST/secretos.env"; set +a
umask 022

echo "1/6 Imágenes base"
az acr login --name acrkernadevg6mzy -o none
docker image inspect "$VERIDY_BASE" >/dev/null 2>&1 || docker pull -q "$VERIDY_BASE"
docker image inspect "$CONECTOR_BASE" >/dev/null 2>&1 || docker pull -q "$CONECTOR_BASE"

ctx_veridy() {  # contexto mínimo para Dockerfile.veridy
  local c="$TMP/veridy"; mkdir -p "$c/backend/globaleaks/rest" "$c/entregable/imagenes" "$c/entregable/dist"
  cp "$RAIZ/backend/globaleaks/rest/api.py" "$c/backend/globaleaks/rest/"
  cp "$AQUI/imagenes/veridy-inicio.sh" "$c/entregable/imagenes/"; cp "$1" "$c/entregable/dist/semilla-veridy.tar.gz"
  echo "$c"
}

if [ "$SEMILLA" = 1 ]; then
  echo "2/6 Datos iniciales de Veridy (copia de $VOL_ORIGEN, cuentas de prueba, sin denuncias)"
  : > "$TMP/vacia.tar.gz"
  docker build -q --build-arg BASE="$VERIDY_BASE" -t veridy-local:semilla -f "$AQUI/imagenes/Dockerfile.veridy" "$(ctx_veridy "$TMP/vacia.tar.gz")" >/dev/null
  VOL="semilla-$VERSION-$$"; docker volume create "$VOL" >/dev/null
  docker run --rm -v "$VOL_ORIGEN:/o:ro" -v "$VOL:/d" debian:trixie-slim sh -c 'cp -a /o/globaleaks.db /o/files /o/attachments /d/ && mkdir -p /d/log /d/tmp && chown -R 1000:1000 /d'
  docker run --rm -u 1000:1000 -v "$VOL:/var/globaleaks" -v "$AQUI/herramientas/semilla_usuarios.py:/s.py:ro" \
    -e USUARIOS="kerna-conector|Kerna AI|$VERIDY_CONECTOR_CLAVE;$VERIDY_AUDITOR_USUARIO|Auditor de prueba|$VERIDY_AUDITOR_CLAVE" \
    --entrypoint python3 veridy-local:semilla /s.py
  docker run --rm -v "$VOL:/d:ro" debian:trixie-slim tar -czf - -C /d globaleaks.db files attachments log tmp > "$DIST/semilla-veridy.tar.gz"
  echo "   volumen temporal $VOL (se puede eliminar con infra/limpiar_docker.sh; no contiene denuncias)"
fi

echo "3/6 Imágenes locales"
docker build -q --build-arg BASE="$VERIDY_BASE" -t "veridy-local:$VERSION" -f "$AQUI/imagenes/Dockerfile.veridy" "$(ctx_veridy "$DIST/semilla-veridy.tar.gz")" >/dev/null
docker tag "$CONECTOR_BASE" "kerna-conector-local:$VERSION"
P="$TMP/panel"; mkdir -p "$P/app/kql" "$P/kerna_comun" "$P/manuales"
cp -r "$RAIZ/kerna/front/app/." "$P/app/"; rm -rf "$P/app/__pycache__" "$P/app/kql"; mkdir "$P/app/kql"
cp "$RAIZ/kerna/front/requirements.txt" "$P/"
C="$RAIZ/kerna/comun/kerna_comun"; cp "$C/ajustes_esquema.py" "$C/clientes_esquema.py" "$C/anonimizador.py" "$C/nombres_cl.py" "$C/__init__.py" "$P/kerna_comun/"; cp -r "$C/diccionarios" "$P/kerna_comun/"
for k in $(sed -n 's/^for k in \(.*\); do$/\1/p' "$RAIZ/kerna/front/desplegar.sh"); do cp "$RAIZ/kerna/docs/observabilidad/consultas/$k.kql" "$P/app/kql/"; done
cp -r "$AQUI/lanzador" "$P/lanzador"; rm -rf "$P/lanzador/__pycache__"
cp "$AQUI"/manuales/*.pdf "$P/manuales/" 2>/dev/null || echo "   (sin manuales en PDF todavía: entregable/manuales/generar.sh)"
docker build -q -t "kerna-panel-local:$VERSION" -f "$AQUI/imagenes/Dockerfile.panel" "$P" >/dev/null

echo "4/6 Carpeta del paquete"
# Arriba solo los instaladores; todo lo demás en archivos/ (la usuaria no necesita abrirla).
if [ -e "$PAQ" ]; then P0="$RAIZ/.papelera/$(date +%F)/entregable/dist/veridy-kerna-local-$(date +%H%M%S)"; mkdir -p "$(dirname "$P0")"; mv "$PAQ" "$P0"; fi
A="$PAQ/archivos"; mkdir -p "$A"
cp "$AQUI/paquete/docker-compose.yml" "$AQUI/paquete/Detener.bat" "$AQUI"/paquete/*.ps1 "$AQUI"/paquete/*.sh "$AQUI/paquete/LEEME.txt" "$A/"
printf '@echo off\r\nstart "" powershell -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "%%~dp0archivos\\instalar.ps1"\r\n' > "$PAQ/Instalar.bat"
printf '#!/usr/bin/env bash\n# Instalador de Veridy y Kerna para Linux. Uso: ./instalar.sh\nexec bash "$(dirname "$0")/archivos/instalar.sh" "$@"\n' > "$PAQ/instalar.sh"
chmod +x "$PAQ"/*.sh "$A"/*.sh
# Windows: fin de línea CRLF; PowerShell 5 necesita BOM para leer bien los acentos.
python3 - "$A" <<'PY'
import pathlib, sys
for p in pathlib.Path(sys.argv[1]).iterdir():
    if p.suffix in (".ps1", ".bat", ".txt"):
        t = p.read_text(encoding="utf-8").replace("\r\n", "\n").replace("\n", "\r\n")
        p.write_text(t, encoding="utf-8-sig" if p.suffix == ".ps1" else "utf-8", newline="")
PY
cp "$AQUI"/manuales/*.pdf "$A/" 2>/dev/null || true
sal() { terraform -chdir="$TF" output -raw "$1"; }
{
  echo "VERSION=$VERSION"
  echo "KERNA_API_URL=$(sal nucleo_url)"
  echo "KERNA_TABLAS_URL=$(sal nucleo_tablas_url)"
  echo "LOG_ANALYTICS_WORKSPACE_ID=$(az monitor log-analytics workspace show -g rg-kerna-dev -n log-kerna-dev --query customerId -o tsv)"
  echo "OPENAI_RECURSO_ID=$(az cognitiveservices account list -g rg-kerna-dev --query '[0].id' -o tsv)"
  echo "AZ_SUSCRIPCION_ID=$(az account show --query id -o tsv)"
  grep -E '^(VERIDY_CONECTOR_CLAVE|VERIDY_AUDITOR_USUARIO|VERIDY_AUDITOR_CLAVE|KERNA_CLIENT_ID|KERNA_CLIENT_SECRET|KERNA_PANEL_USUARIO|KERNA_PANEL_CLAVE|IDENTITY_ENDPOINT|IDENTITY_HEADER|DEMO_CLIENT_ID|DEMO_CLIENT_SECRET|FRONT_CLAVE)=' "$DIST/secretos.env"
  echo "# Solo si la red exige un proxy para salir a internet (p. ej. http://proxy.miinstitucion.cl:8080):"
  echo "HTTPS_PROXY="
} | tr -d '\r' > "$A/configuracion.env"

echo "5/6 Imágenes en el paquete (para instalar sin descargar nada)"
docker save "veridy-local:$VERSION" "kerna-conector-local:$VERSION" "kerna-panel-local:$VERSION" | gzip -1 > "$A/imagenes.tar.gz"

echo "6/6 Listo: $PAQ ($(du -sh "$PAQ" | cut -f1))"
if [ "$ZIP" = 1 ]; then
  mkdir -p "$RAIZ/.papelera/$(date +%F)/entregable/dist"
  [ -e "$DIST/veridy-kerna-local.zip" ] && mv "$DIST/veridy-kerna-local.zip" "$RAIZ/.papelera/$(date +%F)/entregable/dist/veridy-kerna-local-$(date +%H%M%S).zip"
  (cd "$DIST" && python3 -c "import shutil;shutil.make_archive('veridy-kerna-local','zip','.','veridy-kerna-local')")
  echo "   $DIST/veridy-kerna-local.zip"
fi
