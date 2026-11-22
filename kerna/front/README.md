# Front web de Kerna AI

FastAPI con plantillas Jinja y gráficos SVG en línea; sin build de Node ni CDN (fuentes Unbounded y JetBrains Mono auto-alojadas, licencia OFL en `app/estaticos/fuentes/LICENCIAS.txt`).

- URL: https://app-kerna-dev-front-g6mzy.azurewebsites.net
- `/` portada pública: qué hace Kerna, flujo, anonimizador y cifrado, leyes cubiertas (21.643, 19.628/21.719, 20.393) y aviso de que es una sugerencia. Símbolo guilloché animado en línea, quieto con `prefers-reduced-motion`.
- `/panel` (protegido): casos por día, distribución por modo, artículos por ley, valoraciones, latencia P50/P95 y tokens; rango 7 o 30 días. `/api/metricas?dias=7|30` entrega lo mismo en JSON. Solo cifras agregadas, nunca texto ni identificadores.
- `/panel/informe` (protegido): informe de gestión con selector 7/30/90 días o fechas, y descargas `/panel/informe/descargar.{pdf,xlsx,csv}` (mismos parámetros `dias` o `desde`/`hasta`). Ejemplos en `ejemplos/`.
- `/salud` responde `ok` sin autenticación.

## Informe de gestión
Seis secciones, elegidas porque responden lo que un tutor o auditor pregunta, cada una con su fuente y fecha de corte (donde falta un dato dice «sin datos»):
1. Resumen ejecutivo: casos, % con sugerencia, valoración útil, disponibilidad efectiva y modos.
2. Calidad: recall@5 por artículo y por ley frente a la meta de 0,80, anonimizador por tipo, valoraciones de auditores, pruebas automáticas (evaluación sobre el dataset público; no depende del período).
3. Desempeño: latencia P50/P95 frente a PR-30 (15 s) y por etapa. Los reintentos del conector no llegan a Log Analytics: sin datos.
4. Costo y consumo: costo a precios de la API de Anthropic según los tokens por modelo exacto (gpt-5-nano = Haiku 5.5, gpt-5-mini = Sonnet 5.5, otros como Haiku 5.5), por período, por denuncia, desglose por modelo y proyección mensual de 100 y 1.000 denuncias. Precios, fecha y fuente en constantes al inicio de `app/informe.py`.
5. Cobertura normativa: artículos del corpus y artículos sugeridos por ley.
6. Incidentes: fallas de proveedor o modelo y casos en revisión manual por motivo.
Datos: Log Analytics (consultas en `kql/`, rango exacto) y `app/datos/evaluacion.json`, instantánea que `generar_datos_informe.py` crea en cada despliegue desde `kerna/evaluacion/registro/`. Formatos: XLSX (hoja Resumen con logo PNG y una hoja por sección), PDF (reportlab, fuentes Unbounded y JetBrains Mono en TTF embebidas, logo vectorial) y CSV único en formato largo (seccion; metrica; valor; unidad; fuente; fecha_corte, UTF-8 con BOM y `;`), elegido porque un solo archivo se filtra y cruza sin abrir un zip.

## Datos
`app/consultas.py` ejecuta con `azure-monitor-query` y `DefaultAzureCredential` las consultas KQL de `kerna/docs/observabilidad/consultas/` (las del Workbook `solicitudes_por_modo` y `tokens_por_solicitud`, más `front_*.kql`), cambiando `ago(7d)` por el rango. Caché de 60 s. El despliegue copia esas consultas a `app/kql/`.
Artículos por ley salen del evento `articulo_sugerido` (solo el nombre público de la norma), emitido por `orquestador.py`; las valoraciones, de los eventos `feedback` (arriba = útil, abajo = no útil) y `clasificacion_auditor` rechazada (= ninguno aplica).

## Infraestructura (`infra/terraform/front.tf`)
App Service Plan Linux F1 (gratis) y Linux Web App Python 3.12 en `rg-kerna-dev`, HTTPS only, TLS 1.2, FTPS desactivado, identidad administrada de sistema con `Log Analytics Reader` sobre `log-kerna-dev` y `Key Vault Secrets User` sobre el Key Vault de Kerna. Inicio: `gunicorn -k uvicorn.workers.UvicornWorker app.principal:app`. F1 no admite always-on: la primera visita tras inactividad tarda unos segundos.

## Accesos y roles
Cada persona entra en `/acceso` con su usuario y contraseña (`FRONT_AUTH=clave`). `/panel/*` y `/cuenta` exigen una sesión; `/api/*` también acepta la clave compartida por cabecera `X-Clave`.

**Roles y permisos** (tabla única en `app/permisos.py`, aplicada en el servidor a toda ruta GET y POST por el middleware `control_acceso`; el menú solo la refleja):

| Sección | Dirección | Operación de IA | Comercial | Evaluación | Invitado |
| --- | --- | --- | --- | --- | --- |
| Resumen (`/panel`) | editar | editar | editar | ver | no |
| Informe (`/panel/informe`, descargas) | editar | editar | editar | ver | no |
| Negocio (`/panel/negocio`) | editar | no | editar | ver | no |
| Administrar clientes (`/panel/clientes`) | editar | no | editar | ver | no |
| Ajustes y reintentos (`/panel/ajustes`, `/panel/reintentar`) | editar | editar | no | ver | no |
| Cuentas (`/panel/cuentas`, con historial) | editar | no | no | ver | no |
| Demo (`/panel/demo`) | editar | editar | editar | editar | editar |

Evaluación ve todo y no modifica nada: sus formularios salen deshabilitados y cualquier POST responde 403 con la pantalla de Kerna (la Demo no guarda nada del sistema, por eso puede usarla). Sin permiso, un GET responde 403 con la misma pantalla. Una ruta nueva debe agregarse a `permisos.RUTAS`: sin sección no se atiende (404) y `test_front_cuentas.py` lo comprueba. «Mi cuenta» (`/cuenta`) y `/salir` son de cualquier persona con sesión.

**Almacenamiento:** tablas `cuentas` y `cuentaseventos` del Storage del núcleo (URL en `CUENTAS_TABLA_URL`, o `NEGOCIO_TABLA_URL` si falta), con la identidad administrada de la app (rol Storage Table Data Contributor, `infra/terraform/evaluacion.tf`).
- `cuentas`: `usuario` (RowKey), `nombre`, `correo`, `rol`, `hash`, `activa`, `debe_cambiar_clave`, `creada`, `actualizada`, `ultimo_acceso`, `intentos_fallidos`, `bloqueada_hasta`, `sesion` (versión de sesión).
- `cuentaseventos`: `fecha`, `actor`, `accion` (creada, editada, rol_cambiado, clave_restablecida, clave_cambiada, eliminada, desactivada, acceso_ok, acceso_fallido, bloqueada), `cuenta`, `detalle`. Nunca contiene contraseñas, claves temporales ni huellas. Los intentos con un usuario que no existe no dejan evento.

**Contraseñas:** hash argon2id con sal (`argon2-cffi`, parámetros por defecto: 3 pasadas, 64 MiB). Política: de 12 a 128 caracteres y distinta del usuario y del nombre. Nunca se guardan ni se registran en claro.

**Sesión:** cookie `kerna_panel` firmada con HMAC (HttpOnly, Secure, SameSite=Strict, 8 h) con usuario, rol y versión de sesión. En cada petición se comprueba contra la cuenta (existe, activa, misma versión y rol; se recuerda 10 s). Cambiar la clave, restablecerla, cambiar el rol, desactivar o eliminar la cuenta sube la versión y cierra sus sesiones; quien cambia su propia clave sigue con una cookie nueva. Si la tabla no responde, el panel responde 503 y no deja pasar a nadie.

**Intentos:** 5 fallos seguidos bloquean la cuenta 15 minutos (se guarda en la tabla) y la IP tiene un límite aparte de 5 fallos cada 5 minutos. El mensaje es siempre el mismo, exista o no el usuario. Una cuenta con `debe_cambiar_clave` solo puede abrir `/cuenta/clave` hasta elegir su contraseña.

**Cuentas (solo Dirección edita):** crear, editar (nombre, correo, rol, activar o desactivar), restablecer contraseña y eliminar (se escribe el usuario para confirmar). No se puede eliminar, desactivar ni restablecer la propia cuenta, ni dejar el sistema sin una cuenta Dirección activa. Crear y restablecer generan una contraseña temporal aleatoria y la envían por correo (`app/correo.py`, tipos `cuenta_creada`, `clave_restablecida`, `cuenta_eliminada`, `rol_cambiado`, `clave_cambiada`). Si el correo no sale, la contraseña se muestra una vez a quien la creó y el evento lo registra sin ella.

**Cuenta `admin`:** si `cuentas` está vacía al arrancar (o en el primer acceso), se crea `admin`, rol Dirección, con la contraseña actual `FRONT_CLAVE` (hash argon2) y sin obligación de cambiarla. Esa es la primera cuenta: entrar como `admin`, abrir Cuentas y crear las demás (conviene cambiar la contraseña de `admin` en «Mi cuenta»).

**Clave compartida (`X-Clave`):** secreto `front-clave-panel` del Key Vault, entregado como referencia en `FRONT_CLAVE`. Solo vale en `/api/*` (`/api/metricas`, `/api/proveedores`, `/api/negocio`) y da lectura de Resumen y Negocio; no abre `/panel` ni modifica nada. También firma las cookies de sesión: rotarla cierra todas las sesiones. Leerla: `az keyvault secret show --vault-name <kv> --name front-clave-panel --query value -o tsv`.

### Pasar a Entra ID
1. Con una cuenta que pueda crear registros de aplicación: crear el registro (web, redirect `https://<app>/.auth/login/aad/callback`, tokens de ID activados).
2. Activar autenticación integrada: `az webapp auth microsoft update` (o `azurerm_linux_web_app.auth_settings_v2` con `active_directory_v2`) con `require_authentication`, acción `Return401` y exclusión de rutas para `/`, `/estaticos/*` y `/salud`, de modo que solo `/panel` y `/api/*` exijan sesión.
3. Cambiar `FRONT_AUTH` a `entra`: la app pasa a exigir la cabecera `X-MS-CLIENT-PRINCIPAL-ID` que inyecta Easy Auth; cada persona entra con rol Dirección y no usa cuentas propias.

## Despliegue y pruebas
- `kerna/front/desplegar.sh`: empaqueta el front con las consultas y lo sube con `az webapp deploy` (zip; el build de `requirements.txt` lo hace App Service).
- Pruebas: `cd kerna && python3 -m pytest pruebas/unitarias/test_front.py` (Log Analytics simulado).

## Costo
Plan F1 sin costo. Las consultas a Log Analytics no tienen cargo para este volumen.

## Pendiente
- Reconstruir y desplegar la imagen del núcleo para que emita `articulo_sugerido` (hasta entonces "artículos por ley" sale vacío).
- Activar Entra ID cuando exista un registro de aplicación (ver arriba).

## Negocio (clientes, uso y margen)

`/panel/negocio` y `/api/negocio` leen las tablas `clientes` y `usodiario` del núcleo (Azure Table Storage, rol Table Data Reader de la identidad de la app; URL en `NEGOCIO_TABLA_URL`). Los costos de IA se calculan con los tokens por modelo y los precios de Anthropic (nano = Claude Haiku 5.5, 0,10/0,50 USD por millón; mini = Claude Sonnet 5.5, 2/10).

`sembrar_negocio.py` (idempotente) llena las tablas: Veridy (`veridy-dev`) se calcula desde las tablas reales de solicitudes, valoraciones y clasificaciones; los otros cuatro clientes son datos de demostración (90 días de uso con estacionalidad de días hábiles, uno en riesgo por falta de uso y uno sobre su plan) y las tarifas son de referencia, no contractuales. Re-ejecutarlo actualiza el uso de Veridy.

## Administrar clientes (`/panel/clientes`)

Lista, agrega y quita clientes de Kerna. Todo vive en las tablas del núcleo: `clientes` (un perfil por cliente), `solicitud` y `usodiario`
(PartitionKey = cliente). Lo hace `app/clientes.py`; las reglas compartidas (identificador, planes, clave) están en
`kerna/comun/kerna_comun/clientes_esquema.py`. Cada acción exige sesión del panel, mismo origen y token CSRF.

- **Agregar:** nombre, identificador (3 a 40 letras minúsculas, números o guiones), rubro, plan y casos al mes. Crea las credenciales del cliente en el núcleo (client credentials): la clave se muestra una sola vez y solo se guarda su sha256 (`secreto_sha256`).
- **Dar de baja (la decide Kerna):** el cliente queda en `baja` y pierde el acceso al núcleo en menos de 20 s; Kerna conserva toda su información y se puede **reactivar**.
- **Borrar por ley (el cliente lo pide expresamente):** se pide escribir su identificador. Su fila sale de `clientes` y todo lo que lo identifica pasa a ser un uuid sustituto: la clave de partición y los campos `cliente` e `id_empresa` de `solicitud`, la de `usodiario`, y su nombre o identificador dentro del texto libre (`observacion`) de `sugerenciaarticulo`, `valoracion` y `clasificacion`. Los datos de ejecución (denuncias procesadas, uso, costos, resultados) se conservan bajo el uuid, sin forma de saber de quién eran. Queda una fila sin nombre como constancia (fecha, filas conservadas y la referencia que se escriba). No se puede deshacer; si se corta, repetirlo reutiliza el mismo uuid. La telemetría de Azure (Log Analytics) no se reescribe: conserva el identificador hasta que vence su retención.
- **Cuenta de la plataforma:** `veridy-dev` (la que usa el conector de Veridy) no se puede dar de baja ni borrar desde el panel (`PROTEGIDOS`).
- **Permisos:** la identidad del panel tiene *Storage Table Data Contributor* sobre esas seis tablas (`front_clientes_admin` en `infra/terraform/evaluacion.tf`).

## Calidad del panel (set desarrollo)

La banda de calidad (Resumen e Informe) muestra siempre el set `desarrollo` (`parametros.particion` en la tabla `evaluaciones`) con la configuración vigente, la desplegada en Veridy. La marca es la fila `vigente`/`desarrollo` de la misma tabla (campo `corrida` = `fecha` de la medición). Sin marca, toma la última medición de desarrollo sobre la colección `normativa_cl`.

Actualizarla solo cuando una configuración nueva mejora desarrollo y se despliega:
`CONFIRMAR=si kerna/operaciones/tablas.sh escribir evaluaciones vigente desarrollo "corrida=<fecha de la medición>" commit=<commit> "nota=<configuración>"`

«Revisión manual» y «sin sugerencia» cuentan casos distintos que existen hoy en Veridy (fila `conector` de `reintentosmanuales`); las consultas históricas cuentan un caso por su último estado.

Los ajustes de la vista Ajustes (valores, rangos y validación) viven en `kerna/comun/kerna_comun/ajustes_esquema.py`; los consumen el panel, el conector y el núcleo, y `kerna/front/desplegar.sh` empaqueta ese archivo junto a `app/`.
