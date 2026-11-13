# Eliminaciones pendientes de aprobación

Claude no elimina nada en este proyecto. Lo que habría eliminado se movió a `.papelera/` (ruta original conservada).
Revisa cada fila y, si apruebas, bórralo tú manualmente (`rm -r .papelera/...`). Para restaurar: `mv` de vuelta a la ruta original.

| Fecha | Ruta original | Copia en papelera | Motivo | Estado |
|-------|---------------|-------------------|--------|--------|
| 2026-10-12 | `infra/scripts/veridy_bd.sh` | `.papelera/2026-10-12/infra/scripts/veridy_bd.sh` | Reemplazado por el vigía dentro de Azure (`infra/veridy/contenedor/vigia.py`) y `infra/veridy/veridy.sh`; Veridy ya no corre en el host. El cron nunca se instaló. | Pendiente de decisión |
| 2026-10-18 | Azure: entorno de Container Apps `cae-kerna-dev` (modo Express, vacío) | — (recurso de Azure, sin copia) | Express no admite jobs; se recreó con el mismo nombre en modo `WorkloadProfiles`. Eliminado con autorización explícita de la usuaria. | Hecho (autorizado) |
| 2026-10-18 | Azure: contenido de la base `veridy` (PostgreSQL de Veridy) | `~/backups/veridy-azure-2026-10-18.dump` (pg_dump completo) | Reemplazado por la instalación local (personalización y pruebas) con `infra/veridy/migrar_sqlite.py`, a pedido de la usuaria. Restaurar: `pg_restore --clean`. | Hecho (autorizado) |
| 2026-11-10 | `kerna/evaluacion/datos/denuncias_veridy.json` (versión de un intento fallido) | `.papelera/2026-11-10/kerna/evaluacion/datos/denuncias_veridy_intento_fallido.json` | Registro local de un primer intento del generador de denuncias que no llegó a enviar nada a Veridy; lo sustituye el registro actual. | Pendiente de decisión |

## 2026-11-11 — Limpieza de Docker del host (autorizada por la usuaria)
- La usuaria pidió eliminar todo lo histórico de Docker. El clasificador de permisos bloquea a Claude; queda el script
  `infra/limpiar_docker.sh` para que lo ejecute ella (contenedores de prueba detenidos, imágenes viejas, caché de build).
  No toca imágenes desplegadas, contenedores en ejecución ni volúmenes.

## 2026-11-11 — Identidad v3 "Núcleo" en el bloque de Kerna
- No se movió ningún archivo. Se sustituyó la sección `.kerna-*` de `client/app/css/main.css` por `client/app/css/components/kerna.css`.
  Copia de la versión anterior de `main.css` (con la sección vieja) en `.papelera/2026-11-11/client/app/css/main.css`. Motivo: estilos del bloque Kerna acotados a su propio archivo.
- Las siluetas SVG de `kerna-glifo.component.ts` y el ícono "artículo marcado" de `kerna-icono.component.ts` fueron reemplazados por las escenas/logo de Núcleo (quedan en el historial de git).

- 2026-11-11 | client/app/css/components/kerna.css (versión oscura) | .papelera/2026-11-11/client/app/css/components/kerna.css | reemplazada por el tema claro de Núcleo (sin fondos de color); copia movida/guardada para que la usuaria decida.

## 2026-11-11 — Denuncias de prueba antiguas en Veridy (autorizado por la usuaria)
- Eliminadas 62 denuncias de prueba (números 11–74 salvo 25 y 26) cargadas con resumen corto o con rótulos
  "Título/Relato" y marca de prueba. Ids en `kerna/evaluacion/datos/denuncias_veridy.json` y
  `denuncias_veridy_texto_completo.json`. Respaldo previo completo: `~/backups/veridy-azure-2026-11-11.dump`
  (restaurar con `pg_restore --clean`). Quedan 38: las cargadas solo con el relato y las 10, 25 y 26 (origen sin registro).
- 2026-11-11: versión clara de `client/app/css/components/kerna.css` guardada en `.papelera/2026-11-11-claro/client/app/css/components/kerna.css`; la usuaria prefirió volver al fondo oscuro. Pendiente de decisión.
- 2026-11-11: `kerna/diseno/logo/kerna-{logo-horizontal,simbolo}-{claro,oscuro}.svg` (logo anterior) movidos a `.papelera/2026-11-11/kerna/diseno/logo/`; reemplazados por `simbolo.svg`, `simbolo-pequeno.svg` y `logo-horizontal-{claro,oscuro}.svg` (símbolo guilloché aprobado). Además `capturas/estados.png` (captura de viewport redundante). Pendiente de decisión.
| 2026-11-12 | kerna/front/app/datos/proximos_pasos.json | .papelera/2026-11-12/kerna/front/app/datos/proximos_pasos.json | Archivo propio recién creado; la usuaria quitó la sección Próximos pasos del informe |
| 2026-11-11 | kerna/front/app/datos/evaluacion.json | .papelera/2026-11-11/kerna/front/app/datos/evaluacion.json | El front lee la calidad en vivo de la tabla `evaluaciones`; ya no hay instantánea |
| 2026-11-11 | kerna/front/generar_datos_informe.py | .papelera/2026-11-11/kerna/front/generar_datos_informe.py | Generaba evaluacion.json en cada despliegue; reemplazado por kerna/evaluacion/tabla_evaluaciones.py |

- 2026-11-12 · copia previa `kerna/front/diseno-v2/maqueta.html` -> `.papelera/2026-11-12/kerna/front/diseno-v2/maqueta.html` (versión anterior a la revisión de diseño; el original se editó en su lugar). Capturas intermedias `capturas/ant-*.png` -> `.papelera/2026-11-12/kerna/front/diseno-v2/capturas/` (estado previo a la revisión).

- 2026-11-12 · copia previa `kerna/front/diseno-v2/maqueta.html` -> `.papelera/2026-11-12/kerna/front/diseno-v2/maqueta-previa-v3.html` (versión anterior al rediseño v3; el original se reemplaza en su lugar).
- 2026-11-12 · `kerna/pipeline_bcn/salida/fuentes/30210-karin.json` → `.papelera/2026-11-12/kerna/pipeline_bcn/salida/fuentes/30210-karin.json` · idNorma 30210 es el texto de 2005 de la Ley 18.834 sin cambios Karin; se usó el DFL 29 (236392).

## 2026-11-12 · Rediseño del front real (maqueta aprobada)
| Fecha | Ruta original | Ruta en papelera | Motivo |
|---|---|---|---|
| 2026-11-12 | kerna/front/app/estaticos/kerna.css | .papelera/2026-11-12/kerna/front/app/estaticos/kerna.css | Reemplazado por los estilos de la maqueta aprobada (copia de la versión anterior) |
| 2026-11-12 | kerna/front/app/plantillas/{acceso,base,informe,negocio,panel,portada,reintentar}.html | .papelera/2026-11-12/kerna/front/app/plantillas/ | Reescritas con el diseño nuevo (copias de las versiones antiguas, diseño monoespaciado) |
| 2026-11-12 | kerna/front/app/plantillas/_simbolo.html | .papelera/2026-11-12/kerna/front/app/plantillas/_simbolo.html | Símbolo estático antiguo; el logo vivo se dibuja ahora con kerna.js |

| 2026-11-12 | kerna/front/app/estaticos/echarts.min.js | .papelera/2026-11-12/kerna/front/app/estaticos/echarts.min.js | Reemplazado por echarts.custom.min.js (build propio, 617 KB en vez de 1,0 MB; solo los gráficos que usa el front) |

- 2026-11-13 · kerna/front/app/estaticos/img/bg-orbitas.webp (versión regenerada por rasterizar_decoracion.sh, sin commitear) → .papelera/2026-11-13/kerna/front/app/estaticos/img/bg-orbitas.regenerado.webp · motivo: podía reintroducir el satélite quitado a mano de la portada; se restauró la versión commiteada.
- 2026-11-13 · pendientes/orquestador-2026-11-13.md (versión 1, ya cumplida) → .papelera/2026-11-13/pendientes/orquestador-2026-11-13.v1.md · motivo: la usuaria pidió dejar en la página solo lo vigente; se reescribió.
- 2026-11-13 · caso de Veridy (1, creado 2026-10-19, `sin_acceso` para la cuenta de servicio, 136 intentos) → no hay ruta de archivo: borrado en la base por `kerna/operaciones/borrar_casos_invalidos.sh --aplicar` · motivo: autorizado por la usuaria (A6); no se podía procesar. Los datos eran una denuncia de prueba sin comentarios ni archivos.
