#!/usr/bin/env bash
# Prueba de movimiento y CPU en reposo en producción (navegador real, solo lectura): órbitas y satélites de Ajustes, arco, teclado, botón de reintento y «En vivo».
# Uso: kerna/operaciones/probar_movimiento.sh      Salida: kerna/operaciones/salida/movimiento.json (código 1 si algo falla)
exec "$(dirname "$0")/playwright.sh" script "$(dirname "$0")/probar_movimiento.py" "$@"
