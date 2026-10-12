# Manual de Usuario - Gestión de Casos (Panel Administrador)

## Estados de Denuncia

Define el flujo de trabajo para procesar denuncias.

**Estados del Sistema** (no eliminables):
- Nuevo, Abierto, Cerrado (predefinidos)

**Estados Personalizados:**
- **Agregar**: Crear nuevo estado
- **Editar**: Cambiar etiqueta
- **Ordenar**: Flechas arriba/abajo
- **Eliminar**: Solo estados personalizados

**Subestados:**
Subdividen un estado principal (ej: "Cerrado" → "Resuelto", "Rechazado", "Duplicado")

- **Agregar**: Crear nuevo subestado dentro de un estado
- **Editar/Guardar/Cancelar**: Modificar subestado
- **Ordenar**: Flechas arriba/abajo
- **Eliminar**: Borrar subestado

Propiedades del subestado:
- **Etiqueta**: Nombre del subestado
- **Fecha de expiración** (días):
  - *Deshabilitado*: Sin cambio en expiración
  - *Personalizado*: Número de días hasta expirar el reporte al asignar este subestado
