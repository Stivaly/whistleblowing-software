# Eliminaciones pendientes de aprobación

Claude no elimina nada en este proyecto. Lo que habría eliminado se movió a `.papelera/` (ruta original conservada).
Revisa cada fila y, si apruebas, bórralo tú manualmente (`rm -r .papelera/...`). Para restaurar: `mv` de vuelta a la ruta original.

| Fecha | Ruta original | Copia en papelera | Motivo | Estado |
|-------|---------------|-------------------|--------|--------|
| 2026-10-12 | `infra/scripts/veridy_bd.sh` | `.papelera/2026-10-12/infra/scripts/veridy_bd.sh` | Reemplazado por el vigía dentro de Azure (`infra/veridy/contenedor/vigia.py`) y `infra/veridy/veridy.sh`; Veridy ya no corre en el host. El cron nunca se instaló. | Pendiente de decisión |
