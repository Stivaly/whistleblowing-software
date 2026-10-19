# Registro de pruebas y mediciones de Kerna

Evidencia de cada prueba y medición, como respaldo de KPIs y SLAs. Una fila por ejecución, la más reciente
arriba, sin textos de denuncias ni secretos. El detalle completo de cada medición de recall (parámetros, hash
del dataset, resultado por ley y por caso) está en `registro/recall_retriever.jsonl`, que el script escribe solo.

Dataset de evaluación: `datos/denuncias_publicas.json` (113 casos, sha256 `26c4bb1c98c1e490…`; excluido de git).
Retriever: Voyage `voyage-4-large`, 1024 dims, `input_type: query`; Qdrant `normativa_cl`, filtro `vigente=true`, top 5.

## Mediciones

| Fecha (UTC) | Commit | Medición | Comando | Resultado | Observaciones |
| --- | --- | --- | --- | --- | --- |
| 2026-10-19 06:54 | 14539bd15+cambios | recall@5, consulta = `resumen_parafraseado` (repetición) | `recall_retriever.py --campo resumen_parafraseado` | Idéntico a la corrida de 06:35 | Desde el cache, 47,8 s, sin llamadas a Voyage. Primera entrada en `registro/recall_retriever.jsonl` para este campo. |
| 2026-10-19 06:54 | 14539bd15+cambios | recall@5, consulta = `texto_original` (repetición) | `recall_retriever.py --campo texto_original` | Idéntico a la corrida de 06:52 | Desde el cache, 67,4 s. Primera entrada en el JSONL para este campo. |
| 2026-10-19 06:52 | 14539bd15+cambios | recall@5, consulta = `texto_original` | `recall_retriever.py --campo texto_original` | (a) ley 0,934 global (19.628-21.719 1,000 · 20.393 0,792 · 21.643 0,966); (b) artículo 0,328 global sobre 61 casos (0,217 · 0,000 · 0,536). "ninguna": top-1 entre 0,175 y 0,537; con umbral 0,55, 0 % de falsos positivos pero solo pasa el 25 % de los positivos | 113 textos (613 mil caracteres) embebidos en unos 17 min por el límite de 10.000 tokens/min de Voyage. Los candidatos citan artículos de definición o catálogo (CT 2, 20.393 art. 1, 19.628 art. 2); el top-5 trae artículos de procedimiento (CT 211-D/E, 20.393 art. 17 ter, 19.628 art. 55). |
| 2026-10-19 06:35 | 14539bd15+cambios | recall@5, consulta = `resumen_parafraseado` | `recall_retriever.py --campo resumen_parafraseado` | (a) ley 0,967 global (19.628-21.719 0,974 · 20.393 0,917 · 21.643 1,000); (b) artículo 0,344 global sobre 61 casos (0,261 · 0,200 · 0,464). "ninguna": top-1 entre 0,131 y 0,363 | Primera corrida, 113 consultas embebidas de cero. Umbrales de 0,30 a 0,70: se bajaron a 0,15–0,55 porque los scores reales son menores. Antes del registro JSONL: se repite desde el cache para que quede registrada. |
| 2026-10-19 06:3x | 14539bd15+cambios | mapeo de `articulos_candidatos` | `recall_retriever.py --solo-mapeo` | Corpus vigente en Qdrant: 144 artículos. Mapeables 61 de 91 (21.643: 28/29 · 19.628-21.719: 23/38 · 20.393: 10/24) | Igual que en la prueba local contra `pipeline_bcn/salida/`. Sin mapeo: citas sin "art." (p. ej. "Ley 21.719 (seguridad)") o fuera del corpus (CP, Ley 19.913, CT 485). |

## Pruebas automatizadas (pytest, sin red)

| Fecha (UTC) | Commit | Suite | Comando | Resultado |
| --- | --- | --- | --- | --- |
| 2026-10-19 06:56 | 14539bd15+cambios | `kerna/evaluacion` + `kerna/pipeline_bcn` | ambas suites, antes del commit | 19 OK + 30 OK |
| 2026-10-19 06:50 | 14539bd15+cambios | `kerna/evaluacion` | `../pipeline_bcn/.venv-test/bin/python -m pytest -q` | 19 OK (incluye el registro JSONL) |
| 2026-10-19 06:40 | 14539bd15+cambios | `kerna/pipeline_bcn` | `.venv-test/bin/python -m pytest -q` | 30 OK (MongoDB de prueba en 127.0.0.1:27018) |
| 2026-10-19 06:38 | 14539bd15+cambios | `kerna/evaluacion` | `../pipeline_bcn/.venv-test/bin/python -m pytest -q` | 1.ª vez: error de import (`embed_sync` fuera del path); corregido el orden de imports → 18 OK |
