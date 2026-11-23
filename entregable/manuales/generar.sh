#!/usr/bin/env bash
# Genera manual-de-usuario.pdf y manual-de-instalacion.pdf a partir de los .html y de capturas/.
# Las cuentas de prueba se toman de entregable/dist/secretos.env (nunca quedan en el repositorio).
# Capturas: herramientas/pw.sh capturar_{inicio,denuncia,auditor}.py (directo en capturas/) y capturar_panel.py
# con OUT=capturas/crudas (los recuadros del panel los dibuja herramientas/anotar.py aquí).
set -euo pipefail
AQUI="$(cd "$(dirname "$0")" && pwd)"; ENT="$(dirname "$AQUI")"
S="$ENT/dist/secretos.env"
val() { sed -n "s/^$1=//p" "$S" | tr -d '\r'; }
[ -d "$AQUI/capturas/crudas" ] && python3 "$ENT/herramientas/anotar.py" "$AQUI/capturas/crudas" "$AQUI/capturas" >/dev/null
for m in manual-de-usuario manual-de-instalacion; do
  sed -e "s/{{AUDITOR_USUARIO}}/$(val VERIDY_AUDITOR_USUARIO)/g" -e "s/{{AUDITOR_CLAVE}}/$(val VERIDY_AUDITOR_CLAVE)/g" \
      -e "s/{{PANEL_USUARIO}}/$(val KERNA_PANEL_USUARIO)/g" -e "s/{{PANEL_CLAVE}}/$(val KERNA_PANEL_CLAVE)/g" \
      "$AQUI/$m.html" > "$AQUI/$m.final.html"
done
cat > "$AQUI/.pdf.py" <<'PY'
import asyncio
from playwright.async_api import async_playwright
PIE = '<div style="font-size:8px;width:100%;text-align:center;color:#888">Página <span class="pageNumber"></span> de <span class="totalPages"></span></div>'
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        pg = await b.new_page()
        for m in ("manual-de-usuario", "manual-de-instalacion"):
            await pg.goto(f"file:///m/{m}.final.html")
            await pg.wait_for_timeout(1500)
            await pg.pdf(path=f"/m/{m}.pdf", format="A4", print_background=True, display_header_footer=True,
                         header_template="<div></div>", footer_template=PIE,
                         margin={"top": "16mm", "bottom": "16mm", "left": "14mm", "right": "14mm"})
            print("PDF", m)
        await b.close()
asyncio.run(main())
PY
docker run --rm -v "$AQUI:/m" mcr.microsoft.com/playwright/python:v1.64.0-noble \
  bash -c "pip install -q --break-system-packages playwright==1.64.0 2>&1 | tail -0; python /m/.pdf.py; chown $(id -u):$(id -g) /m/*.pdf"
ls -la "$AQUI"/*.pdf
