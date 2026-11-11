# Núcleo de Kerna AI

API (FastAPI) que recibe una denuncia ya anonimizada, recupera del corpus normativo los artículos candidatos (Voyage + Qdrant, con respaldo en el servicio local), genera con Gemini las sugerencias con cita y las valida contra los fragmentos recuperados. El contrato (rutas, cadena, enrutador, variables, telemetría) está en `kerna/docs/contratos.md`.

## Módulos (`kerna_nucleo/`)

`api.py` (rutas, `crear_app(config, almacen, proveedores, reloj)`), `auth.py` (OAuth client credentials, JWT HS256 de 10 min), `orquestador.py` (cadena por caso), `enrutador.py` (niveles, reintentos 1-2-4 s, corte 30 s, cortocircuito, plazo de 240 s), `clasificador` (dentro del orquestador, con `prompts.py`), `retriever.py`, `validador.py`, `almacen.py` (`AlmacenMemoria`, `AlmacenTablas`), `proveedores/` (Gemini, Voyage, Qdrant, servicio local), `servidor.py`.

Decisiones de comportamiento: el cortocircuito se lleva por modelo (cada nivel de la cadena); una solicitud `pendiente` más antigua que 240 s pasa a `revision_manual` / `tiempo_agotado` al consultarla; el texto del caso solo vive en memoria durante la cadena.

## Ejecución local (sin Azure)

```
cd kerna
export PYTHONPATH=comun:nucleo
export KERNA_ALMACEN=memoria KERNA_JWT_SECRETO=$(openssl rand -hex 32)
export KERNA_CLIENTES='{"conector":{"secreto_sha256":"<sha256 del secreto>","cliente":"conector"}}'
export GEMINI_API_KEY=... VOYAGE_API_KEY=... QDRANT_URL=... QDRANT_API_KEY=...
python3 -m kerna_nucleo        # escucha en :8080
```

Imagen: `docker build -f nucleo/Dockerfile kerna` (el contexto es la carpeta `kerna/`).

## Pruebas

```
cd kerna
python3 -m pytest pruebas/unitarias -q -k nucleo      # sin red
python3 -m pytest pruebas/integracion/test_nucleo_real.py -m integracion   # servicios reales, lee el entorno
```

## Variables

`KERNA_CLIENTES`, `KERNA_JWT_SECRETO`, `GEMINI_API_KEY`, `VOYAGE_API_KEY`, `QDRANT_URL`, `QDRANT_API_KEY`, `KERNA_COLECCION` (normativa_cl), `KERNA_EMBEDDING` (voyage-4-large), `KERNA_DIMS` (1024), `KERNA_LOCAL_URL`, `KERNA_LOCAL_TOKEN`, `KERNA_TOP_K` (8), `KERNA_CONCURRENCIA` (2: cadenas simultáneas; el resto espera turno), `KERNA_UMBRAL_SIMILITUD`, `KERNA_CADENA` (JSON de niveles `{modo, proveedor, modelo, esquema, sistema}`), `KERNA_ALMACEN` (memoria | tablas), `KERNA_TABLAS_URL` o `KERNA_TABLAS_CONEXION`, `APPLICATIONINSIGHTS_CONNECTION_STRING`, `PORT` (8080).

## Estado

Gemini: `gemini-3.5-flash-lite` y `gemma-4-31b-it` aceptan esquema JSON e instrucción de sistema por REST; si un modelo responde 400, el cliente repite sin esquema y sin instrucción de sistema y el enrutador extrae y valida el JSON. Voyage, Qdrant y el servicio local solo se prueban simulados en las pruebas unitarias.
