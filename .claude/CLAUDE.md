# Regla de eliminación (proyecto whistleblowing-software)
- NUNCA eliminar archivos, carpetas, ramas, contenedores, volúmenes ni datos.
- Si algo "debe eliminarse": moverlo con `mv` a `.papelera/AAAA-MM-DD/<ruta-original>` (conservando la ruta) y continuar.
- Registrar cada movimiento en `pendientes/eliminaciones-pendientes.md` (fecha, ruta original, ruta en papelera, motivo) para que la usuaria decida.
- Trabajo autónomo: no detenerse a preguntar salvo bloqueo real; documentar decisiones en `pendientes/`.

# Mapa del proyecto
- Veridy = fork de GlobaLeaks 5.0.85 (esquema BD 68). Backend Python/Twisted en `backend/globaleaks/`, cliente Angular 19 en `client/app/src/`, despliegue en `docker/`.
- Kerna (IA de sugerencia normativa) en `kerna/` e infraestructura Azure en `infra/`. `fable upgrades/` es solo referencia y puede estar desactualizado.
- Integración Kerna → Veridy: leer `pendientes/mapa-integracion-kerna-veridy.md` antes de tocar código. Análisis detallados en `pendientes/analisis-veridy/`.
- Ignorar al buscar: `documentation/` (docs upstream), `client/dist`, `client/.angular`, `client/node_modules`, `venv/`, `docker/globaleaks.tar`.
- Cifrado: el texto de una denuncia solo existe en claro en memoria (envío y lectura con sesión del receptor). Todo dato derivado de una denuncia se guarda cifrado con `InternalTip.crypto_tip_pub_key`. Nunca desactivar `encryption` ni usar escrow para procesar.
