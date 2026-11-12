#!/usr/bin/env bash
# Compila ECharts 5.5.1 solo con lo que usa el front (barras, líneas, anillos, mapa de calor; canvas) en app/estaticos/echarts.custom.min.js.
# Instala en una carpeta temporal (nada queda en el repo ni en el host).
set -euo pipefail
AQUI="$(cd "$(dirname "$0")" && pwd)"; TMP="$(mktemp -d)"
cp "$AQUI/echarts_entrada.js" "$TMP/entrada.js"
(cd "$TMP" && npm init -y >/dev/null && npm install --silent echarts@5.5.1 esbuild@0.24.0 && npx esbuild entrada.js --bundle --minify --format=iife --target=es2019 --legal-comments=none --outfile=echarts.custom.min.js)
cp "$TMP/echarts.custom.min.js" "$AQUI/../app/estaticos/echarts.custom.min.js"
echo "listo: $(wc -c < "$AQUI/../app/estaticos/echarts.custom.min.js") bytes"
