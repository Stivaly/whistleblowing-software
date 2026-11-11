# Contexto de build: la carpeta kerna/  (docker build -f nucleo/Dockerfile kerna)
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONPATH=/app/comun:/app/nucleo
WORKDIR /app
COPY nucleo/requirements.txt /app/nucleo/requirements.txt
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu \
    && pip install --no-cache-dir -r /app/nucleo/requirements.txt
# Reranker abierto BAAI/bge-reranker-v2-m3 (solo se descarga; se ejecuta en el contenedor al usarlo).
ENV HF_HOME=/opt/hf KERNA_BGE_RUTA=/opt/bge-reranker-v2-m3
RUN python -c "from huggingface_hub import snapshot_download as d; d('BAAI/bge-reranker-v2-m3', local_dir='/opt/bge-reranker-v2-m3', allow_patterns=['*.json','*.safetensors','sentencepiece*','tokenizer*'])" \
    && chmod -R a+rX /opt
COPY comun/ /app/comun/
COPY nucleo/kerna_nucleo/ /app/nucleo/kerna_nucleo/
RUN useradd --system --uid 10001 --no-create-home kerna
USER 10001
EXPOSE 8080
CMD ["python", "-m", "kerna_nucleo"]
