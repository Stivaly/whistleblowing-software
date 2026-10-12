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
