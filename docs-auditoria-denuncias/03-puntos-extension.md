# Puntos de extensión existentes

## ⚠️ Hallazgo de seguridad activo (leer antes que el resto)

Durante la revisión se encontró que **este entorno ya tiene un mecanismo que
lee el contenido crudo de las denuncias saltándose por completo el cifrado y
el control de roles de GlobaLeaks.** No es un punto de extensión soportado
por el producto: es un script custom en tu propio home, y debe tratarse como
incidente a remediar, no como base para nada nuevo.

**`/home/veridy/etl_incremental.py`** (raíz del home, fuera del repo de GlobaLeaks):

- Lee **directamente el archivo SQLite** del backend
  (`/var/lib/docker/volumes/docker_globaleaks/_data/globaleaks.db`) — es decir,
  accede a los datos **a nivel de disco**, sin pasar por la API, sin sesión,
  sin `check_roles`, sin ninguna de las validaciones descritas en
  [02-autenticacion.md](02-autenticacion.md) ni [05-roles-permisos.md](05-roles-permisos.md).
- Sincroniza de forma incremental (estado en `/home/veridy/etl_state.json`,
  timestamp/PK por tabla) hacia una **instancia Postgres externa alojada en
  Supabase** (host omitido en este documento).
- Usa una **contraseña en texto plano hardcodeada en el propio script**
  (`pg_password` en el bloque `__main__`; valor omitido en este documento).
- Las tablas sincronizadas incluyen `internaltip`, `internaltipanswers`,
  `comment`, `receivertip` y `user` — es decir, exporta el contenido de las
  denuncias, las notas/comentarios internos de los receivers y datos de
  cuentas de usuario a un servicio en la nube fuera de tu control operativo.
- No tiene scheduler propio en el repo (no hay cron/systemd timer) — se
  ejecuta manualmente o por algo externo no documentado aquí.

**Por qué esto es grave en este sistema en particular**: GlobaLeaks está
diseñado deliberadamente para que ni siquiera el operador del servidor pueda
leer el contenido de una denuncia sin pasar por el flujo de sesión y clave
del receiver correspondiente (ver el límite de cifrado en
[04-modelo-datos-cifrado.md](04-modelo-datos-cifrado.md)). Este script anula
esa garantía por completo, porque opera a nivel de archivo de base de datos.

**Recomendación inmediata**:
1. Rotar ya la contraseña de Supabase expuesta en el script.
2. Sacar la credencial del código fuente (variable de entorno / secret manager), y confirmar que este script no esté en el `.git` del repo (está fuera de `whistleblowing-software/`, pero revisa si quedó copiado o versionado en algún otro lado).
3. Decidir explícitamente si este ETL debe existir: si el objetivo es analítica/BI, evaluar sincronizar solo campos no sensibles o agregados, no las tablas con contenido de denuncias en crudo.
4. Restringir el acceso al archivo `globaleaks.db` y a la ejecución de este script a lo estrictamente necesario.

Adicionalmente, se encontró **`/home/veridy/n8n-humancompliance-88863ce5aa8a.json`**:
es una **clave privada de cuenta de servicio de Google Cloud** (proyecto
`n8n-humancompliance`, `n8n-sheets@n8n-humancompliance.iam.gserviceaccount.com`)
sin cifrar, suelta en el home. El contenedor n8n en `/home/veridy/n8n` no
tiene ninguna referencia ni red compartida con el stack de GlobaLeaks — no se
confirmó una conexión activa hacia las denuncias, pero el nombre del proyecto
("humancompliance") sugiere que fue pensado para eso. Recomendación: rotar
esa clave si no está en uso confirmado, y si lo está, no dejarla como archivo
plano en el home.

---

## Puntos de extensión propios de GlobaLeaks (código estándar)

### 1. Webhooks
No existen. Búsqueda de `webhook`, `callback_url`, "hook" en
`backend/globaleaks` no arroja resultados — GlobaLeaks stock no tiene
mecanismo de webhooks salientes.

### 2. Cola de mensajes / bus de eventos
No existen. No hay `celery`, `redis`, `rabbitmq`, `pubsub` en el backend.
Los trabajos periódicos son jobs internos de Twisted (`backend/globaleaks/jobs/*.py`),
no un broker externo.

### 3. API REST relacionada a tips (única superficie programática oficial)

Todas requieren sesión de `receiver` autenticada (`check_roles = 'receiver'`),
definidas en `backend/globaleaks/rest/api.py`:

- `GET /api/recipient/rtips` — listado (`TipsCollection`)
- `GET/POST /api/recipient/rtips/<uuid>` — detalle/operaciones (`RTipInstance`)
- `GET/POST /api/recipient/rtips/<uuid>/comments` — comentarios (`RTipCommentCollection`)
- `GET/POST /api/recipient/rtips/<uuid>/iars` — solicitudes de acceso a identidad
- `GET /api/recipient/rtips/<uuid>/export` — exportación (`ExportHandler`)
- `POST /api/recipient/rtips/<uuid>/rfiles` — subida de archivo del receiver
- `/api/recipient/redactions[/<uuid>]` — redacciones

No existe una API pública/anónima de lectura de tips — por diseño, todo pasa
por sesión de receiver. Esto significa que la única forma "soportada" de que
un sistema externo participe del flujo es actuando como un cliente autenticado
de receiver contra esta API — no hay gancho de "pre-revisión" oficial.

### 4 y 5. Ver el hallazgo de seguridad arriba (`etl_incremental.py`, n8n/GCP key) — no son puntos de extensión soportados, son hallazgos a remediar.
