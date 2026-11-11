#!/usr/bin/env bash
# Libera disco de Docker en el host: contenedores de prueba detenidos, imágenes históricas y caché de build.
# No toca lo desplegado ni lo que está corriendo, ni n8n/evolution/qdrant, ni volúmenes.
# Uso: infra/limpiar_docker.sh
set -uo pipefail

echo "== Antes"; docker system df

docker ps -a --filter status=exited --filter status=created --format '{{.Names}}' \
  | grep -E '^(kerna-probar-|veridy-test-1012-|veridy-pgtest|kerna-mongo-test)' \
  | xargs -r docker rm >/dev/null
docker network rm veridy-pgtest-net 2>/dev/null

R=acrkernadevg6mzy.azurecr.io
docker rmi \
  $R/kerna-eval-embeddings:v1 \
  $R/kerna-pipeline:af8193732 $R/kerna-pipeline:v2 $R/kerna-pipeline:v1 \
  $R/kerna-nucleo:5817f8e57 $R/kerna-conector:86ea66b68-1 $R/veridy:v1 \
  kerna-conector:local kerna-nucleo:local docker_globaleaks:latest \
  cypress/included:15.4.0 mcr.microsoft.com/playwright/python:v1.49.0-noble \
  mongo:8.0 postgres:16 2>&1 | grep -iE "error" || true

docker image prune -f >/dev/null
docker builder prune -f >/dev/null

echo "== Después"; docker system df; df -h / | tail -1
