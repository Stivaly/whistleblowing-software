#!/usr/bin/env bash
# Prueba de íconos y logos en producción con navegador real: falla (código 1) si alguno ocupa espacio y no pinta píxeles.
# Recorre la portada y todas las vistas del panel a 390, 1366 y 1920 px (o los anchos que indiques).
# Uso: kerna/operaciones/probar_iconos.sh [anchos...]      Detalle: kerna/operaciones/salida/iconos-fallos.json
exec "$(dirname "$0")/playwright.sh" script "$(dirname "$0")/probar_iconos.py" "$@"
