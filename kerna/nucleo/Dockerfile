# Contexto de build: la carpeta kerna/  (docker build -f nucleo/Dockerfile kerna)
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONPATH=/app/comun:/app/nucleo
WORKDIR /app
COPY nucleo/requirements.txt /app/nucleo/requirements.txt
RUN pip install --no-cache-dir -r /app/nucleo/requirements.txt
COPY comun/ /app/comun/
COPY nucleo/kerna_nucleo/ /app/nucleo/kerna_nucleo/
RUN useradd --system --uid 10001 --no-create-home kerna
USER 10001
EXPOSE 8080
CMD ["python", "-m", "kerna_nucleo"]
