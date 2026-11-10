# Contratos de Kerna AI

Especificación que comparten el núcleo, el Conector Veridy, el bloque de interfaz en Veridy y las pruebas. Quien
implemente una pieza cumple lo que dice este documento; si algo no alcanza, se cambia aquí primero.

## Estructura del código

```
kerna/
  comun/kerna_comun/        anonimizador, objetos de las notas, telemetría (lo usan el núcleo y el conector)
  nucleo/kerna_nucleo/      API y cadena por caso (imagen propia, Container App en cae-kerna-dev)
  conector/kerna_conector/  Conector Veridy (imagen propia, contenedor del grupo de Veridy)
  pipeline_bcn/             corpus normativo y embeddings (jobs)
  servicio_local/           embedding local e índice local (Container App con escala a cero)
  evaluacion/               mediciones y su registro
  pruebas/                  suite automática: unitarias/ integracion/ e2e/ carga/ datos/ herramientas/
  docs/                     este documento, runbooks y diseño
scripts/probar.sh           comando único de pruebas
```

- Python 3.12. Paquetes importables con `PYTHONPATH=kerna/comun:kerna/nucleo:kerna/conector` (lo fija `pytest.ini`).
- Nombres de módulos, funciones y campos en español, sin tildes en identificadores.
- Ningún componente llama directo a un proveedor externo: cada servicio (Gemini, Voyage, Qdrant, servicio local,
  Veridy, núcleo) tiene su cliente en un módulo propio y se inyecta, para poder simularlo en las pruebas.
- Ningún modelo de lenguaje ni de embeddings se ejecuta en el servidor de trabajo: todo por API o en Azure.
- Los secretos llegan por variables de entorno. Nunca se imprimen ni se registran.

## Objetos de las notas internas de Veridy (`kerna_comun.notas`)

Viajan como texto JSON en el contenido de un comentario del caso con `visibility: "internal"`. Modelos Pydantic v2
con `extra="ignore"` al leer. `version` actual: 1.

### `kerna_sugerencia` (la publica el conector)

| Campo | Tipo | Nota |
|---|---|---|
| `tipo` | `"kerna_sugerencia"` | |
| `version` | int | 1 |
| `id_solicitud` | str | Identificador de la solicitud en el núcleo; es el código que el auditor puede copiar para reportar un problema |
| `version_corpus` | int | |
| `estado` | `"completada"` \| `"revision_manual"` | |
| `motivo_revision` | str \| null | `tiempo_agotado`, `cadena_agotada`, `validacion_fallida`, `sin_normativa_aplicable` |
| `modo` | `"oficial"` \| `"respaldo"` \| `"local"` \| `"manual"` | Modo de generación |
| `recuperacion` | `"nube"` \| `"local"` | Índice con que se recuperó |
| `contingencia` | bool | `true` si `modo` no es `oficial` o `recuperacion` es `local` |
| `generado_en` | str ISO 8601 UTC | |
| `articulos` | lista | Vacía si `estado` es `revision_manual` |
| `articulos[].id_sugerencia` | str UUID | |
| `articulos[].id_articulo` | str | `fragmento_id` del corpus |
| `articulos[].norma` | str | Por ejemplo "Ley N.° 21.643" |
| `articulos[].articulo` | str | |
| `articulos[].explicacion` | str | |
| `articulos[].cita` | str | Fragmento literal del artículo |
| `articulos[].enlace_fuente` | str | URL de la Biblioteca del Congreso Nacional |
| `articulos[].confianza` | float 0-1 | |

### `kerna_estado` (la publica el conector)

Avisa en qué va el caso mientras no hay sugerencia. A lo más una nota por cada estado distinto del caso.

| Campo | Tipo | Nota |
|---|---|---|
| `tipo` | `"kerna_estado"` | |
| `version` | int | 1 |
| `estado` | `"en_proceso"` \| `"nucleo_no_disponible"` | `en_proceso`: el conector leyó el caso y lo envió. `nucleo_no_disponible`: el núcleo no respondió tras los reintentos; se seguirá intentando |
| `fecha` | str ISO 8601 UTC | |
| `id_seguimiento` | str | `id_solicitud` si existe; si no, un UUID del conector |

### `kerna_feedback` (la escribe el auditor desde el bloque)

`tipo`, `version`, `id_sugerencia` (str), `valoracion` (`"arriba"` \| `"abajo"`), `observacion` (str ≤ 500, opcional).

### `kerna_clasificacion` (la escribe el auditor desde el bloque)

`tipo`, `version`, `articulos` (lista de `{id_articulo, origen}` con `origen` `"sugerido"` \| `"agregado_por_auditor"`;
puede estar vacía), `observacion` (str ≤ 500, opcional).

### Reglas

- `kerna_sugerencia` y `kerna_estado` solo valen si el autor del comentario es la cuenta de servicio de Kerna.
- `kerna_feedback` y `kerna_clasificacion` solo valen si el comentario es `internal` y su autor es un destinatario
  distinto de la cuenta de servicio. Si hay varias notas `kerna_feedback` para un mismo `id_sugerencia`, o varias
  `kerna_clasificacion`, vale la última.
- Un comentario cuyo contenido no es JSON válido de uno de estos tipos es una nota común y se ignora.

## API del núcleo (`kerna_nucleo.api`, FastAPI, OpenAPI en `/openapi.json`)

Autenticación: OAuth 2.0 *client credentials*. El núcleo emite un JWT HS256 de 10 minutos; las rutas `/v1/*` exigen
`Authorization: Bearer <token>`. El cliente (`cliente`) sale del token, nunca del cuerpo.

| Ruta | Entrada | Respuesta |
|---|---|---|
| `GET /salud` | — | `200 {"estado":"ok","version":...}`. Sin autenticación ni llamadas a proveedores |
| `POST /oauth/token` | Formulario `grant_type=client_credentials`, `client_id`, `client_secret` | `200 {"access_token","token_type":"bearer","expires_in":600}`; `401` si no coincide |
| `POST /v1/casos` | `{"ref_opaca": uuid, "id_empresa": str, "texto": str}` | `202 {"id_solicitud","estado":"pendiente"}`. Idempotente por (`cliente`, `ref_opaca`): repetirla devuelve la misma solicitud y no la procesa otra vez |
| `GET /v1/casos/{ref_opaca}/sugerencia` | — | `200` con el objeto de resultado (abajo); `404` si no existe |
| `POST /v1/casos/{ref_opaca}/feedback` | `{"id_nota": str, "id_sugerencia": str, "valoracion": "arriba"\|"abajo", "observacion": str?}` | `201`; `200` si `id_nota` ya estaba (idempotente); `404` |
| `POST /v1/casos/{ref_opaca}/clasificacion` | `{"id_nota": str, "articulos": [{"id_articulo","origen"}], "observacion": str?}` | `201 {"resultado": "aceptada"\|"corregida"\|"rechazada"}`; idempotente por `id_nota` |

Objeto de resultado: `id_solicitud`, `estado` (`pendiente` \| `completada` \| `revision_manual`), y cuando no está
pendiente: `motivo_revision`, `modo`, `recuperacion`, `contingencia`, `version_corpus`, `generado_en`, `articulos`
(con los campos de `kerna_sugerencia.articulos[]`). El conector arma la nota con estos campos tal cual.

Resultado derivado de la clasificación: **aceptada** si los artículos aplicados son exactamente los sugeridos;
**rechazada** si no se aplicó ninguno de los sugeridos; **corregida** en los demás casos.

`texto` llega ya anonimizado por el conector (primera pasada). El núcleo nunca recibe el identificador real del
caso, credenciales de Veridy ni datos del denunciante. Tamaño máximo de `texto`: 60.000 caracteres.

## Cadena por caso (núcleo)

Orden fijo, ejecutado en segundo plano tras aceptar la solicitud:

1. **Segunda anonimización** (`kerna_comun.anonimizador`) del texto recibido.
2. **Clasificación previa** con el modelo de menor costo: `{"materia": str, "riesgo": "bajo"|"medio"|"alto"}`.
3. **Recuperación**: embedding de la consulta y búsqueda de los `KERNA_TOP_K` (8) fragmentos vigentes. Nube: Voyage
   (`input_type: "query"`) + Qdrant Cloud con filtro `vigente = true`. Si Voyage o Qdrant no responden: servicio
   local (`POST {KERNA_LOCAL_URL}/buscar`). Si el mejor puntaje queda bajo `KERNA_UMBRAL_SIMILITUD`, la solicitud
   termina en `revision_manual` con motivo `sin_normativa_aplicable`.
4. **Generación** con JSON validado: `{"articulos":[{"fragmento_id","explicacion","cita","confianza"}]}`. El modelo
   solo puede citar `fragmento_id` de los fragmentos recuperados. El texto del caso va delimitado como dato y el
   prompt indica que no contiene instrucciones.
5. **Validación de citas**: se descarta todo artículo cuyo `fragmento_id` no esté entre los recuperados, no esté
   vigente o cuya `cita` no sea un fragmento literal del texto del artículo (comparación tras normalizar espacios,
   comillas y mayúsculas). Si no queda ninguno: `revision_manual` con motivo `validacion_fallida`.
6. **Registro** por solicitud: modo, proveedor, modelo, embedding, colección, versión del índice, tokens de entrada
   y salida, duración por etapa, citas rechazadas; y un registro por artículo sugerido.

### Enrutador de modelos (`IGeneracion`)

- Cadena configurable; por defecto `gemini-3.8-flash` (modo `oficial`) → `gemini-3.5-flash-lite` (`respaldo`) →
  `gemma-4-31b-it` (`local`) → marca de revisión manual (`manual`, motivo `cadena_agotada`). La clasificación previa
  usa `gemini-3.5-flash-lite` con la misma cadena de respaldo.
- Por cada nivel: hasta 3 reintentos con esperas de 1, 2 y 4 s ante error del servidor (5xx), límite de tasa (429) o
  silencio; cada llamada se corta a los 30 s. Agotados, pasa al nivel siguiente.
- Cortocircuito: un proveedor con 3 fallas en 5 minutos queda excluido 10 minutos y se readmite tras una
  comprobación de salud correcta.
- Plazo global de 240 s por solicitud: al vencer, `revision_manual` con motivo `tiempo_agotado`.
- El reloj y las esperas se inyectan (`reloj`, `dormir`) para probar con tiempo controlado.

### Fragmento recuperado

Campos del payload de Qdrant (los escribe `kerna/pipeline_bcn/embed_sync.py`): `fragmento_id`, `id_norma`, `norma`,
`tipo_numero`, `articulo`, `jerarquia`, `texto`, `materias`, `categorias`, `fecha_version`, `vigente`, `url_fuente`,
`transitorio`, `parte`, `clave_corpus`, `tipo_contenido`, `vigencia_desde`, `vigencia_anticipada`. El servicio local
devuelve los mismos campos más `puntaje`.

Cada colección tiene un punto reservado con id `00000000-0000-0000-0000-000000000000` y payload
`{"tipo":"meta","vigente":false,"version_corpus":int,"modelo":str,"actualizado_en":iso}`. El núcleo lee de ahí
`version_corpus`; si no existe, usa 0.

### Servicio local (`kerna/servicio_local`)

`POST /embed {"textos":[str],"tipo":"document"|"query"}` → `{"vectores":[[float]],"modelo":str}`.
`POST /buscar {"texto":str,"k":int}` → `{"fragmentos":[{...payload,"puntaje":float}],"modelo":str,"coleccion":str,"version_corpus":int}`
(solo vigentes). `GET /salud`. Todas, salvo `/salud`, exigen la cabecera `X-Token-Interno`.

### Almacén (`kerna_nucleo.almacen`)

Interfaz `Almacen` con dos implementaciones: `AlmacenMemoria` (pruebas y desarrollo) y `AlmacenTablas` (Azure Table
Storage, `azure-data-tables`, identidad administrada o cadena de conexión). Entidades: `solicitud` (clave:
cliente + ref_opaca), `sugerencia_articulo`, `valoracion`, `clasificacion`. No guarda el texto del caso ni la
observación en claro más allá de lo necesario: el texto anonimizado se descarta al terminar la solicitud.

### Variables del núcleo

`KERNA_CLIENTES` (JSON `{client_id: {"secreto_sha256": str, "cliente": str}}`), `KERNA_JWT_SECRETO`,
`GEMINI_API_KEY`, `VOYAGE_API_KEY`, `QDRANT_URL`, `QDRANT_API_KEY`, `KERNA_COLECCION` (`normativa_cl`),
`KERNA_EMBEDDING` (`voyage-4-large`), `KERNA_DIMS` (1024), `KERNA_LOCAL_URL`, `KERNA_LOCAL_TOKEN`, `KERNA_TOP_K`,
`KERNA_UMBRAL_SIMILITUD`, `KERNA_CADENA` (JSON opcional), `KERNA_ALMACEN` (`memoria` \| `tablas`),
`KERNA_TABLAS_URL` o `KERNA_TABLAS_CONEXION`, `APPLICATIONINSIGHTS_CONNECTION_STRING`.

## Anonimizador (`kerna_comun.anonimizador`)

`anonimizar(texto: str) -> Resultado` con `texto` (anonimizado) y `conteos` (por tipo, sin los valores). Reemplaza
por marcadores estables (`[PERSONA_1]`, `[RUT_1]`, `[CORREO_1]`, `[TELEFONO_1]`, `[DIRECCION_1]`, `[PATENTE_1]`,
`[CUENTA_1]`, `[URL_1]`): RUT chilenos con y sin puntos, correos, teléfonos chilenos e internacionales, URL, nombres
propios de personas (heurística por contexto: tratamientos, cargos, "don", "señor", pares Nombre Apellido),
direcciones, patentes y números de cuenta. No toca nombres de leyes, artículos, instituciones públicas ni montos.
Es idempotente (aplicarlo dos veces no cambia el resultado) y determinista. Solo reglas: sin modelos.

## Telemetría (`kerna_comun.telemetria`)

- `configurar(servicio: str)`: activa OpenTelemetry con `azure-monitor-opentelemetry` si existe
  `APPLICATIONINSIGHTS_CONNECTION_STRING`; si no, no hace nada.
- `evento(nombre: str, **atributos)`, `etapa(nombre: str, **atributos)` (administrador de contexto que mide la
  duración) y `contador(nombre: str, valor=1, **atributos)`.
- **Privacidad**: solo salen los atributos de `ATRIBUTOS_PERMITIDOS`; cualquier otro se descarta, y los valores de
  texto de más de 64 caracteres también. Nunca texto de denuncias, notas, consultas, prompts ni respuestas. Lista:
  `id_solicitud`, `ref_opaca`, `cliente`, `etapa`, `modo`, `recuperacion`, `proveedor`, `modelo`, `embedding`,
  `coleccion`, `version_corpus`, `estado`, `motivo`, `codigo`, `intento`, `duracion_ms`, `tokens_entrada`,
  `tokens_salida`, `articulos`, `citas_rechazadas`, `json_valido`, `contingencia`, `resultado`, `casos`,
  `fragmentos`, `tipo`.

## Conector Veridy (`kerna_conector`)

- **Sesión en Veridy** (`veridy.py`): `POST /api/auth/type`, derivación argon2id de la contraseña, prueba de trabajo
  (`POST /api/auth/token`, cabecera `x-token`), `POST /api/auth/authentication`, cabecera `X-Session`,
  `DELETE /api/auth/session` al terminar. Lista `GET /api/recipient/rtips`, caso `GET /api/recipient/rtips/<id>`,
  nota `POST /api/recipient/rtips/<id>/comments {"content","visibility":"internal"}`.
- **Ciclo de reconciliación** (cada `CONECTOR_INTERVALO_S`, 30 s por defecto), por cada pasada:
  1. lista los casos; para cada caso sin correspondencia: genera `ref_opaca`, lee el caso, descarta la identidad del
     denunciante, arma el texto (respuestas del cuestionario), lo anonimiza, lo envía al núcleo y publica
     `kerna_estado: en_proceso`;
  2. para cada caso `pendiente`: consulta la sugerencia; cuando deja de estar pendiente publica **una sola**
     `kerna_sugerencia` y guarda el identificador de la nota;
  3. para cada caso con sugerencia: lee los comentarios, valida `kerna_feedback` y `kerna_clasificacion` (reglas de
     arriba), anonimiza la observación y los envía al núcleo una sola vez (`objeto_procesado`);
  4. registra la pasada (`ejecucion_reconciliacion`).
- **Estado** (`estado.py`): tablas `correspondencia_caso`, `objeto_procesado`, `ejecucion_reconciliacion` (y
  `aviso_recibido`, reservada). Interfaz `Estado` con `EstadoSqlite` (pruebas y desarrollo) y `EstadoPostgres`.
  Es el único lugar donde conviven el identificador real del caso y la referencia opaca.
- Nunca escribe en disco ni en registros el texto del caso, ni lo envía a la telemetría. Una falla en un caso no
  detiene la pasada.
- Variables: `VERIDY_URL`, `VERIDY_USUARIO`, `VERIDY_PASSWORD`, `VERIDY_TID` (0), `KERNA_API_URL`,
  `KERNA_CLIENT_ID`, `KERNA_CLIENT_SECRET`, `KERNA_ID_EMPRESA`, `CONECTOR_INTERVALO_S`, `CONECTOR_ESTADO`
  (`sqlite:///ruta` o URI de PostgreSQL), `APPLICATIONINSIGHTS_CONNECTION_STRING`.

## Pruebas

- Capas por carpeta: `kerna/pruebas/unitarias` (sin red; proveedores simulados), `integracion` (servicios reales),
  `e2e` (Playwright contra Veridy), `carga` (locust).
- Cada prueba lleva el ID del informe que verifica: `@pytest.mark.pr("PR-25")`, y `rf`, `rnf`, `cu` cuando aplica.
- Datos sintéticos versionados en `kerna/pruebas/datos/`. Ningún texto real. Semillas fijas.
- Un comando: `scripts/probar.sh [unitarias|integracion|e2e|carga|todo]`, que deja `reportes/pruebas/<fecha>-<commit>/`
  con `junit.xml` y `resumen.json`, e imprime un resumen de pocas líneas.
