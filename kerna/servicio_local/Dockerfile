# Contexto de build: la carpeta kerna/  (docker build -f servicio_local/Dockerfile kerna)
# El modelo multilingual-e5-large-instruct se descarga al iniciar el contenedor (HF_HOME), no al construir.
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONPATH=/app/comun:/app/servicio_local \
    HF_HOME=/tmp/hf TOKENIZERS_PARALLELISM=false OMP_NUM_THREADS=2
WORKDIR /app
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu
COPY servicio_local/requirements.txt /app/servicio_local/requirements.txt
RUN pip install --no-cache-dir -r /app/servicio_local/requirements.txt
COPY comun/ /app/comun/
COPY servicio_local/kerna_servicio_local/ /app/servicio_local/kerna_servicio_local/
RUN useradd --system --uid 10001 --create-home kerna
USER 10001
EXPOSE 8080
CMD ["python", "-m", "kerna_servicio_local"]
