# Regla de eliminación (proyecto whistleblowing-software)
- NUNCA eliminar archivos, carpetas, ramas, contenedores, volúmenes ni datos.
- Si algo "debe eliminarse": moverlo con `mv` a `.papelera/AAAA-MM-DD/<ruta-original>` (conservando la ruta) y continuar.
- Registrar cada movimiento en `pendientes/eliminaciones-pendientes.md` (fecha, ruta original, ruta en papelera, motivo) para que la usuaria decida.
- Trabajo autónomo: no detenerse a preguntar salvo bloqueo real; documentar decisiones en `pendientes/`.

# Mapa del proyecto
- Veridy = fork de GlobaLeaks 5.0.85 (esquema BD 68). Backend Python/Twisted en `backend/globaleaks/`, cliente Angular 19 en `client/app/src/`, despliegue en `docker/`.
- Kerna (IA de sugerencia normativa) en `kerna/` e infraestructura Azure en `infra/`. `fable upgrades/` es solo referencia y puede estar desactualizado.
- Integración Kerna → Veridy: leer `pendientes/mapa-integracion-kerna-veridy.md` antes de tocar código. Análisis detallados en `pendientes/analisis-veridy/`.
- Ignorar al buscar: `documentation/` (docs upstream), `client/dist`, `client/.angular`, `client/node_modules`, `venv/`, `docker/globaleaks.tar`.
- Cifrado: el texto de una denuncia solo existe en claro en memoria (envío y lectura con sesión del receptor). Todo dato derivado de una denuncia se guarda cifrado con `InternalTip.crypto_tip_pub_key`. Nunca desactivar `encryption` ni usar escrow para procesar.

# Base de Veridy en Azure (se apaga sola)
- El PostgreSQL de Veridy en Azure se apaga tras 60 min sin peticiones a Veridy y se enciende cuando alguien vuelve a entrar. Lo hace el cron `infra/scripts/veridy_bd.sh cron` (cada minuto); registro en `~/.local/state/veridy-bd/veridy-bd.log`.
- Si aparece un error de conexión a la base (`OperationalError`, `could not connect`, `Connection refused`, `timeout`, `server closed the connection`) en Veridy, en sus logs o en un comando:
  1. `infra/scripts/veridy_bd.sh estado`. Si dice `Stopped`, `infra/scripts/veridy_bd.sh encender` (tarda 1-5 min) y reintentar.
  2. Verificar que el cron esté activo: `crontab -l | grep veridy_bd`. Si no está, `infra/scripts/veridy_bd.sh instalar-cron`.
  3. Si dice `Ready` y aun así no conecta: comparar la IP pública (`curl -4 -s https://ifconfig.me`) con `postgres_ips_permitidas` en `infra/terraform/terraform.tfvars`; si cambió, actualizarla y `terraform plan/apply`.
  4. Si `az` responde `AADSTS50076` (MFA), pedir a la usuaria que repita `az login`: el cron tampoco podrá encender ni apagar hasta entonces.
