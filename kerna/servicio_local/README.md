# Servicio local de Kerna AI

Servicio FastAPI de contingencia: vectoriza con `multilingual-e5-large-instruct` (1024 dimensiones, CPU, dentro del
contenedor) y busca en un índice en memoria, de modo que la recuperación funciona aunque Qdrant Cloud y Voyage estén
caídos. Contrato en `kerna/docs/contratos.md` (sección "Servicio local").

## API

| Ruta | Descripción |
|---|---|
| `POST /embed {"textos":[...],"tipo":"document"\|"query"}` | Hasta 64 textos. Las consultas llevan el prefijo `Instruct: <tarea>\nQuery: ` (el mismo de `evaluacion/job_embeddings/evaluar.py`); los documentos, ninguno. Vectores unitarios |
| `POST /buscar {"texto","k"}` | Vectoriza como consulta y calcula el coseno por fuerza bruta (numpy) solo sobre fragmentos vigentes. Devuelve `fragmentos` (payload + `puntaje`), `modelo`, `coleccion`, `version_corpus` |
| `POST /recargar` | Vuelve a leer la colección de Qdrant (o la copia del blob) y actualiza la copia. No está en el contrato; se usa tras sincronizar la colección |
| `GET /salud` | Sin token. `200` cuando el modelo está cargado, `503 {"estado":"cargando"}` mientras tanto. Incluye `fragmentos`, `version_corpus` y `origen_indice` (`qdrant` \| `blob` \| vacío) |

Todas salvo `/salud` exigen `X-Token-Interno`, comparado con `hmac.compare_digest`. `/embed` funciona aunque no haya
índice (así se puebla la colección la primera vez); `/buscar` responde `503` si no hay índice.

## Índice y arranque

1. Al iniciar, el servicio lee toda la colección `KERNA_LOCAL_COLECCION` (`normativa_cl_local`) de Qdrant (vectores,
   payload y punto meta `00000000-0000-0000-0000-000000000000`) y guarda una copia `normativa_cl_local.npz` en el
   contenedor `indice-local` de la cuenta de almacenamiento del núcleo (identidad administrada).
2. Si Qdrant no responde o la colección no existe, carga esa copia.
3. El modelo se descarga de Hugging Face al iniciar el contenedor (`HF_HOME=/tmp/hf`), no al construir la imagen.
   Con escala a cero, el arranque en frío tarda varios minutos; `/salud` responde `503` hasta que termina y el
   ingress retiene la primera solicitud (el cliente del núcleo espera hasta 60 s).

Variables: `KERNA_LOCAL_TOKEN`, `QDRANT_URL`, `QDRANT_API_KEY`, `KERNA_LOCAL_COLECCION`, `KERNA_BLOB_URL`,
`KERNA_BLOB_CONTENEDOR`, `AZURE_CLIENT_ID`, `APPLICATIONINSIGHTS_CONNECTION_STRING` (opcional). La telemetría usa la
lista de atributos permitidos de `kerna_comun.telemetria`; nunca registra textos de consultas.

## Construcción y despliegue

```
infra/scripts/subir_imagen_kerna.sh servicio_local --tag v1          # construye (contexto kerna/) y sube
terraform apply -var crear_servicio_local=true                        # crea la Container App (infra/terraform/servicio_local.tf)
infra/scripts/subir_imagen_kerna.sh servicio_local --desplegar        # versiones siguientes
```

La Container App `ca-kerna-dev-servicio-local` escala de 0 a 1 réplica, con 2 vCPU y 4 GiB. La URL sale en la salida
`servicio_local_url`.

## Activar la colección local

Con el servicio desplegado (`KERNA_LOCAL_URL` = `servicio_local_url`, `KERNA_LOCAL_TOKEN` = secreto `kerna-local-token`):

```
# 1) agregar a kerna/pipeline_bcn/colecciones.json
{"nombre": "normativa_cl_local", "proveedor": "local", "modelo": "multilingual-e5-large-instruct", "dims": 1024, "activa": true}

# 2) vectorizar el corpus (el pipeline lo hace con --todas)
python3 kerna/pipeline_bcn/embed_sync.py --coleccion normativa_cl_local --proveedor local \
  --modelo multilingual-e5-large-instruct --dims 1024

# 3) que el servicio cargue la colección y deje la copia en el blob
curl -X POST -H "X-Token-Interno: $KERNA_LOCAL_TOKEN" "$KERNA_LOCAL_URL/recargar"
```

Y en el núcleo, `KERNA_LOCAL_URL` (variable `nucleo_entorno`). El paso 2 funciona sin la entrada del paso 1, con los
argumentos de la línea de comandos.

## Pruebas

```
cd kerna && python3 -m pytest pruebas/unitarias -q -k servicio_local
```

Usan un embedder falso inyectado y una simulación de Qdrant y del blob: ningún modelo se ejecuta fuera de Azure.
