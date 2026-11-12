# Regla de eliminación (proyecto whistleblowing-software)
- NUNCA eliminar archivos, carpetas, ramas, contenedores, volúmenes ni datos.
- Si algo "debe eliminarse": moverlo con `mv` a `.papelera/AAAA-MM-DD/<ruta-original>` (conservando la ruta) y continuar.
- Excepción: limpieza de Docker del host. Claude SÍ puede eliminar imágenes que no estén desplegadas ni en uso, contenedores de prueba detenidos y la caché de build (`infra/limpiar_docker.sh` o `docker rm`/`rmi`/`image prune`/`builder prune`). Nunca volúmenes ni contenedores en ejecución.
- Registrar cada movimiento en `pendientes/eliminaciones-pendientes.md` (fecha, ruta original, ruta en papelera, motivo) para que la usuaria decida.
- Trabajo autónomo: no detenerse a preguntar salvo bloqueo real; documentar decisiones en `pendientes/`.

# MVP de Kerna (Fable)
- Plan, reglas, estado y el informe ES2 en notas: `~/documentos/kerna-vault/00-INICIO.md` (fuera del repo; nunca copiarlo dentro).
- Fable, mientras ejecuta ese plan, tiene los permisos de `kerna-vault/reglas.md`: encender y apagar Veridy, Terraform apply, push y subagentes. La integración sigue el conector del informe; el diseño del mapa de integración (tablas nuevas, migración 69) queda reemplazado, aunque sus hechos sobre el cifrado siguen valiendo.

# Mapa del proyecto
- Veridy = fork de GlobaLeaks 5.0.85 (esquema BD 68). Backend Python/Twisted en `backend/globaleaks/`, cliente Angular 19 en `client/app/src/`, despliegue en `docker/`.
- Kerna (IA de sugerencia normativa) en `kerna/` e infraestructura Azure en `infra/`. `fable upgrades/` es solo referencia y puede estar desactualizado.
- Integración Kerna → Veridy: leer `pendientes/mapa-integracion-kerna-veridy.md` antes de tocar código. Análisis detallados en `pendientes/analisis-veridy/`.
- Ignorar al buscar: `documentation/` (docs upstream), `client/dist`, `client/.angular`, `client/node_modules`, `venv/`, `docker/globaleaks.tar`.
- Cifrado: el texto de una denuncia solo existe en claro en memoria (envío y lectura con sesión del receptor). Todo dato derivado de una denuncia se guarda cifrado con `InternalTip.crypto_tip_pub_key`. Nunca desactivar `encryption` ni usar escrow para procesar.

# Veridy en Azure (encendido manual, apagado automático)
- Veridy corre en Azure Container Instances con su PostgreSQL, ambos en `rg-veridy-dev` (Terraform en `infra/veridy/terraform`, separado del de Kerna). Se controla con `infra/veridy/veridy.sh encender | apagar | estado | mantener 3d | logs`.
- Encender lo decide la usuaria (excepción: Fable mientras ejecuta el plan del MVP, ver `kerna-vault/reglas.md`). El vigía del grupo (`infra/veridy/contenedor/vigia.py`) apaga Veridy y PostgreSQL tras 60 min sin uso.
- Si aparece un error de conexión a Veridy o a su base (`OperationalError`, `could not connect`, `Connection refused`, `timeout`): `infra/veridy/veridy.sh estado`. Si está apagado, decírselo a la usuaria y darle el comando `infra/veridy/veridy.sh encender` (Fable, en el MVP, lo enciende él mismo).
- Cambios de Terraform (Veridy o Kerna): dejar el cambio en los `.tf`/`tfvars` y ejecutarlo Claude mismo con `infra/aplicar.sh veridy|kerna` (init + plan + apply; lee de Key Vault lo que haga falta). Primero `echo n | infra/aplicar.sh <x>` para revisar el plan; si solo cambia lo esperado, `infra/aplicar.sh <x> -y`. Nunca pasarle a la usuaria comandos terraform para que los corra; si el plan destruye o reemplaza recursos, consultarle antes.
- Si `az` responde `AADSTS50076` (MFA), pedir a la usuaria que repita `az login`.
