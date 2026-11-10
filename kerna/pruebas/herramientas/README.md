# Herramientas de pruebas

## crear_denuncias.py

Crea denuncias de prueba en Veridy como un denunciante, por la API pública y sin navegador, a partir de `evaluacion/datos/denuncias_publicas.json`.

Uso (siempre `/usr/bin/python3`, desde `kerna/`):

```
export VERIDY_URL=https://<host-de-veridy>
/usr/bin/python3 pruebas/herramientas/crear_denuncias.py --lote 10
/usr/bin/python3 pruebas/herramientas/crear_denuncias.py --casos DEN-0001 DEN-0002
/usr/bin/python3 pruebas/herramientas/crear_denuncias.py --lote 10 --dry-run   # arma y valida, no envía
/usr/bin/python3 pruebas/herramientas/crear_denuncias.py --verificar           # inicia sesión con cada recibo
```

- `--lote N` elige N casos variados por `ley_principal` (turnos rotativos, semilla fija).
- Relato: primera línea `[PRUEBA SINTÉTICA DEN-XXXX]`, luego título, resumen parafraseado y submateria. Nunca usa `texto_original`.
- Los demás campos obligatorios del Cuestionario Base llevan valores neutros ("Prueba sintética"); sin evidencia y sin compartir datos.
- Registro idempotente en `evaluacion/datos/denuncias_veridy.json` (ignorado por git, permisos 600): caso → id de denuncia, recibo, fecha UTC. Un caso registrado no se vuelve a crear. La herramienta no borra nada en Veridy.
- Veridy limita los envíos por hora y por IP: al alcanzar el límite la herramienta se detiene (código de salida 3); repetir el mismo comando más tarde continúa con los casos que faltan.
- La salida muestra solo conteos e identificadores, nunca recibos ni textos.

Funciones reutilizables:

- `iniciar_sesion_denunciante(url, recibo)` devuelve el id de sesión; `cerrar_sesion(url, sesion)`.
- `leer_denuncia_como_denunciante(url, recibo)` devuelve `{"id", "progresivo", "comentarios", "denuncia"}`; `comentarios` contiene solo lo que el denunciante puede ver (las notas internas no aparecen).

Formato del envío (réplica del cliente Angular):

1. `GET /api/public` entrega el contexto y el cuestionario.
2. `POST /api/auth/token` + prueba de trabajo, cabecera `x-token: <id>:<c>`, y `POST /api/auth/receiptauth {"receipt": ""}` abre la sesión de envío (`X-Session`).
3. El recibo son 16 dígitos aleatorios. Si `POST /api/auth/type {"username": ""}` responde `key`, se envía `base64(argon2id(recibo, sal, 16 pasadas, 128 MiB))`.
4. `POST /api/whistleblower/submission` con `{context_id, receivers, identity_provided, answers, score, receipt}`.
5. `answers` es `{id_campo: [{"value": ...}]}`: texto en inputbox/textarea, id de opción en selectbox, `"<ms inicio>:<ms fin>"` en daterange; los campos no activados por disparadores van como `[{}]`.

Pruebas unitarias (sin red): `cd kerna && /usr/bin/python3 -m pytest pruebas/unitarias/test_crear_denuncias.py -q`. Usan `pruebas/datos/cuestionario_base_ejemplo.json`.
