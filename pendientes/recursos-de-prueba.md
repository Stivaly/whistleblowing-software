# Recursos Docker de prueba (2026-10-04)

Creados por Claude, con autorización de la usuaria, para probar Veridy sobre PostgreSQL antes de aplicar nada en
Azure. Están **detenidos, no borrados** (regla del proyecto). La usuaria decide si se eliminan.

| Recurso | Tipo | Para qué |
| --- | --- | --- |
| `veridy-pgtest` | contenedor (postgres:15, puerto 127.0.0.1:55432) | PostgreSQL local con las bases `veridy` (arranque real) y `veridy_test` (tests) |
| `veridy-pgtest-app` | contenedor (veridy-pgtest) | Veridy arrancando contra PostgreSQL; segundo arranque y guardia de versión |
| `veridy-pgtest-guard` | contenedor | Guardia: volumen con `globaleaks.db` + PostgreSQL → no arranca |
| `veridy-pgtest-trial*` (7) | contenedores | Corridas de tests (SQLite, PostgreSQL y línea base) |
| `veridy-pgtest-check`, `-ddl`, `-drv` | contenedores | Versiones de librerías y DDL compilado |
| `veridy-pgtest-net` | red Docker | Red entre los contenedores de prueba |
| `veridy-pgtest:latest` | imagen (3,34 GB; capa propia ~2 MB) | `docker_globaleaks` + `python3-psycopg2` |

Las contraseñas de la base de prueba están en el scratchpad de la sesión (`pgtest.env`), no en el repo.

Para eliminarlo todo (cuando la usuaria lo decida):

```bash
docker rm $(docker ps -aq --filter name=veridy-pgtest)
docker network rm veridy-pgtest-net
docker rmi veridy-pgtest:latest
```

## Resultados

- Esquema creado en PostgreSQL por `veridyadmin`: 34 tablas, tenant raíz con id 1, versión 68, `veridy_app` sin
  privilegio CREATE, 0 columnas con longitud.
- Tests sobre PostgreSQL (`GLOBALEAKS_TEST_PG_URI`): 114/114 (receptor, denunciante, analista, auth, custodio,
  asistente, admin tenant/usuario/contexto/auditoría, jobs, ORM).
- Tests sobre SQLite tras los cambios: 195/195 (mismos módulos + todo admin + models).
- `test_migration` (SQLite): 16 fallos **previos**, iguales con el código original (no los causan estos cambios).
- Guardias de arranque verificadas: segundo arranque (68) arranca; versión 67 no arranca; volumen con
  `globaleaks.db` no arranca.

# Recursos de prueba del 2026-10-12 (diagnóstico general)

Creados por Claude para correr todas las pruebas. Se dejan detenidos, no borrados; la usuaria decide.

| Recurso | Tipo | Para qué |
| --- | --- | --- |
| `veridy-test-1012-sqlite`, `-pg`, `-base` | contenedores (veridy-pgtest) | Suite completa del backend: código actual en SQLite y PostgreSQL, y rama `stable` como línea base |
| `veridy-test-1012-repro52`, `-pg-mig`, `-sqlite-mig` | contenedores | Reproducción del fallo de migración y verificación del skip en PostgreSQL |
| `veridy-test-1012-e2e-backend` | contenedor (detenido) | Primer intento de backend para Cypress (escuchaba solo en 127.0.0.1 interno) |
| `veridy-test-1012-e2e` | contenedor | Backend + cliente de pruebas para Cypress, puerto 127.0.0.1:18443 |
| `veridy-test-1012-roles*`, `-check*` | contenedores (postgres:15) | Roles y verificaciones contra el PostgreSQL de Azure (contraseñas por `.pgpass` montado, no en el entorno) |
| `veridy-test-1012-nube`, `-nube2` | contenedores (veridy-pgtest) | Primer y segundo arranque de Veridy contra Azure, puerto 127.0.0.1:28443 |
| `veridy-test-1012-e2e-*`, `-cypress*` | contenedores | Comparación Cypress `stable` vs Veridy |
| `cypress/included:15.4.0` | imagen (4,5 GB) | Cypress con sus dependencias gráficas (el host no las tiene) |
| `kerna-mongo44-test` | contenedor (mongo:4.4, 127.0.0.1:27018) | MongoDB desechable para las pruebas del pipeline (`MONGODB_TEST_URI`) |
| `kerna-mongo-test` | contenedor (mongo:8.0, salió con error) | Intento con MongoDB 8: no corre, la CPU no tiene AVX |
| `mongo:4.4`, `mongo:8.0` | imágenes | La 8.0 no sirve en esta máquina |
| `kerna/pipeline_bcn/.venv-test` | entorno Python (fuera de git) | Primer entorno de pruebas; ya no hace falta (requirements-dev ya no fija pymongo) |

Para eliminarlo (cuando la usuaria lo decida):

```bash
docker rm $(docker ps -aq --filter name=veridy-test-1012) kerna-mongo-test
docker rmi mongo:8.0
```
