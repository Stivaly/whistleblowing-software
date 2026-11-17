# Ajustes conectados: estado (2026-11-17)

Hecho y desplegado: código (commit 2bd7555b2 y a90ec3509), núcleo `aj-2bd7555b2` en `ca-kerna-dev-nucleo` (sano), front con `desplegar.sh --ref HEAD`. Verificado en producción solo lo del panel (`probar_ajustes.sh --solo-panel`).

Falta (necesita Veridy encendido; `infra/veridy/veridy.sh encender` lo decide la usuaria, el intento de encenderlo fue rechazado):
1. Desplegar el conector: la imagen `kerna-conector:aj-2bd7555b2` ya está subida y `infra/veridy/terraform/terraform.tfvars` ya tiene `conector_tag = "aj-2bd7555b2"` (archivo ignorado por git). Con Veridy y PostgreSQL encendidos: `echo n | infra/aplicar.sh veridy` y, si solo cambia el grupo de contenedores, `infra/aplicar.sh veridy -y`.
2. `kerna/operaciones/crear_equipos.sh` (cuentas de Comité, Auditoría y Fiscalía; sin ellas esos equipos quedan en `equipos_sin_cuenta`).
3. `kerna/operaciones/probar_ajustes.sh` completo (conector y núcleo; para que el núcleo registre `ajustes_aplicados` debe procesar un caso: `kerna/operaciones/cargar_denuncias.sh 1`). Después, una vez, probar compartir con un equipo real (marcar Comité en Ajustes) y mirar `equipos` en la fila `conector`.
Nota: el panel ya guardó en la tabla los valores por defecto (efecto neutro).
