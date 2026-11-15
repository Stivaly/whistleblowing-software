# Front: el total de casos debe ser el de Veridy (anotado 2026-11-15, sin ejecutar)

La usuaria reporta: el front sigue diciendo «en total 433 casos». Debe decir el total de casos que realmente existen en Veridy (hoy 116 según el cierre del orquestador) y nada más.

- Estado: solo anotado. No se ha tocado código ni se ha pedido nada al agente/orquestador.
- Pistas para quien lo retome: `kerna/front/app/consultas.py:96` (`total_casos`) y `kerna/front/app/vistas.py:128` (`tot = m["total_casos"]`). El 433 no aparece en el código del front; probablemente sale de datos sembrados (`kerna/front/sembrar_negocio.py`) o de la tabla propia de Kerna, no de Veridy. Sin verificar.

## Hecho 2026-11-15 (commit 1d17560f8)
- Causa: `total_casos` sumaba los eventos `solicitud_terminada` de Log Analytics (433 en 7 días, con reintentos y casos ya borrados). Ahora Resumen, Informe, PDF/Excel/CSV usan `casos` y `con_sugerencia` de la fila `conector` (118 al 14-nov 20:18); sin fila del conector queda la telemetría.
- Falta: los satélites del anillo del Resumen (principal/respaldo/local) siguen siendo eventos de telemetría por modo (suman 135 contra 118 en el centro).
- Falta: `probar_front.sh` falla en «descarga del PDF: 500» en producción, también con el commit anterior b160b71cc (en local el PDF sale 200). Investigar aparte.
