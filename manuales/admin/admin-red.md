# Manual de Usuario - Red (Panel Administrador)

## Pestañas

### 1. HTTPS

Configura el acceso seguro a la plataforma.

- **Hostname**: Dominio de la plataforma (ej: denuncias.miempresa.com)
- **Estado HTTPS**: Muestra si el certificado SSL está activo
- **Configuración de certificados**: Subir certificado SSL o generar automáticamente

### 2. Tor

Red de anonimato para máxima privacidad.

- **Tor Onion Service**: Dirección .onion generada automáticamente
- **Regenerar**: Crea nueva dirección (la anterior dejará de funcionar)
- **Anonimizar conexiones salientes**: El servidor usa Tor para conexiones externas
- **Acceso sin Tor**: Permite usar la plataforma desde internet normal

**Roles habilitados sin Tor:**
Configura qué usuarios pueden acceder sin usar Tor:
- Admin, Analyst, Custodian, Recipient, Whistleblower

### 3. Control de Acceso

Restringe el acceso por dirección IP.

**Por cada rol puede:**
- Habilitar filtro de IP
- Especificar IPs permitidas (separadas por coma)

**Formato**: IP individual, rango CIDR o IPv6
Ejemplo: `212.35.212.87,192.0.2.0/24,2001:db8::/32`

### 4. Redirecciones URL

Crea redirecciones de rutas dentro de la plataforma.

- **Desde**: Ruta origen
- **Hacia**: Ruta destino
- Útil para enlaces cortos o migraciones
