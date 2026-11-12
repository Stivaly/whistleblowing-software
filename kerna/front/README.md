# Front web de Kerna AI

FastAPI con plantillas Jinja y gráficos SVG en línea; sin build de Node ni CDN (fuentes Unbounded y JetBrains Mono auto-alojadas, licencia OFL en `app/estaticos/fuentes/LICENCIAS.txt`).

- URL: https://app-kerna-dev-front-g6mzy.azurewebsites.net
- `/` portada pública: qué hace Kerna, flujo, anonimizador y cifrado, leyes cubiertas (21.643, 19.628/21.719, 20.393) y aviso de que es una sugerencia. Símbolo guilloché animado en línea, quieto con `prefers-reduced-motion`.
- `/panel` (protegido): casos por día, distribución por modo, artículos por ley, valoraciones, latencia P50/P95 y tokens; rango 7 o 30 días. `/api/metricas?dias=7|30` entrega lo mismo en JSON. Solo cifras agregadas, nunca texto ni identificadores.
- `/salud` responde `ok` sin autenticación.

## Datos
`app/consultas.py` ejecuta con `azure-monitor-query` y `DefaultAzureCredential` las consultas KQL de `kerna/docs/observabilidad/consultas/` (las del Workbook `solicitudes_por_modo` y `tokens_por_solicitud`, más `front_*.kql`), cambiando `ago(7d)` por el rango. Caché de 60 s. El despliegue copia esas consultas a `app/kql/`.
Artículos por ley salen del evento `articulo_sugerido` (solo el nombre público de la norma), emitido por `orquestador.py`; las valoraciones, de los eventos `feedback` (arriba = útil, abajo = no útil) y `clasificacion_auditor` rechazada (= ninguno aplica).

## Infraestructura (`infra/terraform/front.tf`)
App Service Plan Linux F1 (gratis) y Linux Web App Python 3.12 en `rg-kerna-dev`, HTTPS only, TLS 1.2, FTPS desactivado, identidad administrada de sistema con `Log Analytics Reader` sobre `log-kerna-dev` y `Key Vault Secrets User` sobre el Key Vault de Kerna. Inicio: `gunicorn -k uvicorn.workers.UvicornWorker app.principal:app`. F1 no admite always-on: la primera visita tras inactividad tarda unos segundos.

## Protección
La cuenta de estudiante no puede crear registros de aplicación de Entra (`allowedToCreateApps = false`), por eso `/panel` y `/api/*` usan una clave compartida (`FRONT_AUTH=clave`):
- La clave es el secreto `front-clave-panel` del Key Vault; la app la recibe como referencia de Key Vault en `FRONT_CLAVE`. Nunca pasa por Terraform ni por el repo.
- `/panel` redirige a `/acceso`; el formulario entrega una cookie firmada (HttpOnly, Secure, SameSite=Strict, 8 h). Para `/api/*` se usa la cabecera `X-Clave`. Comparación en tiempo constante y límite de 5 fallos por IP cada 5 minutos.
- Leer la clave: `az keyvault secret show --vault-name <kv> --name front-clave-panel --query value -o tsv`. Rotar: `az keyvault secret set` con otro valor y reiniciar la app.

### Pasar a Entra ID
1. Con una cuenta que pueda crear registros de aplicación: crear el registro (web, redirect `https://<app>/.auth/login/aad/callback`, tokens de ID activados).
2. Activar autenticación integrada: `az webapp auth microsoft update` (o `azurerm_linux_web_app.auth_settings_v2` con `active_directory_v2`) con `require_authentication`, acción `Return401` y exclusión de rutas para `/`, `/estaticos/*` y `/salud`, de modo que solo `/panel` y `/api/*` exijan sesión.
3. Cambiar `FRONT_AUTH` a `entra`: la app pasa a exigir la cabecera `X-MS-CLIENT-PRINCIPAL-ID` que inyecta Easy Auth.

## Despliegue y pruebas
- `kerna/front/desplegar.sh`: empaqueta el front con las consultas y lo sube con `az webapp deploy` (zip; el build de `requirements.txt` lo hace App Service).
- Pruebas: `cd kerna && python3 -m pytest pruebas/unitarias/test_front.py` (Log Analytics simulado).

## Costo
Plan F1 sin costo. Las consultas a Log Analytics no tienen cargo para este volumen.

## Pendiente
- Reconstruir y desplegar la imagen del núcleo para que emita `articulo_sugerido` (hasta entonces "artículos por ley" sale vacío).
- Activar Entra ID cuando exista un registro de aplicación (ver arriba).
