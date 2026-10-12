-- Roles de la base "veridy" en Azure Database for PostgreSQL.
--
-- Se corre UNA vez, conectado como el administrador del servidor (veridyadmin),
-- antes del primer arranque de Veridy. Ver infra/terraform/README.md, paso 12.
--
--   veridyadmin  dueño del esquema: crea y actualiza tablas (solo en arranques de
--                instalación o actualización, con GLOBALEAKS_DB_ADMIN_URI)
--   veridy_app   rol con el que corre Veridy: lee y escribe datos, sin DDL
--
-- Compensa el autorizador de SQLite que Veridy usa en modo archivo
-- (backend/globaleaks/orm.py): en PostgreSQL el límite lo pone el rol.
--
-- Uso: psql ... -v app_password="$VERIDY_APP_PASSWORD" -f veridy_roles.sql

\set ON_ERROR_STOP on

SELECT format('CREATE ROLE veridy_app LOGIN PASSWORD %L', :'app_password')
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'veridy_app')
\gexec

ALTER ROLE veridy_app PASSWORD :'app_password';
-- Sin NOSUPERUSER: en Azure el administrador no es superusuario y no puede nombrar ese
-- atributo; un rol creado así nunca es superusuario (la comprobación final lo muestra).
ALTER ROLE veridy_app NOCREATEDB NOCREATEROLE NOINHERIT;
ALTER ROLE veridy_app CONNECTION LIMIT 40;
ALTER ROLE veridy_app SET search_path = public;
ALTER ROLE veridy_app SET statement_timeout = '60s';
ALTER ROLE veridy_app SET lock_timeout = '10s';
ALTER ROLE veridy_app SET idle_in_transaction_session_timeout = '60s';

-- Nadie fuera del dueño crea objetos en el esquema público.
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
REVOKE ALL ON DATABASE veridy FROM PUBLIC;
GRANT CONNECT ON DATABASE veridy TO veridy_app;
GRANT USAGE ON SCHEMA public TO veridy_app;

-- Tablas y secuencias que ya existan...
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO veridy_app;
GRANT USAGE, SELECT, UPDATE ON ALL SEQUENCES IN SCHEMA public TO veridy_app;

-- ...y las que cree después el administrador (primer arranque y actualizaciones).
ALTER DEFAULT PRIVILEGES IN SCHEMA public
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO veridy_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
  GRANT USAGE, SELECT, UPDATE ON SEQUENCES TO veridy_app;

-- Comprobación
SELECT rolname, rolsuper, rolcreatedb, rolcreaterole, rolcanlogin
FROM pg_roles WHERE rolname IN (current_user, 'veridy_app');
