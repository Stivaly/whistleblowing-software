#!/usr/bin/env bash
# Apaga Veridy y Kerna en este computador. Las denuncias y cuentas se conservan para la próxima vez.
cd "$(dirname "$0")"
DOCKER=docker; docker info >/dev/null 2>&1 || DOCKER="sudo docker"
$DOCKER compose --env-file configuracion.env -f docker-compose.yml stop && echo "Apagado. Para volver a usarlo: ./instalar.sh"
