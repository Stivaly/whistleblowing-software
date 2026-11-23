@echo off
rem Abre el instalador con ventana. No hace falta abrir nada mas.
cd /d "%~dp0"
start "" powershell -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "%~dp0instalar.ps1"
