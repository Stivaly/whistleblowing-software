# Relevo: probar la regla de la 20.393 y revisar qué cuenta como acierto (2026-11-16)

Para continuar en otra sesión. Lee antes `.claude/CLAUDE.md`, tu memoria `MEMORY.md` y de `pendientes/orquestador-2026-11-13.md` las reglas para cada agente y «Ahorro de tokens». Decisión de la usuaria: **se descarta el revisor** (no se mide con revisor; se mira la cadena sin revisor). Quiere probar los puntos 1 y 2 de abajo.

## Dónde estamos
- Recall@5 por artículo, desarrollo (42 casos), nano, base desplegada: evaluador 0,738, cadena 0,770, cadena + revisor 0,706 (media de 3 corridas). Ruido entre corridas ±0,07.
- gpt-5-mini (todas las etapas) en desarrollo, 2 corridas: evaluador 0,738, cadena 0,810 / 0,786, con revisor 0,786 / 0,714. **No hay diferencia clara con nano** (dentro del ruido); en 20.393 (9 casos) mini 0,667 = base. Conclusión: el modelo no es el cuello. No pagar mini por esto.
- El retriever trae el artículo correcto entre los 70 candidatos casi siempre (0,95-1,00); se pierde al elegir el top-5 (evaluador). Análisis de fallos de 20.393 en `kerna/evaluacion/registro/analisis_20393_20261115.md`: 8 de 14 fallos son del evaluador (arts. 1, 3 y 4 entre los 70 pero fuera del top-5).
- `KERNA_EVALUADOR_HABILITANTE=1` (reserva un lugar para la norma habilitante): en afinar subió 20.393 de 0,545 a 0,818 y la cadena de 0,881 a 0,929. **Corrida única en el set donde se diseñó: falta confirmarla en desarrollo.** `KERNA_REVISOR_ALCANCE_NO_VETA` se descartó (no aportó).
- Set `desarrollo_nuevo` (206 casos, 172 con falta): mini da cadena 0,948; la etapa de búsqueda sola acierta 0,855 top-5 frente a 0,738 en los 42, así que **sigue siendo más fácil que los 42** y no tiene base con nano. No usarlo para concluir hasta tenerla.
- Presupuesto: Azure for Students; gasto de noviembre 26,45 USD al 15-nov más ~12,8 estimados de la prueba de mini (precios de lista x1,5). **Tope de la usuaria: no gastar más de unos 10 USD en lo que sigue.** Cada corrida de 42 casos con nano cuesta ~0,3-0,4 USD (estimación; los tokens por caso pueden estar subestimados, hasta el doble). Consultar Cost Management (`az rest` a `Microsoft.CostManagement/query`, tiene retraso) antes y después.
- El despliegue `gpt-5-mini` quedó en capacidad 600 (antes 50); `gpt-5-nano` en 250. Tier 1 (sube a Tier 2 solo el 19-nov-2026). El script `kerna/operaciones/mini_con_tope.sh` ya existe, no hace falta para esto.

## Encargos (en orden)
### 0. Dejar registrado lo ya hecho (sin gastar)
Registrar en `kerna/evaluacion/registro-pruebas.md` la sección «2026-11-16 · gpt-5-mini en desarrollo y desarrollo_nuevo» con los números de arriba (archivos `registro/cfg2-mx{1,2,3}-*`, `casos_cfg2_mx*`, `mini_tope_20261116.log`; `cfg2-mx1` se generó a mano con `medir_base_b2.py` porque el script coordinador se reinició). Commitear solo esos archivos y `mini_con_tope.sh`.

### 1. Regla de la 20.393 («norma habilitante») en desarrollo, sin revisor
- Medir `KERNA_EVALUADOR_HABILITANTE=1` en los 42 de desarrollo, **3 repeticiones**, con nano, y comparar con la base sin la flag (ya hay 3 corridas base en `registro/cfg2-v*-desarrollo-20261115.json`; si hace falta una base nueva sin revisor, repetir 3).
- Comando: `KERNA_CONCURRENCIA=3 kerna/operaciones/medicion_config_exp2.sh dh{1,2,3} 20261116 desarrollo KERNA_EVALUADOR_HABILITANTE=1 KERNA_REVISOR=0` (el último valor gana; confirmar en `registro/flags_cfg2_dh1_desarrollo_20261116.txt` que el revisor quedó apagado y que `medir_base_b2.py` informa «cadena»). Mirar la columna **cadena** y la fila 20.393 (9 casos); ignorar «revisor».
- Criterio: se adopta si la media de la cadena sube y 20.393 sube en las 3 corridas, más que el ruido (±0,07). Mirar también que no baje 19.628-21.719 ni 21.643 (comparación pareada con `kerna/evaluacion/combinar_ampliado.py`).
- No ajustar nada con `medir_complejas` (ya medida una vez, 0,841). Si se adopta, confirmar una vez en prueba, prueba2 y prueba3 y recién entonces desplegar (flag en el despliegue del núcleo con `kerna/desplegar.sh`/script del repo; nunca comandos sueltos) y actualizar la fila vigente del panel.

### 2. Qué cuenta como acierto (punto 4 de la usuaria)
La métrica exige el **artículo exacto** de la etiqueta. Falta saber cuántos «fallos» son en realidad sugerencias válidas distintas de la etiqueta.
- Tomar los fallos de la cadena (sin revisor) en los 42 y en una muestra de `desarrollo_nuevo` (usar `registro/casos_cfg2_*` solo con IDs; el texto está en `kerna/evaluacion/datos/`). Para cada fallo, leer el relato completo y clasificar el artículo sugerido que reemplazó al esperado: (a) incorrecto, (b) válido y equivalente al esperado (misma conducta y misma norma, otro artículo de la misma ley), (c) válido adicional que la etiqueta no incluía.
- Encargarlo a agentes Sonnet nuevos (esfuerzo medio, máx. 2 a la vez, relevo a ~250k de contexto, uno por tanda de casos, datos a archivos y resumen corto de vuelta). Auditar tú una muestra de sus clasificaciones.
- Salida: «acierto estricto» (actual) frente a «acierto con equivalentes» (a + c), por set y por ley, con IC. Si la diferencia es grande, proponer cambiar la métrica del panel o ampliar las etiquetas, y dejarlo para que decida la usuaria (no cambiar el panel solo).
- Registrar todo en `registro-pruebas.md` con fecha, commit, parámetros y resultado.

## Reglas
- Nada se elimina (mover a `.papelera/AAAA-MM-DD/...` y anotar en `pendientes/eliminaciones-pendientes.md`). Commitear solo archivos propios, con rutas explícitas.
- Medir solo con scripts (`kerna/operaciones/*`), con esperas largas y pocos turnos: la cuota de Claude de la usuaria está baja.
- Antes de gastar, estimar el costo con los tokens por caso y no pasar del tope; si la proyección lo supera, parar y dejarlo escrito.
- No lanzar `claude`/sesiones nuevas sin que lo pida la usuaria. Dejar el avance en un archivo nuevo `pendientes/resumen-criterio-y-metrica-2026-11-16.md`.
