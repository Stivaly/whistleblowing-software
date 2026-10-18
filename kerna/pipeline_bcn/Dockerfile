# Imagen del pipeline normativo (extractor BCN + sincronizador de embeddings).
# Corre como Azure Container Apps Job; las credenciales llegan como variables de
# entorno desde Key Vault, nunca dentro de la imagen.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 TZ=America/Santiago
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY extraer_bcn.py embed_sync.py crear_bd.py atlas_acceso.py leyes.json ./
COPY run.sh ./
RUN chmod +x run.sh && useradd --create-home kerna && chown -R kerna /app
USER kerna

ENTRYPOINT ["./run.sh"]
CMD ["diario"]
