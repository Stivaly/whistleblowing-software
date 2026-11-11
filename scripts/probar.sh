#!/usr/bin/env bash
# Suite de pruebas de Kerna: un comando por capa, resultados en reportes/pruebas/<AAAAMMDD-HHMM>-<commit>/.
# Uso: scripts/probar.sh [unitarias|integracion|e2e|carga|veridy|todo]   (ver kerna/pruebas/README.md)
# Imprime solo un resumen corto; la salida completa de cada capa queda en salida-*.log del reporte.
set -uo pipefail

CAPA="${1:-unitarias}"
RAIZ="$(git -C "$(dirname "$0")" rev-parse --show-toplevel)"
PY=/usr/bin/python3
cd "$RAIZ" || exit 2

COMMIT="$(git rev-parse --short=9 HEAD)"
COMMIT_COMPLETO="$COMMIT"
[ -n "$(git status --porcelain -- . ':!reportes' 2>/dev/null)" ] && COMMIT_COMPLETO="${COMMIT}+cambios"
OUT="$RAIZ/reportes/pruebas/$(date -u +%Y%m%d-%H%M)-$COMMIT"
mkdir -p "$OUT"
export KERNA_SEMILLA="${KERNA_SEMILLA:-20260101}"
export PYTHONDONTWRITEBYTECODE=1

PLAYWRIGHT_IMAGEN="mcr.microsoft.com/playwright/python:v1.64.0-noble"
VERIDY_IMAGEN_PRUEBAS="${VERIDY_IMAGEN_PRUEBAS:-veridy-pgtest}"
CONT_E2E="kerna-probar-e2e-v1.64.0"
CONT_VERIDY="kerna-probar-veridy"
CONT_PG="kerna-probar-pg"
RED_PG="kerna-probar-net"
DENTRO=()   # contenedores que esta corrida inició (se detienen al final; nunca se eliminan)

log() { printf '%s\n' "$*" >> "$OUT/proceso.log"; }
error_capa() { printf '%s\n' "$2" > "$OUT/error-$1.txt"; }
espera() {  # espera <segundos> <comando...>: reintenta hasta que el comando tenga éxito o venza el tope
  local fin=$(( $(date +%s) + $1 )); shift
  until "$@" >/dev/null 2>&1; do
    [ "$(date +%s)" -ge "$fin" ] && return 1
    sleep 1
  done
}
pytest_base() {  # pytest_base <nombre-archivo> <args...>
  local n="$1"; shift
  KERNA_MARCAS_JSON="$OUT/marcas-$n.json" PYTHONPATH="$RAIZ/kerna/pruebas${PYTHONPATH:+:$PYTHONPATH}" \
    "$PY" -m pytest -c kerna/pytest.ini -p plugin_resumen -p no:cacheprovider -q --junitxml="$OUT/junit-$n.xml" "$@" \
    > "$OUT/salida-$n.log" 2>&1
  echo $? > "$OUT/rc-$n.txt"
}

capa_unitarias() {
  pytest_base unitarias kerna/pruebas/unitarias -n auto -m "not integracion and not e2e and not carga"
  # Pruebas previas del pipeline y de la evaluación: en serie (comparten la base MongoDB de prueba).
  if ! (exec 3<>/dev/tcp/127.0.0.1/27018) 2>/dev/null && docker inspect kerna-mongo44-test >/dev/null 2>&1; then
    log "iniciando kerna-mongo44-test"
    docker start kerna-mongo44-test >/dev/null 2>&1 && DENTRO+=("kerna-mongo44-test")
    espera 30 bash -c 'exec 3<>/dev/tcp/127.0.0.1/27018'
  fi
  local previas=()
  for f in kerna/pipeline_bcn/test_*.py kerna/evaluacion/test_*.py; do previas+=("$f"); done
  pytest_base unitarias-previas "${previas[@]}"
}

capa_integracion() {
  # Variables de kerna/pipeline_bcn/.env en un subshell, sin imprimirlas.
  (
    [ -f kerna/pipeline_bcn/.env ] && { set -a; . kerna/pipeline_bcn/.env; set +a; }
    pytest_base integracion kerna/pruebas/integracion -m integracion
  )
}

veridy_estado() { infra/veridy/veridy.sh estado 2>&1; }
capa_e2e() {
  local est; est="$(veridy_estado)"
  echo "$est" > "$OUT/veridy-estado.txt"
  if ! grep -Eq '^Veridy:[[:space:]]+Running' <<<"$est"; then
    if [ "${PROBAR_ENCENDER_VERIDY:-0}" = "1" ]; then
      infra/veridy/veridy.sh encender > "$OUT/veridy-encender.log" 2>&1
      est="$(veridy_estado)"
    fi
  fi
  if ! grep -Eq '^Veridy:[[:space:]]+Running' <<<"$est"; then
    error_capa e2e "Veridy no está Running. Enciéndalo con infra/veridy/veridy.sh encender o use PROBAR_ENCENDER_VERIDY=1."
    return
  fi
  local url="${VERIDY_URL:-$(sed -n 's/^Link:[[:space:]]*//p' <<<"$est" | head -1)}"
  [ -z "$url" ] && { error_capa e2e "No se pudo determinar VERIDY_URL."; return; }
  espera 180 curl -sf --max-time 5 "$url/api/health" || { error_capa e2e "Veridy no responde en $url/api/health."; return; }
  docker image inspect "$PLAYWRIGHT_IMAGEN" >/dev/null 2>&1 || docker pull -q "$PLAYWRIGHT_IMAGEN" >/dev/null 2>&1 \
    || { error_capa e2e "No se pudo obtener la imagen $PLAYWRIGHT_IMAGEN."; return; }
  if ! docker inspect "$CONT_E2E" >/dev/null 2>&1; then
    docker run -d --name "$CONT_E2E" --ipc=host --user "$(id -u):$(id -g)" -e HOME=/tmp \
      -v "$RAIZ/kerna:/repo/kerna:ro" -v "$OUT:/reporte" --entrypoint tail "$PLAYWRIGHT_IMAGEN" -f /dev/null >/dev/null 2>&1 \
      || { error_capa e2e "No se pudo crear el contenedor $CONT_E2E."; return; }
  else
    # el montaje del reporte cambia en cada corrida: se recrea el contenedor con otro nombre solo si hace falta
    if ! docker inspect "$CONT_E2E" --format '{{range .Mounts}}{{.Source}} {{end}}' | grep -q "^$OUT \| $OUT "; then
      docker stop "$CONT_E2E" >/dev/null 2>&1
      CONT_E2E="${CONT_E2E}-$(date -u +%Y%m%d%H%M)"
      docker run -d --name "$CONT_E2E" --ipc=host --user "$(id -u):$(id -g)" -e HOME=/tmp \
        -v "$RAIZ/kerna:/repo/kerna:ro" -v "$OUT:/reporte" --entrypoint tail "$PLAYWRIGHT_IMAGEN" -f /dev/null >/dev/null 2>&1 \
        || { error_capa e2e "No se pudo crear el contenedor de e2e."; return; }
    else
      docker start "$CONT_E2E" >/dev/null 2>&1
    fi
  fi
  DENTRO+=("$CONT_E2E")
  docker exec "$CONT_E2E" sh -c 'PYTHONPATH=/tmp/pylib python3 -c "import pytest, pytest_timeout, playwright" 2>/dev/null || python3 -m pip install -q --target /tmp/pylib pytest pytest-timeout playwright==1.64.0' \
    > "$OUT/salida-e2e-preparar.log" 2>&1
  docker exec -e VERIDY_URL="$url" -e VERIDY_USUARIO -e VERIDY_PASSWORD -e KERNA_ARTEFACTOS=/reporte/artefactos-e2e \
    -e KERNA_MARCAS_JSON=/reporte/marcas-e2e.json -e KERNA_SEMILLA -e PYTHONDONTWRITEBYTECODE=1 \
    -e PYTHONPATH=/tmp/pylib:/repo/kerna/pruebas -w /repo/kerna "$CONT_E2E" \
    python3 -m pytest -c /repo/kerna/pytest.ini --rootdir /repo/kerna -p plugin_resumen -p no:cacheprovider -q \
      --junitxml=/reporte/junit-e2e.xml pruebas/e2e -m e2e > "$OUT/salida-e2e.log" 2>&1
  echo $? > "$OUT/rc-e2e.txt"
}

capa_carga() {
  local f
  for f in KERNA_API_URL KERNA_CLIENT_ID KERNA_CLIENT_SECRET; do
    if [ -z "${!f:-}" ]; then
      if [ "$CAPA" = "todo" ]; then log "carga omitida: falta $f"; return; fi
      error_capa carga "Faltan variables de carga (KERNA_API_URL, KERNA_CLIENT_ID, KERNA_CLIENT_SECRET)."; return
    fi
  done
  local ini; ini=$(date +%s)
  "$PY" -m locust -f kerna/pruebas/carga/locustfile.py --headless \
    -u "${CARGA_USUARIOS:-3}" -r "${CARGA_TASA:-1}" -t "${CARGA_DURACION:-60s}" \
    --csv "$OUT/carga" --only-summary > "$OUT/salida-carga.log" 2>&1
  echo $? > "$OUT/rc-carga.txt"
  [ -f "$OUT/carga_stats.csv" ] && "$PY" kerna/pruebas/herramientas/carga_a_junit.py "$OUT/carga" \
    "$OUT/junit-carga.xml" "$OUT/marcas-carga.json" --duracion "$(( $(date +%s) - ini ))" >> "$OUT/salida-carga.log" 2>&1
}

capa_veridy() {
  docker image inspect "$VERIDY_IMAGEN_PRUEBAS" >/dev/null 2>&1 || { error_capa veridy "Falta la imagen docker $VERIDY_IMAGEN_PRUEBAS."; return; }
  local motores="${PROBAR_VERIDY_MOTORES:-sqlite,pg}" mods="${PROBAR_VERIDY_MODULOS:-globaleaks.tests}" m
  if docker inspect "$CONT_VERIDY" >/dev/null 2>&1; then docker start "$CONT_VERIDY" >/dev/null 2>&1
  else
    docker run -d --name "$CONT_VERIDY" -v "$RAIZ/backend:/src:ro" --entrypoint tail "$VERIDY_IMAGEN_PRUEBAS" -f /dev/null >/dev/null 2>&1 \
      || { error_capa veridy "No se pudo crear el contenedor $CONT_VERIDY."; return; }
  fi
  DENTRO+=("$CONT_VERIDY")
  local pg_uri=""
  if [[ ",$motores," == *,pg,* ]]; then
    docker network inspect "$RED_PG" >/dev/null 2>&1 || docker network create "$RED_PG" >/dev/null 2>&1
    if docker inspect "$CONT_PG" >/dev/null 2>&1; then docker start "$CONT_PG" >/dev/null 2>&1
    else docker run -d --name "$CONT_PG" --network "$RED_PG" -e POSTGRES_HOST_AUTH_METHOD=trust postgres:15 >/dev/null 2>&1; fi
    DENTRO+=("$CONT_PG")
    docker network connect "$RED_PG" "$CONT_VERIDY" >/dev/null 2>&1
    if espera 60 docker exec "$CONT_PG" pg_isready -U postgres; then
      docker exec "$CONT_PG" psql -U postgres -tc "select 1 from pg_database where datname='veridy_test'" | grep -q 1 \
        || docker exec "$CONT_PG" createdb -U postgres veridy_test >/dev/null 2>&1
      pg_uri="postgresql+psycopg2://postgres@$CONT_PG:5432/veridy_test?sslmode=disable"
    else
      error_capa veridy "PostgreSQL de prueba no arrancó."; return
    fi
  fi
  local pids=()
  for m in ${motores//,/ }; do
    local uri=""; [ "$m" = "pg" ] && uri="$pg_uri"
    (
      timeout "${PROBAR_VERIDY_TOPE:-1800}" docker exec -e GLOBALEAKS_TEST_PG_URI="$uri" "$CONT_VERIDY" sh -c \
        "D=/tmp/run-$m; mkdir -p \$D && cp -r /src/. \$D/ && cd \$D && python3 -m twisted.trial --reporter=bwverbose $mods" \
        > "$OUT/salida-veridy-$m.log" 2>&1
      echo $? > "$OUT/rc-veridy-$m.txt"
      "$PY" kerna/pruebas/herramientas/trial_a_junit.py "$OUT/salida-veridy-$m.log" "$OUT/junit-veridy-$m.xml" --nombre "veridy-$m"
    ) &
    pids+=($!)
  done
  wait "${pids[@]}"
}

case "$CAPA" in
  unitarias|integracion|e2e|carga|veridy) capas=("$CAPA") ;;
  todo) capas=(unitarias integracion e2e carga veridy) ;;
  *) echo "Uso: $0 [unitarias|integracion|e2e|carga|veridy|todo]" >&2; exit 2 ;;
esac
for c in "${capas[@]}"; do "capa_$c"; done

for c in "${DENTRO[@]}"; do docker stop "$c" >/dev/null 2>&1; done   # se detienen, no se eliminan

"$PY" kerna/pruebas/herramientas/resumen.py "$OUT" --commit "$COMMIT" --commit-completo "$COMMIT_COMPLETO" \
  --registro "$RAIZ/kerna/evaluacion/registro"
estado=$?
"$PY" kerna/evaluacion/matriz_pruebas.py >> "$OUT/proceso.log" 2>&1
exit $estado
