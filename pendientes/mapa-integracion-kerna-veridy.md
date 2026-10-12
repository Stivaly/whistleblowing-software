# Mapa de integración Kerna → Veridy (2026-10-04)

Referencia de trabajo para implementar. El razonamiento completo está en los docs:

- Informe del sistema: https://claude.ai/code/artifact/4105b4d0-68ff-449f-9118-e72a04a38d75
- Cifrado: https://claude.ai/code/artifact/5f0f11d0-049d-47c8-902e-d397176ceeae
- Plan de integración: https://claude.ai/code/artifact/05bcaf21-a791-44aa-965a-09baa71bfa4e

Análisis de origen, con referencias `ruta:línea`: `pendientes/analisis-veridy/arquitectura.md` y
`pendientes/analisis-veridy/cifrado.md`.

## Hechos que condicionan todo

- Veridy = GlobaLeaks 5.0.85, `DATABASE_VERSION = 68` (`backend/globaleaks/__init__.py:9-13`).
- Cifrado en el servidor, una clave X25519 por denuncia. El texto solo está en claro en memoria:
  envío (`handlers/whistleblower/submission.py:168-262`) y lectura con sesión (`handlers/recipient/rtip.py:1160`).
- Cifrar no requiere sesión: `InternalTip.crypto_tip_pub_key`. Descifrar requiere `session.cc`.
- `InternalTipData` NO sirve para guardar sugerencias: el serializador la entrega también al denunciante
  (`models/serializers.py:232-238`) y `decrypt_tip` solo descifra `whistleblower_identity`.
- La CSP `connect-src 'self'` (`rest/api.py:555`) obliga a pasar por el backend. No hay `requests`: usar
  `twisted.web.client.Agent` (`utils/agent.py`), nunca dentro de `@transact`.
- `State.get_agent()` sale por Tor si `anonymize_outgoing_connections` (`state.py:116-120`): usar un agente dedicado.
- Resultado por pull (job de consulta): no añade endpoints entrantes a Veridy.

## Decisión de diseño (plan §6)

A pedido del receptor + job de consulta (pull). Reglas R1–R5 (plan §5): solo texto anonimizado sale; todo
resultado se cifra con `crypto_tip_pub_key`; en claro solo metadatos operativos; Kerna nunca recibe claves;
ningún texto en logs/trazas.

## Archivos nuevos

| Archivo | Qué |
| --- | --- |
| `backend/globaleaks/kerna/anonimizador.py` | Adaptar `fable upgrades/kerna_entrega2.zip!gl_patches/backend/globaleaks/anonimizador.py` |
| `backend/globaleaks/kerna/texto.py` | Relato desde la ficha descifrada y redactada, sin identidad ni adjuntos. Definir aquí la profundidad máxima (el parche de referencia importa `MAX_ANSWERS_DEPTH`, que no existe) |
| `backend/globaleaks/kerna/cifrado.py` | `GCE.asymmetric_encrypt(tip_pub_key, json)` / `GCE.asymmetric_decrypt(tip_key, ...)` en Base64, como `label` (`rtip.py:891-892`) |
| `backend/globaleaks/kerna/cliente.py` | `enviar_denuncia`, `consultar_sugerencia`, `enviar_feedback`; clave desde `/var/globaleaks/kerna.key` (0600) |
| `backend/globaleaks/handlers/recipient/kerna.py` | POST/GET `/api/recipient/rtips/<id>/kerna`, POST `.../kerna/feedback`; `check_roles='receiver'`; reutilizar `get_rtip` + `decrypt_tip` + `redact_report` como `export.py:146-152` |
| `backend/globaleaks/jobs/kerna.py` | `KernaConsulta(LoopingJob)` cada 15 s; patrón de `jobs/delivery.py:114-134` |
| `backend/globaleaks/db/migrations/update_69/__init__.py` | `class MigrationScript(MigrationBase): pass` |
| `backend/globaleaks/tests/kerna/` | Ver plan §13 |
| `client/app/src/shared/partials/tip-kerna/` | Panel standalone |
| `client/app/src/models/receiver/kerna.ts` | Tipos |

## Archivos upstream a tocar

| Archivo | Punto | Cambio |
| --- | --- | --- |
| `backend/globaleaks/__init__.py` | `:12` | `DATABASE_VERSION = 69` |
| `backend/globaleaks/models/__init__.py` | mixins + clases finales (`:1049-1182`) | `_KernaSolicitud`, `_KernaFeedback` (FK `internaltip`/`kerna_solicitud`, `ondelete='CASCADE'`, `deferrable`) |
| `backend/globaleaks/db/migration.py` | `migration_mapping` `:47-85` | Un `0` al final de cada lista + `[-1]*17 + [models._KernaX]` |
| `backend/globaleaks/models/config_desc.py` | `:32-128` y filtros | `kerna_enabled`, `kerna_url`, `kerna_organizacion`, `kerna_sintetico` (sembrado solo si cambia `__version__`, `db/migration.py:130-146`) |
| `backend/globaleaks/rest/api.py` | bloque receptor `:74-85` | 2 rutas |
| `backend/globaleaks/rest/requests.py` | junto a `CommentDesc` `:169-172` | `KernaFeedbackDesc` |
| `backend/globaleaks/handlers/recipient/__init__.py` | `:16` | `import globaleaks.handlers.recipient.kerna` |
| `backend/globaleaks/jobs/__init__.py` | `jobs_list` `:15-29` | `KernaConsulta` |
| `backend/globaleaks/handlers/analyst/__init__.py` | `get_stats` | Conteos por estado/acción, sin contenido |
| `client/app/src/shared/services/http.service.ts` | `:328` | 3 métodos |
| `client/app/src/pages/recipient/tip/tip.component.{ts,html}` | `imports :48-73`, plantilla `:143-169` | pestaña |
| `client/app/src/pages/analyst/statistics/*` | — | sección nueva |
| `client/app/src/pages/admin/settings/` | — | ajustes Kerna (estructura de pestañas sin verificar) |
| `client/app/assets/data/l10n/es.json` | — | textos (no `i18n/`) |

No tocar: `submission.py`, `utils/crypto.py`, `sessions.py`, `RTipInstance.get`, notificaciones.

## Tablas

- `kerna_solicitud`: `id` (= request_id), `tid`, `internaltip_id`, `user_id`, `estado`
  (pendiente|lista|sin_sugerencia|fallida|caducada), fechas, `modelo`, `version_prompt`, `modelo_provisional`,
  `hash_texto`, `resultado` (cifrado).
- `kerna_feedback`: `id`, `solicitud_id`, `user_id`, `creation_date`, `accion` (en claro), `detalle` (cifrado).

## Contrato con Kerna (Azure Functions, clave de Function)

- `POST /api/denuncias` `{request_id, organizacion, texto, sintetico, idioma}` → 202
- `GET /api/sugerencias/{request_id}` → 404 mientras no está; luego `ResultadoClasificar`
  (`fable upgrades/kerna_entrega2.zip!kerna_orquestador/schemas.py`)
- `POST /api/feedback` `{request_id, suggestion_ref, accion, etiqueta, comentario}`

## Bloqueos antes de implementar (plan §15)

Migración de los datos de prueba que reemplaza al script temporal `etl_incremental.py` (destino a evaluar: Azure SQL
Database o Azure Database for PostgreSQL), atribución, escrow por defecto, rama de trabajo.

## Base de datos en PostgreSQL de Azure (hecho en código, 2026-10-04)

- Modo PostgreSQL con `GLOBALEAKS_DB_URI` (+ `PGPASSWORD`); `GLOBALEAKS_DB_ADMIN_URI` solo en el primer arranque.
  Sin la variable, SQLite como siempre. Guía: `docker/README-postgres.md`.
- Cambios: `settings.py`, `orm.py`, `db/__init__.py`, `db/migration.py`, `models/properties.py` (TEXT sin longitud),
  `models/__init__.py` (`ReceiverFile.size` TEXT en PG), `handlers/recipient/__init__.py` (sin GROUP BY),
  `handlers/whistleblower/submission.py` (contador con bloqueo), `jobs/notification.py`, `tests/helpers.py`
  (`GLOBALEAKS_TEST_PG_URI` corre la suite sobre una base PG desechable).
- Infra: `infra/terraform/postgres.tf` (`crear_postgres`), `infra/sql/veridy_roles.sql`, README pasos 11 y 12.
- Docker: `python3-psycopg2` en el Dockerfile; `docker/docker-compose.nube.yml` (volumen `veridy_nube`);
  `docker/veridy-db.env` fuera de git.
- Las tablas nuevas de Kerna (migración 69) deben probarse también con `GLOBALEAKS_TEST_PG_URI`. En PostgreSQL no hay
  migración automática: subir `DATABASE_VERSION` exige un procedimiento manual o recrear la base (prototipo).
- Pruebas y recursos Docker de prueba: `pendientes/recursos-de-prueba.md`.
