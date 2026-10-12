# Veridy con PostgreSQL en Azure

Veridy puede guardar su base de datos en **Azure Database for PostgreSQL – Flexible Server** en lugar del archivo
SQLite. Adjuntos, archivos y logs siguen en el volumen local del contenedor.

- Sin `GLOBALEAKS_DB_URI`, Veridy funciona exactamente como antes (SQLite en el volumen).
- Con `GLOBALEAKS_DB_URI`, usa PostgreSQL. La base en la nube empieza **vacía**: se vuelve a pasar por el asistente
  inicial. Los datos locales (volumen `docker_globaleaks`) no se tocan.

Requisitos previos: servidor y roles creados según `infra/terraform/README.md`, pasos 11 y 12.

## Cómo se conecta

| Variable | Para qué | Cuándo |
| --- | --- | --- |
| `GLOBALEAKS_DB_URI` | Conexión del rol `veridy_app` (solo lee y escribe datos) | Siempre |
| `PGPASSWORD` | Contraseña de `veridy_app` (libpq la lee; así no va en la URI) | Siempre |
| `GLOBALEAKS_DB_ADMIN_URI` | Conexión de `veridyadmin`, que crea las tablas | Solo en el primer arranque |
| `GLOBALEAKS_DB_URI_FILE` | Alternativa a `GLOBALEAKS_DB_URI`: ruta a un archivo con la URI | Opcional |

- **TLS:** sin `sslmode` en la URI, Veridy usa `sslmode=verify-full` con los certificados raíz del sistema
  (`sslrootcert=system`, libpq 17 de la imagen). El ejemplo lo deja explícito.
- **La URI no va por línea de comandos**, para que no aparezca en la lista de procesos.

## 1. Construir la imagen

El Dockerfile ya instala `python3-psycopg2`. Desde `docker/`:

```bash
docker compose -f docker-compose.yml -f docker-compose.nube.yml build
```

## 2. Preparar las credenciales

```bash
cd docker
cp veridy-db.env.example veridy-db.env && chmod 600 veridy-db.env     # veridy-db.env está en .gitignore

cd ../infra/terraform
KV=$(terraform output -raw key_vault_nombre)
PGHOST=$(terraform output -raw postgres_servidor)
APP=$(az keyvault secret show --vault-name $KV --name veridy-db-app-password   --query value -o tsv)
ADM=$(az keyvault secret show --vault-name $KV --name veridy-db-admin-password --query value -o tsv)
ADM_URL=$(python3 -c 'import sys, urllib.parse; print(urllib.parse.quote(sys.argv[1], safe=""))' "$ADM")

cd ../../docker
sed -i "s|<servidor>.postgres.database.azure.com|$PGHOST|g" veridy-db.env
sed -i "s|^PGPASSWORD=.*|PGPASSWORD=$APP|" veridy-db.env
# Primer arranque: activar la línea del administrador
sed -i "s|^# GLOBALEAKS_DB_ADMIN_URI=postgresql+psycopg2://veridyadmin:<contraseña url-encoded>@|GLOBALEAKS_DB_ADMIN_URI=postgresql+psycopg2://veridyadmin:$ADM_URL@|" veridy-db.env
unset APP ADM ADM_URL
```

## 3. Primer arranque

`docker-compose.nube.yml` usa un volumen propio (`veridy_nube`), separado del local:

```bash
cd docker
docker compose -f docker-compose.yml -f docker-compose.nube.yml up -d
docker logs -f veridy-nube        # esperar "GlobaLeaks is now running"
```

Al arrancar sobre una base vacía, Veridy crea las 34 tablas con `veridyadmin` (bajo un bloqueo, por si arrancan
dos contenedores a la vez) y desde ahí trabaja con `veridy_app`.

## 4. Quitar la credencial de administrador

```bash
sed -i 's|^GLOBALEAKS_DB_ADMIN_URI=|# GLOBALEAKS_DB_ADMIN_URI=|' veridy-db.env
docker compose -f docker-compose.yml -f docker-compose.nube.yml up -d     # recrea el contenedor sin esa variable
```

Abrir Veridy en el navegador y completar el asistente inicial.

## Protecciones en el arranque

| Situación | Qué hace Veridy |
| --- | --- |
| La base está vacía | Crea el esquema e inicializa el inquilino raíz |
| La base es de esta versión (esquema 68) | Arranca normalmente |
| La base es de otra versión de esquema | **No arranca** y lo explica en el log: en PostgreSQL no hay migración automática |
| El volumen contiene un `globaleaks.db` (instalación SQLite) | **No arranca**: la limpieza de arranque borraría los adjuntos de esa instalación, que la base nueva no conoce |
| La base tiene tablas pero no `config` | No arranca (esquema ajeno o a medio crear) |

## Respaldo

Azure guarda respaldos automáticos 7 días (restauración a un punto en el tiempo). Los adjuntos viven en el volumen
`veridy_nube`: un respaldo completo es la base **y** el volumen del mismo momento.

```bash
# Copia lógica manual de la base (cliente de la imagen postgres:15)
docker run --rm -e PGPASSWORD="<contraseña de veridyadmin>" postgres:15 \
  pg_dump "host=$PGHOST dbname=veridy user=veridyadmin sslmode=require" -Fc > veridy-$(date +%F).dump
```

## Limitaciones conocidas

- `gl-admin` (`backend/bin/gl-admin`): `resetpass`, `disable-2fa`, `getvar` y `setvar` usan `sqlite3` directamente y
  **no funcionan** con PostgreSQL. Su `backup` tampoco incluye la base.
- Una actualización de GlobaLeaks que suba `DATABASE_VERSION` exige un procedimiento manual (pg_dump, migración en
  SQLite y recarga), porque el sistema de migraciones solo opera sobre archivos SQLite.
- Pasan a Azure, en claro dentro de la base, los mismos datos que SQLite guarda en claro: metadatos de las
  denuncias, `config` (claves TLS y onion, contraseña SMTP) y `user.two_factor_secret`. El contenido de las
  denuncias sigue cifrado con las claves de cada denuncia.
