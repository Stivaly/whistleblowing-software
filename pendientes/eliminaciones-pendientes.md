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
