# Manual de Usuario - Usuarios (Panel Administrador)

## Pestañas

### 1. Usuarios

**Agregar Usuario:**
- **Rol**: Tipo de usuario a crear:
  - *Admin*: Acceso completo a configuración del sistema
  - *Analyst*: Analiza reportes sin acceso a datos sensibles
  - *Custodian*: Custodia claves de cifrado para recuperación
  - *Recipient (Destinatario)*: Recibe y gestiona las denuncias
- **Username**: Nombre para iniciar sesión (no requerido si login simplificado está activo para destinatarios)
- **Nombre**: Nombre completo del usuario
- **Email**: Correo electrónico (obligatorio para notificaciones)
- **Enviar enlace de activación**: Si está marcado, el usuario recibirá un email para configurar su contraseña

**Lista de Usuarios:**
Muestra todos los usuarios con opciones de búsqueda y paginación. Cada usuario muestra:
- Nombre y rol
- Estado (Deshabilitado si aplica)
- Icono de advertencia si no ha realizado primer inicio de sesión

**Editar Usuario:**
- **Imagen**: Foto de perfil
- **Username/Nombre/Nombre público**: Datos de identificación
- **Descripción**: Información adicional sobre el usuario
- **Email**: Correo para notificaciones

**Contraseña:**
- *Enviar enlace de activación/reseteo*: Envía email para que el usuario establezca su contraseña
- *Establecer contraseña*: Permite asignar contraseña directamente (requiere mínimo 12 caracteres con mayúsculas, minúsculas, números y símbolos)

**Opciones de cuenta:**
- **Habilitado**: Activa/desactiva el acceso del usuario
- **Forzar cambio de contraseña**: El usuario deberá cambiar su contraseña en el próximo inicio de sesión
- **Deshabilitar 2FA**: Elimina la autenticación de dos factores (útil si el usuario perdió su dispositivo)
- **Idioma**: Idioma de la interfaz para este usuario
- **Notificaciones por email**: Recibir alertas por correo

**PGP (si está habilitado):**
Cifrado adicional para usuarios avanzados. Muestra la huella digital y fecha de expiración de la clave, o permite subir una nueva.

**Opciones específicas por rol:**

*Administradores:*
- **Escrow**: Permite a este admin cambiar contraseñas de otros usuarios (solo si la función escrow está activada globalmente)

*Destinatarios (Receivers):*
- **Selección forzada**: El destinatario recibirá TODAS las denuncias automáticamente, sin importar el canal seleccionado
- **Enmascarar información**: Permite ocultar temporalmente datos sensibles en reportes
- **Redactar permanentemente**: Permite eliminar definitivamente información enmascarada
- **Eliminar reportes**: Permite borrar denuncias
- **Editar fecha de expiración**: Permite extender el tiempo antes de que un reporte expire
- **Otorgar acceso**: Permite dar acceso a reportes a otros usuarios
- **Transferir reportes**: Permite mover reportes a otros usuarios

*Usuarios no-admin:*
- **Acceso administrativo a configuración**: Permite editar ajustes generales aunque no sea administrador

### 2. Opciones de Usuarios

**Política de Privacidad:**
- **Texto**: Contenido de la política de privacidad que los usuarios deben aceptar
- **URL**: Enlace externo a documento completo de política de privacidad

---
*Recuerde guardar cambios con el botón "Guardar" al editar cada usuario.*
