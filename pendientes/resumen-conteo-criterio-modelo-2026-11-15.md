# Conteo, criterio 20.393 y modelo (2026-11-15/16)

## 1. Conteo del Resumen: hecho
- Conector publica conteos por modo de la sugerencia final (`342696e3a`, imagen `342696e3a` desplegada). Front `738f15aa3` desplegado: 118 denuncias = 117 principal + 1 respaldo, 100 % = con sugerencia / denuncias. Informe, PDF, Excel y CSV con las mismas cifras.
- 500 del PDF: recall por ley vacío en la medición (`738f15aa3`). `probar_front.sh` pasa entero.
- Capturas `kerna/front/diseno-v2/capturas/prod15-conteo-*` (Chromium y Firefox, 390/1366/1920); script `kerna/operaciones/verificar_conteo.py`.
- Pendiente menor: costo del período 0,19 en pantalla y «—» en el PDF; añadir `verificar_conteo.py` al índice de scripts.

## 2-3. Criterio 20.393 y gpt-5-mini
- Afinar: ver `kerna/evaluacion/registro-pruebas.md` (h1 20.393 0,545 → 0,818; m1 c+r 0,929; n1 descartado).
- Desarrollo ×3 en curso: logs `kerna/evaluacion/registro/var5_dh.log` y `var5_dm.log`.

## Pendiente de despliegue (tras la sesión hermana)
- Ninguno aún; depende de desarrollo ×3.
