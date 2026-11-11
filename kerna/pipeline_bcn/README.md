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
| `meta` | `_id: "corpus"` con `version_corpus` (entero que crece cuando el corpus cambia) |

Nunca se borra nada: un artículo que desaparece de la versión vigente queda `vigente: false` y `retirado_en`, y queda pendiente en cada colección para que `embed_sync.py` actualice el payload en Qdrant (el retriever filtra `vigente=true`).

IDs de fragmento: `<idNorma>-art-<n>` (`-art-t-<n>` para transitorios, sufijo `-p<i>` para partes). La `ñ` se escribe `nn` (los artículos `183 N` y `183 Ñ` coexisten).

## Embeddings (`embed_sync.py`)

Las colecciones activas están en `colecciones.json` (`nombre`, `proveedor`, `modelo`, `dims`, `activa`); hoy solo
`normativa_cl` (Voyage `voyage-4-large`, 1024 dims, coseno). Para sumar una colección local se agrega otra entrada
(`{"nombre":"normativa_cl_local","proveedor":"local","modelo":"<modelo>","dims":1024}`).

```bash
python3 embed_sync.py                                   # normativa_cl
python3 embed_sync.py --todas                           # todas las colecciones activas
python3 embed_sync.py --coleccion X --proveedor azure-openai --modelo text-embedding-3-large --dims 1024
python3 embed_sync.py --paridad [--coleccion X | --todas]   # Mongo vs colección; sale con 1 si difieren
```

Proveedores: `voyage` (`voyage-4-large`, `voyage-4-lite` con `output_dimension`; `voyage-law-2` no lo acepta: 1024
fijas), `azure-openai` (`AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_KEY`, despliegue con el nombre del modelo o
`AZURE_OPENAI_DEPLOYMENT`, `dimensions`), `local` (`POST {KERNA_LOCAL_URL}/embed` con `X-Token-Interno`),
`gemini` y `openai`. Los documentos se embeben con `input_type: "document"`; las consultas, con el mismo modelo y
dimensiones, vía `crear_embedder(...)(textos, "query")`.

**Estado por colección.** Cada fragmento guarda `embeddings.<coleccion> = {modelo, hash_texto, firma, en}`. Está
pendiente para una colección si no tiene entrada o su modelo, `hash_texto` o `firma` (texto contextualizado, vigencia,
categorías) difieren. Los `no_aplica` (no sustantivos) no se indexan. `estado_embedding`/`embedding_modelo` se
mantienen para `normativa_cl`: un fragmento con `estado_embedding: "ok"` y el mismo modelo cuenta como sincronizado
aunque no tenga el mapa. Un artículo retirado cambia su `firma`, así que cada colección recibe el punto con
`vigente=false`.

**Punto de metadatos.** Cada colección tiene el punto `00000000-0000-0000-0000-000000000000` con payload
`{"tipo":"meta","vigente":false,"version_corpus":int,"modelo":str,"actualizado_en":iso}`, que cada corrida deja
al día: se escribe si falta o si su versión no es la de Mongo. `version_corpus` es el contador `meta/_id:"corpus"` de Mongo, que `extraer_bcn.py`
incrementa una vez por corrida si hubo fragmentos nuevos, cambiados o retirados. Un corpus con fragmentos y sin
contador empieza en 1.

**Regla de disparo (`run.sh`: diario, semanal, vigencia-21719).** `extraer_bcn.py --resultado ARCHIVO` escribe
`{ok, errores, nuevos, cambiados, retirados, cambios, version_corpus}`. Luego `embed_sync.py --todas --si-cambios
ARCHIVO`: si la extracción falló no vectoriza; si `cambios > 0` o alguna colección tiene fragmentos pendientes
(consulta a Mongo, sin proveedores) sincroniza todas las colecciones activas; si no, imprime "sin cambios" y no llama
a ningún proveedor.

**Límites de Voyage.** `VOYAGE_TPM` y `VOYAGE_RPM` (por defecto 10.000 tokens y 3 peticiones por minuto): las
peticiones se arman bajo el 80 % del límite de tokens, la siguiente espera lo que exija el más estricto de los dos
(medido con `usage.total_tokens`) y un 429 se reintenta esperando `Retry-After` o un tiempo creciente. Unos 200
fragmentos tardan ~10 minutos.

## Acceso a Atlas desde los jobs (`atlas_acceso.py`)

Con `ATLAS_ACCESO_TEMPORAL=1`, `run.sh` autoriza la IP de salida del contenedor en la lista de acceso del proyecto
de Atlas antes de empezar (`abrir`: entrada con `deleteAfterDate`, `ATLAS_ACCESO_HORAS` = 2 por defecto) y la quita
al terminar, también si el pipeline falla (`cerrar`). Si la IP ya tiene una entrada permanente no la toca. Requiere
`ATLAS_PUBLIC_KEY`, `ATLAS_PRIVATE_KEY` y `ATLAS_PROJECT_ID`. Prueba manual con una IP de documentación:
`python3 atlas_acceso.py abrir --ip 192.0.2.10 && python3 atlas_acceso.py cerrar`.

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
