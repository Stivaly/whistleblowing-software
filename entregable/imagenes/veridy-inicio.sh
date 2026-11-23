#!/bin/sh
# Primera vez (volumen vacío): copia los datos iniciales. Después arranca Veridy normalmente.
set -e
if [ ! -e /var/globaleaks/globaleaks.db ] && [ -s /opt/semilla-veridy.tar.gz ]; then
  tar -xzf /opt/semilla-veridy.tar.gz -C /var/globaleaks
fi
exec /usr/bin/python3 /usr/bin/globaleaks --working-path=/var/globaleaks/ -n
