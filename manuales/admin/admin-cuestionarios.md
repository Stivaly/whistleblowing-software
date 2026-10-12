# Manual de Usuario - Cuestionarios (Panel Administrador)

## Pestañas

El módulo de Cuestionarios contiene dos pestañas principales:
1. **Cuestionarios** - Gestión de cuestionarios completos
2. **Plantillas de Preguntas** - Preguntas reutilizables

---

## 1. Cuestionarios

### Gestión de Cuestionarios

**Acciones disponibles:**
- **Agregar**: Crear nuevo cuestionario (solo requiere nombre)
- **Importar**: Cargar cuestionario desde archivo JSON exportado previamente

**Acciones por cuestionario:**
- **Editar**: Modificar nombre y estructura del cuestionario
- **Guardar**: Guardar los cambios realizados
- **Cancelar**: Descartar cambios sin guardar
- **Exportar**: Descargar el cuestionario como archivo JSON
- **Duplicar**: Crear una copia del cuestionario
- **Eliminar**: Borrar el cuestionario (solo si es editable)

---

### Estructura del Cuestionario

Un cuestionario se organiza de la siguiente manera:

```
Cuestionario
└── Pasos (secciones)
    └── Preguntas
        └── Opciones (para preguntas de selección)
```

---

### Pasos (Secciones)

Los pasos son las secciones o páginas del cuestionario. Cada paso agrupa preguntas relacionadas.

#### Crear un Paso

1. Haga clic en **"Agregar"** junto a "Pasos"
2. Ingrese la **Etiqueta** (nombre del paso)
3. Haga clic en **"Agregar"**

#### Propiedades del Paso

| Campo | Descripción |
|-------|-------------|
| **Etiqueta** | Nombre visible del paso para el usuario |
| **Descripción** | Texto explicativo que aparece al inicio del paso |
| **Activado por puntuación** | (Si el sistema de puntuación está habilitado) Define qué nivel de puntuación activa este paso: Bajo, Medio o Alto |
| **Condiciones de activación** | Reglas que determinan cuándo mostrar este paso |

#### Acciones del Paso

- **Mover arriba/abajo**: Cambiar el orden del paso
- **Editar**: Modificar propiedades y preguntas
- **Guardar**: Guardar cambios
- **Cancelar**: Descartar cambios
- **Eliminar**: Borrar el paso y sus preguntas

---

### Preguntas

Las preguntas son los campos que el usuario debe completar.

#### Agregar Preguntas

Existen dos formas de agregar preguntas:

1. **Nueva pregunta**: Crear una pregunta desde cero
   - Ingrese el nombre de la pregunta
   - Seleccione el tipo
   - Haga clic en "Agregar"

2. **Desde plantilla**: Usar una pregunta predefinida
   - Seleccione la plantilla deseada del menú desplegable
   - Haga clic en "Agregar"
   - La pregunta se agrega como referencia a la plantilla

---

### Tipos de Preguntas

| Tipo | Descripción | Uso recomendado |
|------|-------------|-----------------|
| **Texto una línea** | Campo de texto corto | Nombres, títulos, respuestas breves |
| **Texto multilínea** | Área de texto grande | Descripciones detalladas, narrativas |
| **Caja de selección** | Menú desplegable | Seleccionar UNA opción de una lista |
| **Opción múltiple** | Botones de radio/checkbox | Seleccionar VARIAS opciones |
| **Casilla de verificación** | Checkbox simple | Preguntas Sí/No |
| **Adjunto** | Subir archivos | Documentos, imágenes, evidencia |
| **Términos de servicio** | Aceptación obligatoria | Políticas, consentimientos |
| **Fecha** | Selector de fecha | Fechas específicas |
| **Rango de fechas** | Dos selectores de fecha | Períodos de tiempo |
| **Voz** | Grabación de audio | Testimonios orales |
| **Grupo de preguntas** | Contenedor de preguntas | Agrupar preguntas relacionadas |

---

### Propiedades de las Preguntas

Al editar una pregunta, encontrará los siguientes campos:

#### Campos Básicos

| Campo | Descripción |
|-------|-------------|
| **Nombre (Etiqueta)** | Texto de la pregunta que verá el usuario. Es el título principal de la pregunta. |
| **Pista (Hint)** | Texto de ayuda breve que aparece junto a la pregunta. Útil para aclaraciones rápidas. |
| **Descripción** | Texto explicativo más extenso. Proporciona contexto adicional sobre la pregunta. |
| **Placeholder** | Texto de ejemplo dentro del campo (solo para texto una línea y multilínea). Desaparece cuando el usuario empieza a escribir. |
| **Obligatorio** | Si está marcado, el usuario debe responder esta pregunta para continuar. |
| **Vista previa** | Si está marcado, la respuesta se mostrará en la vista previa del reporte. |
| **Ancho** | Ancho del campo en columnas (0-12). 0 = automático, 12 = ancho completo. |

#### Campos de Posicionamiento

| Campo | Descripción |
|-------|-------------|
| **Fila** | Posición vertical de la pregunta |
| **Columna** | Posición horizontal de la pregunta |
| **Ancho** | Espacio horizontal que ocupa (sistema de 12 columnas) |

**Botones de movimiento:**
- Flechas izquierda/derecha: Mover horizontalmente
- Flechas arriba/abajo: Mover verticalmente

---

### Propiedades Específicas por Tipo

#### Texto una línea / Texto multilínea / Voz

| Campo | Descripción |
|-------|-------------|
| **Mín** | Longitud mínima de caracteres. 0 = sin límite. |
| **Máx** | Longitud máxima de caracteres. 0 = sin límite. |
| **Validación de entrada** | Tipo de validación: Ninguna, Email, Número, Teléfono, Personalizada |
| **Expresión regular** | (Solo si validación = Personalizada) Patrón regex para validar la entrada |

#### Caja de selección / Opción múltiple / Casilla de verificación

| Campo | Descripción |
|-------|-------------|
| **Mostrar opciones alfabéticamente** | Ordena las opciones de A-Z |
| **Opciones** | Lista de opciones disponibles (ver sección Opciones) |

#### Fecha / Rango de fechas

| Campo | Descripción |
|-------|-------------|
| **Fecha más temprana seleccionable** | Fecha mínima que el usuario puede elegir |
| **Fecha más tardía seleccionable** | Fecha máxima que el usuario puede elegir |

#### Términos de servicio

| Campo | Descripción |
|-------|-------------|
| **Texto** | Contenido de los términos que el usuario debe aceptar |
| **Etiqueta de la casilla** | Texto junto al checkbox de aceptación |
| **Adjunto** | Habilitar enlace a documento adjunto |
| **Texto del adjunto** | Texto del enlace al documento |
| **URL del adjunto** | Dirección del documento |

#### Adjunto (Subir archivos)

| Campo | Descripción |
|-------|-------------|
| **Aceptar múltiples archivos** | Permitir subir más de un archivo |

#### Grupo de preguntas

| Campo | Descripción |
|-------|-------------|
| **Aceptar múltiples respuestas** | Permitir agregar múltiples instancias del grupo |
| **Agregar contenido multimedia** | Incluir imagen, audio o video en el grupo |
| **Tipo de multimedia** | Imagen, Audio o Video |
| **URL del multimedia** | Dirección del contenido multimedia |

---

### Condiciones de Activación

Las condiciones de activación permiten mostrar u ocultar preguntas (o pasos) basándose en las respuestas a otras preguntas.

#### Cómo funcionan

Una pregunta con condiciones de activación solo se mostrará cuando se cumplan las condiciones especificadas.

#### Configurar una Condición

1. En la pregunta, haga clic en **"Agregar"** junto a "Condiciones de activación"
2. **Seleccione la pregunta**: Elija la pregunta cuya respuesta activará esta
3. **Seleccione la opción**: Elija qué respuesta debe tener la pregunta anterior
4. **Suficiente**: Si está marcado, esta condición por sí sola activa la pregunta
5. Haga clic en **"Agregar"**

#### Lógica de las Condiciones

- **Sin condiciones**: La pregunta siempre se muestra
- **Una condición**: La pregunta se muestra si se cumple esa condición
- **Múltiples condiciones**:
  - Si alguna tiene "Suficiente" marcado: Se muestra si cualquiera de las suficientes se cumple
  - Si ninguna tiene "Suficiente": Se muestra solo si TODAS las condiciones se cumplen

#### Ejemplo Práctico

```
Pregunta 1: "¿Tiene pruebas documentales?"
  - Opciones: Sí, No

Pregunta 2: "Suba los documentos" (tipo Adjunto)
  - Condición de activación: Pregunta 1 = "Sí"

Resultado: La pregunta 2 solo aparece si el usuario responde "Sí" en la pregunta 1.
```

#### Activación por Puntuación

Si el sistema de puntuación está habilitado, puede configurar que la pregunta solo aparezca cuando la puntuación acumulada alcance cierto nivel:
- **Bajo**: Aparece siempre
- **Medio**: Aparece con puntuación media o alta
- **Alto**: Solo aparece con puntuación alta

---

### Opciones (para preguntas de selección)

Las preguntas de tipo Caja de selección, Opción múltiple y Casilla de verificación requieren definir opciones.

#### Agregar una Opción

1. En la pregunta, haga clic en **"Agregar"** junto a "Opciones"
2. Ingrese la **Etiqueta** de la opción
3. Configure las propiedades adicionales si es necesario

#### Propiedades de las Opciones

| Botón | Función |
|-------|---------|
| **Eliminar** (X roja) | Elimina la opción |
| **Mover arriba/abajo** | Cambia el orden de la opción |
| **Pista** (?) | Agregar texto de ayuda a la opción. Incluye dos campos: Pista 1 y Pista 2 |
| **Bloquear envío** (prohibido) | Si se selecciona esta opción, se bloquea el envío del formulario |
| **Destinatarios** (usuario) | Asignar destinatarios específicos que recibirán el reporte si se elige esta opción |
| **Puntuación** (rayo) | (Si está habilitado) Asignar puntos a esta opción |

#### Sistema de Puntuación

Si el sistema de puntuación está habilitado, cada opción puede tener:
- **Tipo de puntuación**: Adición o Multiplicador
- **Puntos**: Valor numérico

---

### Acciones de las Preguntas

| Acción | Descripción |
|--------|-------------|
| **Editar** | Abrir el editor de la pregunta |
| **Guardar** | Guardar los cambios |
| **Cancelar** | Descartar cambios |
| **Exportar** | Descargar la pregunta como archivo JSON |
| **Eliminar** | Borrar la pregunta |
| **Mover** | Flechas para cambiar posición (izq, der, arriba, abajo) |

---

## 2. Plantillas de Preguntas

Las plantillas son preguntas predefinidas que pueden reutilizarse en múltiples cuestionarios.

### Ventajas de usar Plantillas

- **Consistencia**: La misma pregunta en todos los cuestionarios
- **Mantenimiento centralizado**: Cambios en la plantilla se reflejan en todos los cuestionarios
- **Rapidez**: Agregar preguntas comunes con un clic

### Gestión de Plantillas

**Acciones disponibles:**
- **Agregar**: Crear nueva plantilla de pregunta
- **Importar**: Cargar plantilla desde archivo JSON

### Crear una Plantilla

1. Haga clic en **"Agregar"**
2. Ingrese el **nombre** de la plantilla
3. Seleccione el **tipo** de pregunta
4. Haga clic en **"Agregar"**
5. Configure las propiedades de la pregunta

### Usar una Plantilla en un Cuestionario

1. En el paso deseado, haga clic en **"Agregar pregunta desde plantilla"**
2. Seleccione la plantilla del menú desplegable
3. Haga clic en **"Agregar"**

La pregunta se agrega como **referencia** a la plantilla. Los cambios en la plantilla original afectarán a todas las preguntas que la usen.

### Identificar Preguntas de Plantilla

Las preguntas basadas en plantillas muestran la etiqueta "Plantilla" en lugar del tipo específico.

### Sobrescritura de Plantilla

El campo **"Template override"** permite especificar un ID de plantilla alternativo para casos especiales.

---

## Buenas Prácticas

### Organización

1. **Agrupe preguntas relacionadas** en el mismo paso
2. **Use nombres descriptivos** para pasos y preguntas
3. **Ordene los pasos** de forma lógica (de general a específico)
4. **Limite las preguntas obligatorias** a lo esencial

### Condiciones de Activación

1. **Simplifique el flujo** ocultando preguntas no relevantes
2. **Evite condiciones complejas** que confundan al usuario
3. **Pruebe el cuestionario** con diferentes respuestas

### Plantillas

1. **Use plantillas** para preguntas que se repiten
2. **Nombre las plantillas claramente** para fácil identificación
3. **Documente el propósito** de cada plantilla

### Validación

1. **Configure validaciones** apropiadas (email, teléfono, etc.)
2. **Establezca límites** de caracteres razonables
3. **Use pistas** para guiar al usuario

---

## Importar y Exportar

### Exportar

Los cuestionarios y preguntas se exportan en formato JSON, incluyendo:
- Estructura completa
- Pasos y preguntas
- Opciones y condiciones
- Configuraciones

### Importar

1. Haga clic en **"Importar"**
2. Seleccione el archivo JSON
3. El sistema validará y cargará el contenido

**Nota**: Al importar, se crea una copia nueva. No se sobrescriben cuestionarios existentes.
