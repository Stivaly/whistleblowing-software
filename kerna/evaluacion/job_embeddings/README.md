# Job de Azure para los modelos de embeddings abiertos

Corre `Qwen3-Embedding 8B`, `BGE-M3`, `EmbeddingGemma 300M` y `multilingual-e5-large-instruct` dentro de Azure
(`job-kerna-dev-eval-embeddings` en `cae-kerna-dev`, perfil Consumption, 4 vCPU, 8 GiB, sin GPU), nunca en el servidor
local. Tiempo máximo 9000 s, 1 reintento.

| Archivo | Función |
|---|---|
| `preparar_datos.sh` / `.py` | Exporta de Mongo los fragmentos vigentes sustantivos (acceso temporal a Atlas con cierre garantizado) y copia el dataset a `datos/` |
| `Dockerfile` | Ollama (copiado de la imagen oficial) + sentence-transformers CPU; los modelos se descargan al ejecutar |
| `evaluar.py` | Por modelo: vectoriza fragmentos y consultas (una por petición, con su tiempo), sube a Qdrant |
| `.gitignore` | `datos/` (texto de leyes y dataset: entran a la imagen, no al repo) |

Cada modelo deja dos colecciones en Qdrant: `normativa_cl_eval_<modelo>` (fragmentos, mismo id y payload que
`embed_sync.py`) y `normativa_cl_eval_<modelo>_consultas` (vector, `ms` y `tokens` de cada consulta, sin textos).
Nombres de modelo: `embeddinggemma-300m`, `bge-m3`, `multilingual-e5-large-instruct`, `qwen3-embedding-8b`
(`qwen3-embedding-4b` si el 8B no cabe: variable `eval_modelos` de Terraform o `MODELOS` del job).
Los vectores de más de 1024 dimensiones (Qwen3) se truncan a 1024 y se normalizan; EmbeddingGemma queda en 768.
Un modelo que falla o excede `TIEMPO_MODELO_S` (3600) se registra y el job sigue; el job termina con error solo si
ninguno se completó. Un modelo con colecciones completas se omite (reintentos baratos; `FORZAR=1` para repetir).
Cada línea de log es un JSON; `resultado_modelo` y `fin` traen el estado, P95 y tokens.

## Comandos (desde la raíz del repo, en este orden)

```bash
# 1. Datos dentro del contexto de build (abre y cierra Atlas solo)
kerna/evaluacion/job_embeddings/preparar_datos.sh

# 2. Azure OpenAI + secretos (sin el job todavía: no hay imagen)
terraform -chdir=infra/terraform plan -out=eval.tfplan && terraform -chdir=infra/terraform apply eval.tfplan

# 3. Construir y subir la imagen (tag v1 la primera vez, el de var.imagen_eval_tag)
infra/scripts/subir_imagen_eval.sh --tag v1

# 4. Crear el job
terraform -chdir=infra/terraform apply -var crear_job_eval=true

# 5. Lanzar SIN --args (reemplazaría el contenedor y perdería variables y secretos)
RG=$(terraform -chdir=infra/terraform output -raw grupo_recursos)
JOB=$(terraform -chdir=infra/terraform output -json job_eval_embeddings | python3 -c 'import json,sys;print(json.load(sys.stdin)[0])')
EJEC=$(az containerapp job start -n "$JOB" -g "$RG" --query name -o tsv)

# 6. Esperar a que la ejecución termine (consulta el estado hasta que deja de ser Running/Processing)
until s=$(az containerapp job execution show -n "$JOB" -g "$RG" --job-execution-name "$EJEC" --query properties.status -o tsv); \
      [ "$s" != Running ] && [ "$s" != Processing ]; do sleep 30; done; echo "estado: $s"

# 7. Logs (pueden tardar 1-2 minutos en aparecer en Log Analytics)
az containerapp job logs show -n "$JOB" -g "$RG" --execution "$EJEC" --container eval-embeddings --format text
```

Consumo real: `az containerapp job execution list -n "$JOB" -g "$RG" -o table`.
Si la imagen cambia: `infra/scripts/subir_imagen_eval.sh --desplegar`.

## Medición (desde `kerna/`, con `set -a; . pipeline_bcn/.env; set +a`)

```bash
PY=pipeline_bcn/.venv/bin/python
# Abiertos: leen los vectores de consulta que dejó el job (no ejecutan el modelo aquí)
for m in embeddinggemma-300m bge-m3 multilingual-e5-large-instruct qwen3-embedding-8b; do
  $PY evaluacion/recall_retriever.py --coleccion normativa_cl_eval_$m --proveedor local --modelo $m \
      --vectores-consulta qdrant:normativa_cl_eval_${m}_consultas
done
# Nube
$PY evaluacion/recall_retriever.py                                             # voyage-4-large (caché)
$PY evaluacion/recall_retriever.py --coleccion normativa_cl --modelo-consulta voyage-4-lite   # asimétrica
# voyage-law-2 y text-embedding-3-large: primero vectorizar su colección (embed_sync, ver abajo), luego
$PY evaluacion/recall_retriever.py --coleccion normativa_cl_eval_voyage-law-2 --proveedor voyage --modelo voyage-law-2
$PY evaluacion/recall_retriever.py --coleccion normativa_cl_eval_text-embedding-3-large --proveedor azure-openai --modelo text-embedding-3-large
$PY evaluacion/comparar_embeddings.py                                          # escribe informe-embeddings.md
```

Colecciones de nube (usan `MONGODB_URI` con acceso temporal a Atlas):

```bash
python3 pipeline_bcn/embed_sync.py --coleccion normativa_cl_eval_voyage-law-2 --proveedor voyage --modelo voyage-law-2 --dims 1024
python3 pipeline_bcn/embed_sync.py --coleccion normativa_cl_eval_text-embedding-3-large --proveedor azure-openai --modelo text-embedding-3-large --dims 1024
```
(`AZURE_OPENAI_ENDPOINT` y `AZURE_OPENAI_KEY` se leen de Key Vault: `azure-openai-endpoint`, `azure-openai-key`.)

## Límites a tener presentes

- Qwen3 no es medible en este job (4 vCPU, 8 GiB, sin GPU): con el 8B Ollama responde 500 al cargarlo y el 4B no
  termina los 145 fragmentos y las 226 consultas en los 60 min de `TIEMPO_MODELO_S` (queda `tiempo_excedido`).
  Medirlos requiere un perfil con GPU o más memoria.
- Disco efímero: el job borra cada modelo de Ollama al terminar con él.
- e5 (sentence-transformers) trunca a 512 tokens, su límite; los artículos largos quedan recortados.
