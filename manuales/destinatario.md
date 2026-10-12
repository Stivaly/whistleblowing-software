# Manual de Usuario - Destinatario (Recipient)

## Navegación Principal

El panel del destinatario tiene las siguientes secciones:
- **Inicio**: Panel principal con resumen
- **Reportes**: Lista de todas las denuncias asignadas
- **Configuración**: Ajustes personales (si tiene permisos)

---

## 1. Lista de Reportes

### Vista General
La lista muestra todas las denuncias asignadas en formato de tabla con las siguientes columnas:

| Columna | Descripción |
|---------|-------------|
| ☐ | Casilla de selección múltiple |
| ★ | Marcado como importante |
| 🔔 | Tiene recordatorio configurado |
| # | Número progresivo del reporte |
| Canal | Categoría de la denuncia |
| Etiqueta | Etiqueta personalizada asignada |
| Estado | Estado actual del caso |
| Fecha reporte | Cuándo se creó |
| Última actualización | Último cambio |
| Fecha expiración | Cuándo se eliminará |
| ✉ | Si el denunciante leyó la última actualización |
| 💬 | Cantidad de comentarios |
| 📎 | Cantidad de archivos |
| 👤 | Si proporcionó identidad |
| 👥 | Cantidad de destinatarios |
| Puntuación | Prioridad (si está habilitado) |

### Ordenamiento
Haga clic en el encabezado de cualquier columna para ordenar:
- Un clic: Orden ascendente
- Segundo clic: Orden descendente
- Icono de flecha indica dirección actual

### Filtros Disponibles

**Por Canal**: Icono de filtro junto a "Canal"
- Seleccione uno o más canales
- El icono se resalta cuando hay filtro activo

**Por Estado**: Icono de filtro junto a "Estado"
- Filtre por: Nuevo, Abierto, Cerrado, etc.
- Permite selección múltiple

**Por Fecha de Reporte**: Icono de calendario
- Seleccione rango de fechas de creación

**Por Última Actualización**: Icono de calendario
- Filtre por fecha de última modificación

**Por Fecha de Expiración**: Icono de calendario
- Encuentre reportes próximos a expirar

**Por Puntuación** (si está habilitado):
- Filtre por prioridad: Baja, Media, Alta

### Acciones en Lote

**Selección:**
- Casilla individual: Selecciona un reporte
- "Seleccionar todos": Marca todos los visibles
- "Deseleccionar todos": Quita todas las marcas

**Con reportes seleccionados:**
- **Otorgar acceso**: Dar acceso a otro usuario
- **Revocar acceso**: Quitar acceso a un usuario
- **Exportar**: Descargar reportes seleccionados

**Otras acciones:**
- **Actuar como denunciante**: Crear denuncia en nombre de alguien
- **Actualizar**: Recargar lista
- **Exportar CSV**: Descargar lista completa

---

## 2. Detalle del Reporte

### Barra de Herramientas

**Navegación:**
- ← Volver a lista de reportes

**Marcadores:**
- ★ **Importante**: Marca/desmarca como prioritario
- 🔔 **Recordatorio**: Configura fecha de recordatorio
- 🔇/🔊 **Notificaciones**: Activa/silencia emails para este reporte

**Gestión de Usuarios** (si tiene permisos):
- **Otorgar acceso**: Dar acceso a otros destinatarios
- **Revocar acceso**: Quitar acceso a usuarios
- **Transferir acceso**: Mover reporte a otro usuario

**Opciones:**
- **Editar expiración**: Cambiar fecha de eliminación
- **Enmascarar**: Ocultar información sensible
- **Cambiar estado**: Modificar estado del caso
- **Reabrir**: Reabrir caso cerrado
- **Eliminar**: Borrar reporte permanentemente

**Exportación:**
- **Descargar**: Exportar reporte completo
- **Imprimir**: Versión para impresión

### Información del Reporte

Muestra datos principales:
- **Etiqueta**: Campo editable para clasificar
- **ID**: Identificador único
- **Canal**: Categoría de la denuncia
- **Fechas**: Creación, actualización, expiración, recordatorio
- **Lectura**: Si el denunciante leyó la última actualización
- **Tor**: Si se envió por red anónima
- **Estado**: Estado actual
- **Puntuación**: Nivel de prioridad

### Lista de Destinatarios
Si hay múltiples destinatarios, muestra quiénes tienen acceso al reporte.

### Respuestas del Cuestionario
Información proporcionada por el denunciante. Si tiene permisos de enmascaramiento, puede ocultar datos sensibles.

### Identidad del Denunciante
Si el denunciante proporcionó su identidad voluntariamente, aparece en panel separado.

### Archivos Adjuntos
Lista de archivos subidos por el denunciante con opciones de descarga.

### Pestañas de Comunicación

**Público**: Comentarios visibles para el denunciante
- Use esta pestaña para comunicarse con el informante
- El denunciante puede ver y responder estos mensajes

**Interno**: Comentarios entre destinatarios
- Solo visible para otros destinatarios del caso
- El denunciante NO puede ver estos comentarios
- Útil para coordinación interna

**Personal**: Notas privadas
- Solo usted puede ver estos comentarios
- Para anotaciones personales sobre el caso

En cada pestaña puede:
- Subir archivos adicionales
- Escribir comentarios (máx 4096 caracteres)

---

## 3. Gestión de Estados

### Estados Principales
- **Nuevo**: Denuncia recién recibida
- **Abierto**: En proceso de investigación
- **Cerrado**: Caso finalizado

### Cambiar Estado
1. Abra el reporte
2. Vaya a Opciones → "Cambiar estado"
3. Seleccione el nuevo estado/subestado
4. El cambio queda registrado en comentarios

### Reabrir Caso
Si un caso está cerrado y necesita reabrirse:
1. Vaya a Opciones → "Reabrir"
2. El caso vuelve a estado "Abierto"

---

## 4. Funciones Especiales

### Marcar como Importante (★)
- Resalta el reporte en la lista
- Útil para priorizar casos urgentes

### Configurar Recordatorio (🔔)
- Define fecha para recibir alerta
- El icono cambia a amarillo cuando la fecha pasa

### Enmascarar Información
Permite ocultar datos sensibles:
1. Active modo "Enmascarar"
2. Seleccione el texto a ocultar
3. La información se oculta pero puede recuperarse

### Redactar Permanentemente
Si tiene permisos adicionales:
- Puede eliminar permanentemente información enmascarada
- Esta acción es IRREVERSIBLE

### Otorgar/Revocar Acceso
- **Otorgar**: Permite a otro destinatario ver el reporte
- **Revocar**: Quita el acceso a un destinatario
- **Transferir**: Mueve completamente el caso a otro usuario

### Actuar como Denunciante
Permite crear una denuncia en nombre de alguien:
- Útil para denuncias recibidas por otros medios (teléfono, presencial)
- El reporte se crea como si lo hubiera enviado el denunciante

---

## 5. Indicadores Visuales

### En la Lista
- **Negrita**: Reporte con actualizaciones no leídas
- **★ Amarilla**: Marcado como importante
- **🔔 Amarilla**: Recordatorio vencido
- **✓**: Denunciante leyó última actualización
- **✗**: Denunciante NO ha leído última actualización

### Puntuación (si está habilitado)
- **-**: Sin puntuación
- **Baja**: Prioridad baja
- **Media**: Prioridad media
- **Alta**: Prioridad alta

### Identidad
- **✗**: No solicitada o no proporcionada
- **✓**: Solicitada pero no proporcionada
- **✓ subrayado**: Identidad proporcionada (con fecha)

---

## 6. Exportación

### Exportar Reporte Individual
1. Abra el reporte
2. Icono de descarga → "Descargar"
3. Se genera archivo ZIP con toda la información

### Exportar Lista a CSV
1. En lista de reportes
2. Clic en "Exportar" (parte inferior)
3. Descarga archivo CSV con datos tabulares

### Imprimir
1. Abra el reporte
2. Icono de descarga → "Imprimir"
3. Abre versión optimizada para impresión
