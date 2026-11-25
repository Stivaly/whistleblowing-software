#!/bin/sh
# Arranque local: clave de la base de Azure en un .pgpass, archivos de Veridy (logo) si faltan, y Veridy.
set -e
umask 077
printf '%s:5432:veridy:veridy_app:%s\n' "$VERIDY_PG_FQDN" "$VERIDY_DB_CLAVE" > /tmp/pgpass
umask 022
mkdir -p /var/globaleaks/files /var/globaleaks/attachments /var/globaleaks/log /var/globaleaks/tmp
cp -n /opt/veridy-archivos/* /var/globaleaks/files/ 2>/dev/null || true
export GLOBALEAKS_DB_URI="postgresql+psycopg2://veridy_app@${VERIDY_PG_FQDN}:5432/veridy?sslmode=verify-full&sslrootcert=system"
exec /usr/bin/python3 /usr/bin/globaleaks --working-path=/var/globaleaks/ -n
