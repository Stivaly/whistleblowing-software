@echo off
rem Apaga Veridy y Kerna. Las denuncias y cuentas se conservan.
cd /d "%~dp0"
echo Apagando Veridy y Kerna...
docker compose --env-file configuracion.env -f docker-compose.yml stop
echo.
echo Listo. Para volver a usarlo, abre Instalar.
pause
