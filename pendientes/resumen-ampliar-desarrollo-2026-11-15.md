# Ampliar desarrollo · avance 2026-11-15

## Hecho
- 160 relatos nuevos DX-0001…0160 (partición `desarrollo_nuevo`), escritos por 4 agentes Sonnet, etiquetados a mano por 2 agentes con `etiquetar_cx.py … dx` sobre el texto vigente del corpus. Quedaron 135 `si`, 12 `control` y 13 `no`. Por ley: 20.393 44, 19.628-21.719 35, 21.643 34, estatutos 22.
- Datos (fuera de git): `kerna/evaluacion/datos/denuncias_desarrollo_20261115_{auditadas,etiquetadas}.json`, `dx_etiquetas.jsonl`, lotes y encargos en `datos/dx_lotes/`.
- Disjuntos: el máximo de 8-gramas compartidos con prueba, prueba2, prueba3, afinar, medir_complejas, públicas y Veridy es 2,7 %.
- Código (commit 657689884): partición `desarrollo_nuevo` en recall_retriever, correr_revisor, medir_base_b2 y medicion_config_exp2.sh, y lote `dx` en etiquetar_cx.py. Script nuevo `kerna/evaluacion/combinar_ampliado.py`: une, por corrida, los 42 con los nuevos y da cada set por separado, el ampliado y la diferencia pareada entre variantes.

## Auditoría (67 casos leídos completos: uno de cada cuatro, más todos los de confianza baja, control y no)
- Etiquetas: ninguna cambiada. Los 5 casos 20.393 de confianza baja son fraudes contra la propia empresa (art. 3, inciso final); se dejaron `si` igual que en B6 (CX-0008).
- Textos corregidos:
  - DX-0041, 0043 y 0045 eran clones de 0001, 0002 y 0004. Los reescribí y los reetiqueté.
  - DX-0143, 0144, 0145, 0146, 0149, 0158, 0159 y 0100 tenían un cierre pegado de otro relato. Lo quité.
  - Cambié 35 correos `.example` por dominios creíbles.
  - Las versiones anteriores quedaron en `dx_lotes/*_v1*`.
- **Sesgo de dificultad:** los relatos nuevos son más explícitos que los 42 originales. Llevan 3,45 artículos esperados por caso frente a 2,55, y en 20.393 dicen casi siempre «no hay canal ni modelo». Por eso la base saca 0,963 en los nuevos y 0,714 en los 42. El ampliado no es comparable en nivel con el histórico; sirve para comparar variantes entre sí.

## Tamaño
- Con p ≈ 0,75, un IC 95 % de ±0,04 exige unos 450 casos. El ampliado tiene 177 (42 + 135), lo que da unos ±0,06 de IC por corrida. La comparación entre variantes usa la diferencia pareada por caso, que es más estrecha.
- Lotes 5 y 6 (80 relatos más, DX-0161…0240) están escritos con fichas de diversidad (`dx_lotes/fichas_lote*.json`), pero **sin etiquetar ni auditar** y fuera de la partición. Los lotes 7 a 11 (fichas listas) no se escribieron porque se acabó la cuota de agentes a las 17:30.

## Mediciones
Ver `kerna/evaluacion/registro-pruebas.md` (2026-11-15 · ampliación de desarrollo).

## Pendiente (en orden; superado por «Reescritura difícil»)
1. Si no terminaron hoy, completar las repeticiones 2 y 3 (`var3_dv{b,a}{2,3}.log`) y combinarlas con `combinar_ampliado.py`.
2. Antes de seguir generando, endurecer las fichas para que se parezcan a los 42 en dificultad: hechos ambiguos, sin decir si hay o no modelo de prevención, y 2-3 artículos esperados.
3. Etiquetar y auditar los lotes 5 y 6 (y los 7 a 11) en un lote nuevo separado; no mezclarlos en `desarrollo_nuevo` mientras haya mediciones abiertas sobre él.

## Reescritura difícil (2026-11-15 22:05 a 2026-11-16 06:45)
- La usuaria detuvo las mediciones de la cadena sobre `desarrollo_nuevo` porque los casos eran fáciles: base 0,963 en los nuevos frente a 0,714 en los 42.
- Los 42 son fallos, noticias y dictámenes (683 palabras, 2,55 artículos, casi nunca dicen si hay canal o modelo). Con ese molde se reescribieron 206 casos (DX-0001…0206, que incluye los lotes 5 y 6). Los escribieron agentes Sonnet a partir de fichas `dx_lotes/fichas_dificil_*.json`.
- Etiquetas: 172 `si`, 14 `control` y 20 `no`; 2,47 artículos por caso. Auditados 130; un cambio (DX-0064). Siguen disjuntos (máximo 0,8 %).
- Calibración con el retriever solo: 0,512 [0,44-0,58] frente a 0,643 de los 42. Por ley: 21.643 0,69 y datos personales 0,65, iguales a los 42; 20.393 0,28 (42: 0,44); estatutos 0,47. Con el reparto de leyes de los 42 daría ≈0,59. Detalle en `kerna/evaluacion/registro-pruebas.md`.
- Versiones anteriores, nada eliminado: `dx_lotes/*_v1` (fácil, antes de la auditoría), `_v2` (fácil, auditada), `_v3` (difícil antes de ajustes), `_v4` (ajuste 1).
- Lotes 7 a 11: no se generaron. Con 206 casos (172 con falta) ya se supera el objetivo de ≥150, y el IC por corrida queda en ≈±0,07.

## Pendiente
1. Decisión de la usuaria: retomar la comparación base/alt3 (3 corridas) sobre `desarrollo_nuevo` ya difícil, y combinarla con los 42 con `combinar_ampliado.py`.
2. Si se quiere un 20.393 más parecido a los 42, la siguiente palanca es el formato noticia de causas conocidas; no se tocó para no sobreajustar al retriever.
