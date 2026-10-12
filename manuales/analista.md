# Manual de Usuario - Analista

## Navegación Principal

El panel del analista tiene las siguientes secciones:
- **Inicio**: Panel principal con información de cuenta
- **Estadísticas**: Métricas y gráficos de reportes

---

## 1. Panel de Estadísticas

### Contador Principal
En la parte superior se muestra el **total de reportes** recibidos en la plataforma.

### Gráficos Disponibles

El sistema genera automáticamente 4 gráficos de pastel (pie charts) con métricas clave:

#### 1. Denunciantes Recurrentes (Returning whistleblowers)
Muestra el porcentaje de denunciantes que han vuelto a acceder a sus reportes.

| Segmento | Descripción |
|----------|-------------|
| Sí | Denunciantes que volvieron a consultar su reporte |
| No | Denunciantes que no han regresado |

**Utilidad**: Indica el nivel de seguimiento que los denunciantes dan a sus casos.

#### 2. Anonimato (Anonymity)
Distribución de reportes según el nivel de identificación del denunciante.

| Segmento | Descripción |
|----------|-------------|
| Anónimo | Nunca proporcionaron identidad |
| Suscrito | Proporcionaron identidad desde el inicio |
| Suscrito después | Inicialmente anónimos, luego se identificaron |

**Utilidad**: Permite evaluar la confianza de los denunciantes en la plataforma.

#### 3. Tor
Porcentaje de reportes enviados usando la red Tor vs. conexión regular.

| Segmento | Descripción |
|----------|-------------|
| Sí | Enviados a través de Tor Browser |
| No | Enviados por conexión web normal |

**Utilidad**: Indica cuántos denunciantes priorizan el anonimato de red.

#### 4. Móvil (Mobile)
Distribución de reportes según el dispositivo utilizado.

| Segmento | Descripción |
|----------|-------------|
| Sí | Enviados desde dispositivo móvil |
| No | Enviados desde computadora de escritorio |

**Utilidad**: Ayuda a entender cómo acceden los usuarios a la plataforma.

---

## 2. Interpretación de Métricas

### Porcentajes
Cada segmento del gráfico muestra:
- Etiqueta descriptiva
- Porcentaje calculado automáticamente

### Colores
Los gráficos usan una paleta consistente de azules para facilitar la lectura visual.

---

## 3. Descarga de Información

### Exportar Gráficos
Para guardar los gráficos:
1. Haga clic derecho sobre el gráfico deseado
2. Seleccione "Guardar imagen como..."
3. Elija ubicación y formato (PNG)

### Captura de Pantalla
Para reportes completos:
1. Use la función de captura de pantalla del sistema
   - **Windows**: Win + Shift + S
   - **macOS**: Cmd + Shift + 4
   - **Linux**: PrintScreen o herramienta de captura

### Impresión
1. Use Ctrl+P (Cmd+P en Mac)
2. Seleccione "Guardar como PDF" para archivo digital

---

## 4. Casos de Uso

### Reportes de Cumplimiento
Use las estadísticas para generar informes sobre:
- Volumen de denuncias recibidas
- Patrones de comportamiento de denunciantes
- Nivel de confianza en la plataforma (identificación voluntaria)
- Medios de acceso utilizados

### Análisis de Tendencias
Compare periódicamente:
- Incremento/decremento en número de reportes
- Cambios en el uso de Tor (indica percepción de seguridad)
- Porcentaje de denunciantes que se identifican

### Mejora de la Plataforma
Los datos ayudan a decidir:
- Si optimizar la versión móvil
- Si promover más el acceso vía Tor
- Estrategias para aumentar la confianza de denunciantes

---

## 5. Limitaciones del Rol

El analista tiene acceso **únicamente** a estadísticas agregadas. **NO puede**:
- Ver contenido de denuncias individuales
- Acceder a datos personales de denunciantes
- Identificar reportes específicos
- Modificar configuraciones del sistema

Esta separación garantiza que el análisis estadístico se realice sin comprometer la confidencialidad de las denuncias.
