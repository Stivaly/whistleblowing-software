# Contexto de build: la carpeta kerna/  (infra/scripts/subir_imagen_kerna.sh pasarela)
FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
COPY pasarela/pasarela.py /app/pasarela.py
RUN useradd --system --uid 10001 --no-create-home pasarela
USER pasarela
EXPOSE 8080
CMD ["python", "/app/pasarela.py"]
