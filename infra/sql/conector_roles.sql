-- Rol y permisos del Conector Veridy sobre su base de estado `kerna_conector`
-- (la base la crea Terraform: infra/veridy/terraform/conector.tf).
--
-- Se corre conectado a la base kerna_conector como el administrador del servidor (veridyadmin):
--   psql "host=... dbname=kerna_conector user=veridyadmin sslmode=require" -v conector_password=... -f conector_roles.sql
-- (ver el comando completo en infra/veridy/README.md). El rol no tiene ningún acceso a la base `veridy`.

\set ON_ERROR_STOP on

SELECT format('CREATE ROLE kerna_conector LOGIN PASSWORD %L', :'conector_password')
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'kerna_conector')
\gexec

ALTER ROLE kerna_conector PASSWORD :'conector_password';
ALTER ROLE kerna_conector NOCREATEDB NOCREATEROLE NOINHERIT;
ALTER ROLE kerna_conector CONNECTION LIMIT 5;
ALTER ROLE kerna_conector SET search_path = public;
ALTER ROLE kerna_conector SET statement_timeout = '60s';
ALTER ROLE kerna_conector SET lock_timeout = '10s';
ALTER ROLE kerna_conector SET idle_in_transaction_session_timeout = '60s';

-- Solo esta base: sin acceso a la de Veridy ni conexión pública a la de estado.
REVOKE ALL ON DATABASE kerna_conector FROM PUBLIC;
REVOKE ALL ON DATABASE veridy FROM kerna_conector;
GRANT CONNECT, TEMPORARY ON DATABASE kerna_conector TO kerna_conector;

-- El conector crea y mantiene sus propias tablas (CREATE TABLE IF NOT EXISTS al iniciar).
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
GRANT USAGE, CREATE ON SCHEMA public TO kerna_conector;

-- Comprobación: el rol no es superusuario y no puede conectarse a veridy.
SELECT rolname, rolsuper, rolcreatedb, rolcreaterole, rolcanlogin,
       has_database_privilege('kerna_conector', 'veridy', 'CONNECT') AS conecta_a_veridy
FROM pg_roles WHERE rolname IN (current_user, 'kerna_conector');
