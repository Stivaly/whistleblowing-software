#!/usr/bin/env bash
# Instalador de Veridy y Kerna para Linux. Uso: ./instalar.sh  (o doble clic > «Ejecutar en terminal»)
set -uo pipefail
cd "$(dirname "$0")"
VERSION="$(sed -n 's/^VERSION=//p' configuracion.env | tr -d '\r')"
INICIO="http://localhost:8400"
verde() { printf '\033[32m✓ %s\033[0m\n' "$1"; }
paso()  { printf '\n\033[1m► %s\033[0m\n' "$1"; }
falla() { printf '\033[31m✗ %s\033[0m\n' "$1"; read -rp "Presiona Enter para cerrar." _; exit 1; }

DOCKER=docker
paso "Revisar o instalar Docker"
if ! command -v docker >/dev/null; then
  echo "Instalando Docker (pedirá la contraseña de este computador)."
  command -v curl >/dev/null || sudo apt-get install -y curl >/dev/null 2>&1 || sudo dnf install -y curl >/dev/null 2>&1
  curl -fsSL https://get.docker.com | sudo sh >/dev/null || falla "No se pudo instalar Docker. Revisa la conexión a internet y vuelve a ejecutar ./instalar.sh"
  sudo systemctl enable --now docker >/dev/null 2>&1 || true
fi
if ! docker info >/dev/null 2>&1; then
  if sudo -n true 2>/dev/null || [ -t 0 ]; then DOCKER="sudo docker"; fi
fi
verde "Docker instalado"

paso "Encender Docker"
if ! $DOCKER info >/dev/null 2>&1; then
  (systemctl --user start docker-desktop || sudo systemctl start docker) >/dev/null 2>&1 || true
  for _ in $(seq 1 36); do $DOCKER info >/dev/null 2>&1 && break; sleep 5; done
fi
$DOCKER info >/dev/null 2>&1 || falla "Docker no responde. Enciéndelo (Docker Desktop, o: sudo systemctl start docker) y vuelve a ejecutar ./instalar.sh"
$DOCKER compose version >/dev/null 2>&1 || falla "Falta «docker compose». Instala el paquete docker-compose-plugin y vuelve a ejecutar ./instalar.sh"
verde "Docker encendido"

paso "Copiar los programas (la primera vez tarda unos minutos)"
if ! $DOCKER image inspect "veridy-local:$VERSION" "kerna-conector-local:$VERSION" "kerna-panel-local:$VERSION" >/dev/null 2>&1; then
  $DOCKER load -i imagenes.tar.gz || falla "No se pudieron copiar los programas."
fi
verde "Programas copiados"

paso "Poner en marcha Veridy y Kerna"
if ! salida="$($DOCKER compose --env-file configuracion.env -f docker-compose.yml up -d 2>&1)"; then
  echo "$salida"
  echo "$salida" | grep -qiE "already allocated|address already in use" && falla "Otro programa usa los puertos 8400, 8401 o 8402. Ciérralo y vuelve a ejecutar ./instalar.sh"
  falla "No se pudo poner en marcha."
fi
verde "En marcha"

paso "Esperar a que todo responda (hasta 3 minutos)"
ok=0
for _ in $(seq 1 60); do
  curl -fs -o /dev/null http://localhost:8401/api/health && curl -fs -o /dev/null http://localhost:8402/salud && { ok=1; break; }
  sleep 3
done
[ $ok = 1 ] && verde "Listo. Veridy y Kerna están funcionando" || echo "Todavía no responde: la página de inicio muestra qué falta y se actualiza sola."

cat <<FIN

  Página de inicio (botones a cada parte y cuentas de prueba):  $INICIO
  Hacer una denuncia en Veridy:  http://localhost:8401/#/submission
  Panel de Kerna:                http://localhost:8402/acceso
  Para apagar todo:              ./archivos/detener.sh

FIN
