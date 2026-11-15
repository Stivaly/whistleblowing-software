# Relevo de evaluación 2026-11-15
Estado: ver las dos últimas secciones de `kerna/evaluacion/registro-pruebas.md`. Desplegado sin cambios: cfg2 (`vigente/desarrollo` 78,6 %). Flags nuevos apagados: `KERNA_REVISOR_{VOTOS,VETO_MIN,VETO_CITA,ESTRICTO,RELLENO}`, `KERNA_EVALUADOR_VOTOS`.
Falta, en orden:
1. 20.393 arts. 1/3/4 (afinar 0,545 con revisor): analizar fallos en `registro/casos_cfg2_a1_afinar_20261114.json` (solo IDs); cambio general (enriquecimiento `rol` o criterio del evaluador), medir en afinar, luego desarrollo; nunca ajustar con medir_complejas (ya medida una vez: 0,841).
2. Partir arts. 82/84 por letra: solo si el análisis de fallos de afinar lo justifica; requiere reindexar con `indexar_enriquecido.sh`.
3. Estabilidad en desarrollo: repetir 3 veces cada candidato (`medicion_config_exp2.sh ETIQ 20261114 desarrollo VAR=…`, ~50 min por corrida) o ampliar con más casos reales.
4. Si una configuración mejora desarrollo de forma estable: subir imagen (`infra/scripts/subir_imagen_kerna.sh nucleo --tag … --desplegar`), `echo n | infra/aplicar.sh kerna`, y `subir_medicion_cfg2.py --escribir` para la fila vigente.

## Cierre del orquestador 2026-11-15 04:50
- El agente de varianza se cortó al cerrar la sesión. Su código quedó commiteado con flags apagados y sin medir: `KERNA_AZURE_OPENAI_SEED`, `KERNA_EVALUADOR_ESFUERZO`, `KERNA_EVALUADOR_ORDEN`. Hay una corrida de humo (`registro/var_humo_desarrollo_20261115.json`); la corrida v1 (base / alt3 / medio, 3 repeticiones) no terminó.
- Siguiente, en orden:
  1. Medir v1 en desarrollo, 3 corridas por variante, con `medicion_config_exp2.sh`. Mirar la media y el rango.
  2. Analizar los fallos de 20.393 (arts. 1/3/4) en `afinar` y desarrollo.
  3. Tomar la mejor variante: confirmarla una vez en prueba, prueba2, prueba3 y medir_complejas; desplegarla si la media de desarrollo da 0,80 o más, y actualizar la fila vigente.
