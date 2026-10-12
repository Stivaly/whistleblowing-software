# Manual de Usuario - Sitios (Panel Administrador)

Gestión multi-tenant: permite administrar múltiples plataformas desde una instalación.

## Pestañas

### 1. Sitios

**Agregar Sitio:**
- **Nombre**: Identificador del nuevo sitio
- **Modo**:
  - *DEFAULT*: Instalación estándar
  - *WHISTLEBLOWINGPA*: Modo especial para administración pública

**Lista de Sitios:**
Muestra todos los sitios/tenants con opciones de gestión.

### 2. Opciones

**Configuración General:**
- **Usar primer sitio solo para administración**: El sitio principal no recibe denuncias, solo gestiona otros sitios
- **Modo**: DEFAULT, DEMO o WHISTLEBLOWINGPA
- **Dominio raíz**: Dominio base para sitios secundarios (ej: sitios usan subdominio.dominio.com)
- **Cuestionario predeterminado**: Formulario inicial para nuevos sitios

**Registro de Usuarios:**
- **Permitir registro**: Usuarios pueden crear sus propios sitios
- **Términos de servicio #1 y #2**: Condiciones que deben aceptar al registrarse
  - Título, texto y etiqueta del checkbox para cada uno
