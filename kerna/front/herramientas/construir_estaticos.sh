#!/usr/bin/env bash
# Reconstruye los archivos estáticos del front con versiones fijas (sin CDN en producción):
#   estaticos/tailwind.css  Tailwind CLI 3.4.17 compilado contra plantillas/ y estaticos/kerna.js
#   estaticos/echarts.min.js  Apache ECharts 5.5.1
#   estaticos/iconos.svg  sprite con los íconos usados de Lucide 0.469.0 (lista en herramientas/iconos.txt)
#   estaticos/fuentes/inter-*.woff2  Inter (latin) de @fontsource/inter 5.1.0
# Uso: kerna/front/herramientas/construir_estaticos.sh   (requiere node/npm y red solo al instalar los paquetes)
set -euo pipefail
AQUI="$(cd "$(dirname "$0")" && pwd)"; APP="$AQUI/../app"; EST="$APP/estaticos"
TMP="$(mktemp -d)"; cd "$TMP"
npm init -y >/dev/null
npm install --silent --no-audit --no-fund tailwindcss@3.4.17 echarts@5.5.1 lucide@0.469.0 @fontsource/inter@5.1.0
cp node_modules/echarts/dist/echarts.min.js "$EST/echarts.min.js"
for p in 400 500 600 700; do cp "node_modules/@fontsource/inter/files/inter-latin-$p-normal.woff2" "$EST/fuentes/"; done
node "$AQUI/sprite_iconos.js" "$TMP/node_modules/lucide/dist/cjs/lucide.js" "$AQUI/iconos.txt" "$EST/iconos.svg"
cp "$AQUI/tailwind.config.js" "$AQUI/entrada.css" "$TMP/"
sed -i "s#__APP__#$APP#g" "$TMP/tailwind.config.js"
npx tailwindcss -c "$TMP/tailwind.config.js" -i "$TMP/entrada.css" -o "$EST/tailwind.css" --minify
echo "listo: $EST"
