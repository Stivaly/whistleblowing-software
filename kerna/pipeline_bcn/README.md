# Pipeline normativo BCN (LeyChile) → MongoDB → Qdrant

Código base: `fable upgrades/kerna_codigo.zip` (plan en `fable upgrades/04_PIPELINE_BCN.md` y `05_EMBEDDINGS_VECTORDB.md`).
El extractor se reescribió el 2026-10-02 tras probarlo contra XML reales de la BCN (ver "Cambios").

## Instalación

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt      # producción
docker run -d --name kerna-mongo44-test -p 127.0.0.1:27018:27017 mongo:4.4   # una vez: MongoDB de prueba (5+ exige AVX)
.venv/bin/pip install -r requirements-dev.txt && .venv/bin/python -m pytest -q   # pruebas
```

## Uso

```bash
# 1. Verificar una norma antes de agregarla a leyes.json (solo lee metadatos)
python3 extraer_bcn.py --verificar idLey=21643 idNorma=1984

# 2. Extraer: solo las normas con "activa": true en leyes.json…
python3 extraer_bcn.py
# …o solo las indicadas (idNorma, idLey o parte del nombre), aunque estén inactivas
python3 extraer_bcn.py --normas 1984 "Ley Karin"

# Revisión sin tocar Mongo (deja salida/<idNorma>.json)
python3 extraer_bcn.py --dry-run --normas 1984

# Con Mongo
export MONGODB_URI='mongodb+srv://USER:PASS@cluster.mongodb.net/kerna'
python3 extraer_bcn.py --normas 1984
```

Otros flags: `--solo-prioridad N`, `--forzar` (re-evaluar fragmentos aunque el XML no haya cambiado), `--xml-local DIR` (procesar `idNorma=N.xml` ya descargados), `-v`.

## Colecciones Mongo (db por defecto de la URI)

| Colección | Contenido |
|---|---|
| `normas` | 1 doc por norma (metadatos, `hash_xml`, conteos) |
| `normas_historial` | versión anterior de la norma cada vez que su XML cambia |
| `fragmentos` | 1 doc por artículo (o por parte, si el artículo supera 5.000 caracteres): la unidad del RAG |
| `fragmentos_historial` | versión anterior de cada fragmento cambiado o retirado |

Nunca se borra nada: un artículo que desaparece de la versión vigente queda `vigente: false` y `retirado_en`, y vuelve a `estado_embedding: "pendiente"` para que `embed_sync.py` actualice el payload en Qdrant (el retriever filtra `vigente=true`).

IDs de fragmento: `<idNorma>-art-<n>` (`-art-t-<n>` para transitorios, sufijo `-p<i>` para partes). La `ñ` se escribe `nn` (los artículos `183 N` y `183 Ñ` coexisten).

## Embeddings (`embed_sync.py`)

Proveedor por defecto: Voyage `voyage-4-large`, 1024 dimensiones, colección Qdrant `normativa_cl` (coseno). Los
fragmentos se embeben con `input_type: "document"`; las consultas del retriever deben usar `embed_consulta()`
(`input_type: "query"`, mismo modelo y dimensiones). Cada fragmento guarda el modelo en `embedding_modelo`.

Límites de la cuenta en `VOYAGE_TPM` y `VOYAGE_RPM` (por defecto 10.000 tokens y 3 peticiones por minuto, los de una
cuenta sin medio de pago): las peticiones se arman bajo el 80 % del límite de tokens y la siguiente espera lo que
exija el más estricto de los dos; ante un 429 se espera `Retry-After` y se reintenta. Con esos límites, unos 200
fragmentos tardan ~10 minutos. `--proveedor gemini|openai` queda como alternativa (no mezclar modelos en una misma
colección).

## Cambios respecto del código original (hallados con XML reales)

1. El parser no bajaba a los `EstructurasFuncionales` anidados: devolvía 0 artículos del Código Penal y 3 de la Ley 20.393.
2. "Doble articulado": la Ley 20.393 trae la ley completa dentro del "Artículo Primero". Ahora se recorre siempre el interior de los artículos.
3. `derogado` y `transitorio` se leen por artículo (antes solo a nivel de norma). Un artículo derogado queda `vigente: false`.
4. Encabezados marcados como artículo ("ARTICULOS TRANSITORIOS" en el Código del Trabajo) se tratan como sección.
5. Texto con incisos conservados (`\n\n`) y líneas des-envueltas. Los artículos largos se parten por inciso y, si hace falta, por oración.
6. Colisiones de ID (ñ, numeración repetida) resueltas de forma determinística.
7. Detección de cambios por firma (texto contextualizado + vigencia + categorías) con carga masiva, historial por fragmento y retiro de artículos que desaparecen.
8. Descarga con reintentos. Sin User-Agent identificable la BCN responde 401, y tras ~12 descargas seguidas responde 429 (se respeta `Retry-After`, o se espera 60 s × intento).

Conteos con XML reales (2026-10-02): Código Penal 677 artículos / 856 fragmentos (48 no vigentes); Código del Trabajo 737 / 745; Ley 20.393 40 / 40; Ley 21.643 8 / 12.
