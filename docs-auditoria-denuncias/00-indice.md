# Mapa técnico del flujo de denuncias (GlobaLeaks) — índice

Documentación generada a partir de una revisión directa del código en
`/home/veridy/whistleblowing-software` (checkout de GlobaLeaks) y de los
archivos de configuración/automatización presentes en `/home/veridy`
(`globaleaks-config`, `globaleaks-external-config`, `etl_incremental.py`, `n8n`).

Todos los nombres de archivo, clase, endpoint y tabla citados son reales y
verificados en el código, no genéricos de la documentación pública de
GlobaLeaks.

1. [01-flujo-denuncia.md](01-flujo-denuncia.md) — Flujo de pantallas del receiver/auditor, de recepción a decisión.
2. [02-autenticacion.md](02-autenticacion.md) — Modelo real de autenticación de sesión.
3. [03-puntos-extension.md](03-puntos-extension.md) — Puntos de extensión existentes **y hallazgos de seguridad activos** que debes remediar.
4. [04-modelo-datos-cifrado.md](04-modelo-datos-cifrado.md) — Dónde vive el contenido de la denuncia y el límite de cifrado.
5. [05-roles-permisos.md](05-roles-permisos.md) — Roles, permisos y separación entre contenido crudo y anotaciones.

## Nota importante antes de leer el punto 3

Durante la revisión se encontró que **ya existe en este entorno** un mecanismo
que lee el contenido crudo de las denuncias directamente de la base de datos
y lo envía a un servicio externo (Supabase), evitando el cifrado y el control
de roles del sistema, con una credencial en texto plano dentro del script.
Esto no es una funcionalidad de GlobaLeaks ni un punto de extensión "seguro":
es un hallazgo de seguridad que se documenta para que lo corrijas, con
recomendaciones concretas en el archivo 03.
