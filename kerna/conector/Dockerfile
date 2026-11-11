# Contexto de build: la carpeta kerna/  (docker build -f conector/Dockerfile kerna/)
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/app/comun:/app/conector

WORKDIR /app
COPY conector/requirements.txt /app/conector/requirements.txt
RUN pip install --no-cache-dir -r /app/conector/requirements.txt

COPY comun/kerna_comun /app/comun/kerna_comun
COPY conector/kerna_conector /app/conector/kerna_conector
COPY conector/entrada.py /app/conector/entrada.py

RUN useradd --system --uid 10001 --no-create-home conector && mkdir /datos && chown conector /datos
USER conector
WORKDIR /datos

# Local: python -m kerna_conector. En Azure el grupo ejecuta entrada.py (lee los secretos de Key Vault).
CMD ["python", "-m", "kerna_conector"]
