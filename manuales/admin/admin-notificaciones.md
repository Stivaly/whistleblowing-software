# Manual de Usuario - Notificaciones (Panel Administrador)

## Pestañas

### 1. Configuración SMTP

Configura el servidor de correo para enviar notificaciones.

**Servidor de Correo:**
- **Dirección SMTP**: Email desde el cual se envían notificaciones
- **Servidor SMTP**: Dirección del servidor de correo (ej: smtp.gmail.com)
- **Puerto SMTP**: Puerto del servidor (común: 587 para TLS, 465 para SSL)
- **Seguridad**: Protocolo de conexión
  - *PLAIN*: Sin cifrado (no recomendado)
  - *SMTPS*: Cifrado SSL
  - *SMTP/TLS*: Cifrado TLS (recomendado)
- **Autenticación**: Si requiere usuario/contraseña

**Notificaciones por Rol:**
Habilita/deshabilita emails para cada tipo de usuario:
- Admin, Analyst, Custodian, Recipient

**Opciones:**
- **Horas antes de alerta de expiración**: Anticipo para avisar que un reporte va a expirar (0=deshabilitado)

**Acciones:**
- **Probar configuración**: Envía email de prueba a su dirección
- **Resetear SMTP**: Restaura configuración de correo por defecto
- **Resetear plantillas**: Restaura textos de emails por defecto

### 2. Plantillas de Notificación

Personaliza el contenido de cada tipo de email enviado por el sistema.

- Seleccione la plantilla a editar
- Modifique el texto (soporta variables del sistema)
- Guarde los cambios
