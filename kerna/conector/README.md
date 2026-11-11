# Conector Veridy

Proceso que corre junto a Veridy. Con una cuenta de servicio (rol destinatario) lee los casos, arma solo el relato
(respuestas de texto del cuestionario con la etiqueta de cada pregunta), lo anonimiza, lo envía al núcleo de Kerna con
una referencia opaca y publica la sugerencia como nota interna del caso. También reenvía al núcleo el feedback y la
clasificación que escriben los auditores. Contrato: `kerna/docs/contratos.md` (secciones "Objetos de las notas",
"API del núcleo" y "Conector Veridy").

## Módulos

`config.py` variables de entorno · `veridy.py` cliente de Veridy (login argon2id con prueba de trabajo, sesión de 120 s
renovada antes de vencer y ante 401/412) · `lector_casos.py` relato y notas propias · `lector_decisiones.py` feedback y
clasificación válidos · `nucleo.py` cliente del núcleo (token OAuth en caché, reintentos 1, 2, 4 s) · `publicador.py`
notas `kerna_sugerencia` y `kerna_estado` · `estado.py` `EstadoSqlite` y `EstadoPostgres` · `reconciliacion.py` una
pasada · `__main__.py` bucle.

## Ejecución

```bash
export PYTHONPATH=kerna/comun:kerna/conector
python -m kerna_conector              # bucle cada CONECTOR_INTERVALO_S; termina limpio con SIGTERM
python -m kerna_conector --una-pasada # una pasada; salida 0 ok, 1 errores o núcleo caído, 2 configuración, 3 omitida
```

Imagen: `docker build -f conector/Dockerfile kerna/` (contexto = carpeta `kerna/`; usuario sin privilegios).

Despliegue: contenedor `conector` del grupo de Veridy en Azure (`infra/veridy/terraform/conector.tf`, alta en
`infra/veridy/README.md`). El grupo ejecuta `entrada.py`, que lee de Key Vault `veridy-kerna-conector-password`,
`kerna-client-id`, `kerna-client-secret` y `conector-pg-password` con la identidad administrada, arma
`CONECTOR_ESTADO` (base `kerna_conector`, rol `kerna_conector`, TLS verificado), hace que `VERIDY_RESOLVER_LOCAL`
(nombre público de Veridy) resuelva a 127.0.0.1 y ejecuta el conector. `VERIDY_URL` es `https://<nombre público>:8443`.
Todas las peticiones a Veridy llevan `?kerna_conector=1` para que el vigía de inactividad no las cuente como uso.

Variables: `VERIDY_URL`, `VERIDY_USUARIO`, `VERIDY_PASSWORD`, `VERIDY_TID` (0), `KERNA_API_URL`, `KERNA_CLIENT_ID`,
`KERNA_CLIENT_SECRET`, `KERNA_ID_EMPRESA` (`veridy`), `CONECTOR_INTERVALO_S` (30), `CONECTOR_ESTADO`
(`sqlite:///ruta` o URI de PostgreSQL; por defecto `sqlite:///conector.db`), `APPLICATIONINSIGHTS_CONNECTION_STRING`.

## Comportamiento

- Cada caso se envía una vez (la `ref_opaca` se fija al verlo por primera vez). Una sola `kerna_sugerencia` por caso:
  antes de publicar se revisa si la cuenta ya dejó una y se adopta su id. A lo más una `kerna_estado` por estado.
  Feedback y clasificación se envían una vez (caso + id de nota), en orden de creación.
- Los casos anteriores a la instalación se procesan igual, del más antiguo al más nuevo.
- Caso ilegible o sin acceso (403/404, `accessible: false`): se registra como error y se reintenta con espera creciente
  (30 s, 60 s... tope 1 h) sin detener la pasada.
- Núcleo sin respuesta tras los reintentos: se publica una vez `nucleo_no_disponible` en cada caso afectado, no se
  insiste en esa pasada y se continúa en las siguientes.
- Un cerrojo en el estado evita dos pasadas simultáneas (también entre procesos).
- Privacidad: el texto del caso solo existe en memoria durante la pasada. El id real del caso solo está en el estado;
  al núcleo solo va la `ref_opaca`. Las notas se publican siempre con `visibility: "internal"`.

## Pruebas

```bash
cd kerna && /usr/bin/python3 -m pytest pruebas/unitarias -q -k conector      # sin red
VERIDY_URL=... VERIDY_USUARIO=... VERIDY_PASSWORD=... /usr/bin/python3 -m pytest pruebas/integracion/test_conector_veridy_real.py
```

La de integración inicia sesión, lista, lee un caso y cierra; no publica nada. Requiere Veridy encendido.

## Runbook

- Alta de la cuenta de servicio: crear en Veridy un usuario destinatario `kerna-conector`, sin notificaciones por correo,
  sin permisos de borrar, transferir, otorgar acceso, redactar ni enmascarar; asignarlo al canal Denuncia; fijar
  contraseña temporal, entrar una vez para definir la definitiva (crea su clave de cifrado) y guardarla en el Key Vault
  como `veridy-kerna-conector-password`. El doble factor no debe ser obligatorio. Para casos previos, un destinatario con
  `can_grant_access_to_reports` debe otorgarle acceso.
- Caducidad: la contraseña vence a los 365 días del cambio (`password_change_period`). Antes, cambiarla entrando con la
  cuenta y actualizar el secreto; si venció, el login responde error y el conector sale con errores en cada pasada.
- Núcleo sin respuesta: los casos reciben `nucleo_no_disponible` y se reintentan solos en cada pasada. Revisar
  `GET {KERNA_API_URL}/salud` y las credenciales `KERNA_CLIENT_*`; al volver, el conector continúa sin intervención.
- Casos con error persistente: mirar `correspondencia_caso.ultimo_error` (`sin_acceso`, `http_403`, `ilegible_*`,
  `sin_texto`); la causa habitual es que la cuenta no tiene acceso al caso.
