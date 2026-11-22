# Demo del panel — pendientes

## Demo «Denuncias»: conexión con el núcleo (pendiente de aplicar)

El front es un cliente más del núcleo (OAuth client credentials, como el conector de Veridy) con cuenta propia de demo. Lo hace `kerna/front/app/demo_denuncias.py`; los 10 casos y sus respuestas esperadas están en `kerna/front/app/demo_denuncias_casos.py`.

Cambios de Terraform ya escritos (no aplicados; `echo n | infra/aplicar.sh kerna` para revisar el plan y luego `-y`):
- `infra/terraform/secretos.tf`: `random_password.cliente_demo`; la cuenta `demo-panel-<ambiente>` se suma al secreto `kerna-clientes` (cliente `demo-panel`, solo el sha256 de la clave); secretos de Key Vault `demo-panel-client-id` y `demo-panel-client-secret`.
- `infra/terraform/front.tf`: app settings `KERNA_NUCLEO_URL` (fqdn del núcleo, solo si `crear_nucleo`), `DEMO_CLIENT_ID` y `DEMO_CLIENT_SECRET` como referencias de Key Vault (el front ya tiene `Key Vault Secrets User`).
- Se espera que el plan solo cambie: el secreto `kerna-clientes` (nueva versión), 2 secretos nuevos, 1 `random_password` y los app settings del front. No debería destruir nada.
- Después del apply: el núcleo (Container App) toma la nueva versión de `kerna-clientes` solo al crear una revisión nueva: reiniciar la revisión (`az containerapp revision restart`) o redesplegar con `infra/scripts/subir_imagen_nucleo.sh`. Luego desplegar el front con `kerna/front/desplegar.sh --ref HEAD`.
- Por qué en `KERNA_CLIENTES` y no en la tabla `clientes`: así la cuenta de la demo no aparece en «Clientes» ni en «Negocio» (habría contado como cliente con tarifa).
- Sin esos app settings el front no falla: la demo muestra la respuesta esperada guardada con el aviso «La demo no está conectada al núcleo».

Efectos a tener en cuenta: cada denuncia de la demo gasta modelos de pago (la demo limita a 8 envíos por 10 minutos y 60 por día) y cuenta en la telemetría del núcleo (Resumen) y en la tabla `solicitud` bajo `demo-panel`. El núcleo tiene mínimo 0 réplicas: el primer envío tras un rato puede tardar en despertar (el cliente espera hasta 70 s). El texto no se guarda ni se registra en el front.

Verificación hecha: `kerna/operaciones/medir_demo_denuncias.sh` levanta el código del núcleo en 127.0.0.1 con la configuración del tfvars y las APIs reales y envía los 10 casos con el mismo cliente HTTP del front. Resultado en `kerna/evaluacion/registro-pruebas.md` y `kerna/evaluacion/registro/demo_denuncias_20261122_*.json`. No se probó contra el núcleo desplegado porque la cuenta de demo aún no existe allí.
