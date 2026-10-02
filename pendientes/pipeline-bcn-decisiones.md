# Pipeline BCN — decisiones y pendientes (2026-10-02)

## Hecho
- Código del pipeline desempaquetado de `fable upgrades/kerna_codigo.zip` en `kerna/pipeline_bcn/` (los zip quedan intactos).
- `extraer_bcn.py` reescrito: el original no funcionaba con el XML real (0 artículos en el Código Penal). Detalle en `kerna/pipeline_bcn/README.md`.
- 7 pruebas (`test_extraer_bcn.py`, con mongomock), todas OK.
- Las 10 normas de la lista del plan están verificadas con `--verificar` y tienen su idNorma, pero todas quedan `"activa": false`: la usuaria indicará qué leyes extraer.
- NO se ha hecho ninguna extracción a Mongo ni a `salida/`. Las descargas de prueba quedaron solo en el scratchpad de la sesión.

## Decisiones tomadas sin preguntar
- Ubicación `kerna/pipeline_bcn/` en la raíz del repo (el plan usaba `/opt/kerna/pipeline_bcn` solo como ruta de despliegue en `crontab.txt`).
- Los artículos que desaparecen de una norma no se borran: quedan `vigente: false` (coherente con la regla de no eliminar).
- Límite de fragmento: 5.000 caracteres (~1.500 tokens), partiendo por inciso y luego por oración.

## Para decidir / tener en cuenta
- **Leyes modificatorias** (Ley 21.643 Karin, Ley 21.719): su XML contiene sobre todo instrucciones del tipo "Modifícase el Código del Trabajo…". El contenido sustantivo vive en la norma modificada (Código del Trabajo, Ley 19.628), que la BCN entrega ya consolidada. Para el RAG conviene priorizar la norma consolidada; la ley modificatoria aporta poco por sí sola.
- Ley 21.719: su texto vigente en la Ley 19.628 depende de su entrada en vigencia. Revisar qué versión entrega la BCN al momento de extraer.
- Algunos textos antiguos del Código del Trabajo traen notas marginales mezcladas en el texto (p. ej. "L. 18.620 … ART. PRIMERO"). Es así en el XML de la BCN; no se limpian.
- Falta `MONGODB_URI` (cluster Atlas M0) para la carga real.
