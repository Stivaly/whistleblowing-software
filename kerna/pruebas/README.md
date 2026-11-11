# Pruebas automáticas de Kerna

Suite que corre con un comando y deja resultados en archivos legibles por máquina. Contrato general en
`kerna/docs/contratos.md` (sección Pruebas).

## Capas

| Capa | Carpeta | Qué hace | Comando |
| --- | --- | --- | --- |
| unitarias | `unitarias/` | Sin red, proveedores simulados, en paralelo (pytest-xdist). Incluye las pruebas previas de `kerna/pipeline_bcn/test_*.py` y `kerna/evaluacion/test_*.py` (en serie; usan MongoDB local en 127.0.0.1:27018, el script inicia `kerna-mongo44-test` si existe) | `scripts/probar.sh unitarias` |
| integracion | `integracion/` | Servicios reales; se omiten con motivo si falta una variable. Carga `kerna/pipeline_bcn/.env` sin imprimirlo | `scripts/probar.sh integracion` |
| e2e | `e2e/` | Playwright (Chromium) contra Veridy, dentro de `mcr.microsoft.com/playwright/python:v1.64.0-noble`. Trazas, capturas y video solo al fallar, en `artefactos-e2e/` del reporte | `scripts/probar.sh e2e` |
| carga | `carga/` | locust sin interfaz contra la API del núcleo; evalúa P95 (PR-30) y ausencia de fallas (PR-31) | `scripts/probar.sh carga` |
| veridy | (backend) | Suite existente del backend de Veridy (`twisted.trial`) en SQLite y PostgreSQL desechable, dentro de la imagen `veridy-pgtest` | `scripts/probar.sh veridy` |

`scripts/probar.sh todo` corre todas. El script usa siempre `/usr/bin/python3`.

## Resultados

`reportes/pruebas/<AAAAMMDD-HHMM>-<commit>/` (ignorado por git) contiene `junit-<capa>.xml`, `marcas-<capa>.json`
(prueba -> marcas -> resultado), `salida-<capa>.log` (salida completa), `resumen.json` y, en e2e, los artefactos.
`resumen.json` trae por capa totales, pasadas, fallidas, omitidas, duración y la lista de fallidas con sus IDs del
informe; además commit, fecha UTC y sha256 de `datos/`. Se copia a `kerna/evaluacion/registro/pruebas-<corrida>.json`
y se regenera `kerna/evaluacion/matriz-pruebas.md` (PR del informe -> pruebas -> último resultado).
En la terminal solo salen una línea por capa y las fallidas; el código de salida es distinto de 0 si algo falla.

## Variables

| Variable | Uso |
| --- | --- |
| `VERIDY_URL` | URL de Veridy para e2e (por defecto, la que informa `infra/veridy/veridy.sh estado`) |
| `VERIDY_USUARIO`, `VERIDY_PASSWORD` | Credenciales para pruebas e2e con sesión |
| `PROBAR_ENCENDER_VERIDY=1` | Si Veridy no está Running, lo enciende con `veridy.sh encender` y espera `/api/health` (tope 3 min). Sin esto, e2e falla con un mensaje claro |
| `KERNA_API_URL`, `KERNA_CLIENT_ID`, `KERNA_CLIENT_SECRET`, `KERNA_ID_EMPRESA` | API del núcleo para carga e integración |
| `CARGA_USUARIOS` (3), `CARGA_TASA` (1), `CARGA_DURACION` (60s) | Parámetros de locust |
| `KERNA_P95_MAX_MS` (15000), `KERNA_SONDEO_MAX_S` (60), `KERNA_SONDEO_PAUSA_S` (2) | Criterio y sondeo de la carga |
| `QDRANT_URL`, `QDRANT_API_KEY`, `VOYAGE_API_KEY`, `GEMINI_API_KEY` | Integración |
| `PROBAR_VERIDY_MOTORES` (`sqlite,pg`), `PROBAR_VERIDY_MODULOS` (`globaleaks.tests`), `PROBAR_VERIDY_TOPE` (1800 s) | Capa veridy |
| `KERNA_SEMILLA` (20260101) | Semilla fija de las pruebas |

## Capa veridy

Los 16 fallos de `globaleaks.tests.test_migration` también ocurren en la rama `stable`: `datos/base_veridy.json` los
declara como conocidos y el resumen los cuenta aparte (`conocidas`) sin hacer fallar la capa; si fueran más de 16 sí falla.
Usa los contenedores persistentes `kerna-probar-veridy` y `kerna-probar-pg` (PostgreSQL 15 sin puerto publicado); se
detienen al terminar, nunca se eliminan.

## Agregar una prueba

1. Crear `unitarias/test_<tema>.py` (o la carpeta de la capa que corresponda).
2. Marcar con el ID del informe: `@pytest.mark.pr("PR-25")`, y `rf("RF-..")`, `rnf("..")`, `cu("..")` cuando aplique.
   Se puede marcar el módulo entero con `pytestmark = [pytest.mark.pr("PR-25")]`.
3. Usar datos de `datos/` (`denuncias_sinteticas.json`: texto, `ley_esperada`, `pii_sembrada`, `inyeccion`); nada real.
4. Si el PR es nuevo en el MVP, clasificarlo en `datos/alcance_pr.json`. Ejecutar la capa y revisar
   `kerna/evaluacion/matriz-pruebas.md`.
