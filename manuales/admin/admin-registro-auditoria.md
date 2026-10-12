# Manual de Usuario - Registro de Auditoría (Panel Administrador)

Monitoreo de actividad del sistema para seguridad y cumplimiento.

## Pestañas

### 1. Registro de Auditoría

Historial de acciones en el sistema.

| Columna | Descripción |
|---------|-------------|
| Fecha | Momento de la acción |
| Tipo | Categoría de evento |
| Usuario | Quién realizó la acción |
| Objeto | Elemento afectado |

**Exportar**: Descargar registro en archivo
**Logs adicionales** (solo tenant raíz):
- globaleaks.log: Log del sistema
- access.log: Log de accesos

### 2. Usuarios

Información de cuentas del sistema.

| Columna | Descripción |
|---------|-------------|
| ID | Identificador único |
| Username | Nombre de usuario |
| Rol | Tipo de cuenta |
| Nombre | Nombre completo |
| 2FA | Estado de autenticación de dos factores |
| Fecha creación | Cuándo se creó la cuenta |
| Último acceso | Última vez que ingresó |

### 3. Reportes

Resumen de todas las denuncias.

| Columna | Descripción |
|---------|-------------|
| # | Número progresivo |
| Fecha | Fecha de creación |
| Última actualización | Último cambio |
| Expiración | Cuándo expira |
| Canal | Categoría de denuncia |
| Estado | Estado actual |
| Tor | Si se envió por Tor |
| Comentarios/Archivos | Cantidad adjunta |
| Receptores | Cantidad de destinatarios |
| Último acceso denunciante | Última visita del informante |

### 4. Tareas Programadas

Monitoreo de trabajos automáticos del sistema.

Muestra las últimas 10 ejecuciones de cada tarea con:
- Nombre del trabajo
- Duración (segundos)
- Hora y fecha de ejecución

**Exportar**: Disponible en todas las pestañas
