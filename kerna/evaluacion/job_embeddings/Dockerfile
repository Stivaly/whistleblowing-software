# Job de evaluación de embeddings abiertos (corre en Azure, CPU; nunca en el servidor local).
# Ollama (Qwen3-Embedding, BGE-M3, EmbeddingGemma) + sentence-transformers (multilingual-e5-large-instruct).
# Los modelos se descargan al ejecutar el job, no al construir la imagen. Los datos (datos/) salen de
# preparar_datos.sh y van dentro de la imagen porque el ACR es privado.
ARG OLLAMA_VERSION=0.12.6
FROM ollama/ollama:${OLLAMA_VERSION} AS ollama

FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    OLLAMA_MODELS=/tmp/ollama HF_HOME=/tmp/hf OLLAMA_HOST=127.0.0.1:11434 \
    OLLAMA_NUM_PARALLEL=1 OLLAMA_MAX_LOADED_MODELS=1 OLLAMA_KEEP_ALIVE=30m
RUN apt-get update && apt-get install -y --no-install-recommends libstdc++6 ca-certificates \
    && rm -rf /var/lib/apt/lists/*
COPY --from=ollama /usr/bin/ollama /usr/bin/ollama
COPY --from=ollama /usr/lib/ollama /usr/lib/ollama
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu \
    && pip install --no-cache-dir sentence-transformers==3.3.1

WORKDIR /app
COPY evaluar.py ./
COPY datos/ ./datos/
RUN useradd --create-home kerna && chown -R kerna /app
USER kerna
ENTRYPOINT ["python", "evaluar.py"]
