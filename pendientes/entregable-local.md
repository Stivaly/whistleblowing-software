# Entregable local (Veridy + Kerna en un computador) — 2026-11-22

Detalle técnico en `entregable/README.md`. Decisiones tomadas sin consultar (revisables):

- Cuenta del panel para quien prueba: `evaluador.prueba`, rol **Evaluación** (ve todo, no cambia nada; la Demo sí se
  usa). El panel local comparte las tablas de producción, así que un rol que edita podría borrar clientes o cuentas reales.
  Si se quiere que pruebe Ajustes, cambiarle el rol a Operación de IA desde Cuentas.
- Configuración en Azure para redes cerradas: pasarela de identidad `ca-kerna-dev-pasarela` (Container App, escala a
  cero, solo HTTPS 443) creada con `infra/aplicar.sh kerna` (9 recursos nuevos, nada modificado). No se pudo usar un
  registro de aplicación: la suscripción no permite crearlos.
- Cliente del núcleo `veridy-local` (plan Plataforma, 500 casos/mes) para el conector local; secreto en Key Vault
  (`veridy-local-client-secret`). Aparece en Administrar clientes.
- El conector local lee y escribe las mismas filas de `ajustes` y `reintentosmanuales` que el de Azure (el panel
  muestra los casos de la instalación local). Con Veridy de Azure apagado no hay conflicto.
- La semilla de Veridy parte de la personalización del volumen `docker_globaleaks` (sin sus denuncias de prueba, que
  ninguna cuenta nueva podría leer). El volumen original no se tocó.
- La cuenta de servicio del conector debe llamarse «Kerna AI…» (así la reconoce el bloque de Kerna).

## Recursos Docker de prueba en este servidor (se pueden limpiar)

- Volúmenes: `semilla-veridy`, `semilla-base`, `semilla-20261122-*` (copias de prueba, sin denuncias reales).
- Contenedores detenidos: `semilla-veridy`, `semilla-v2`, `semilla-v3`, `semilla-v4`.
- Proyecto `veridy-kerna` (Veridy local de prueba en 8400-8402), encendido para las capturas: `entregable/dist/veridy-kerna-local/detener.sh`.
