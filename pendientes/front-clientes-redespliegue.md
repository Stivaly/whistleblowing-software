# Panel de Kerna: redesplegar la sección «Administrar clientes»

Estado al 2026-11-18:
- Núcleo desplegado (`kerna-nucleo:26ba1e6be`): lee la tabla `clientes` cada 20 s (altas, bajas) además de `KERNA_CLIENTES`.
- Permisos de Terraform aplicados (`front_clientes_admin`: 6 tablas).
- Código del panel commiteado (26ba1e6be y el fix del empaquetado). **El panel desplegado es el primero, que no arranca**: `desplegar.sh` no copiaba `clientes_esquema.py` (corregido, con prueba).
- El plan F1 del panel (`app-kerna-dev-front-g6mzy`) quedó en `QuotaExceeded` (60 min de CPU al día; el arranque fallido en bucle la agotó). Azure rechaza el despliegue con 403 hasta que se renueva la cuota (00:00 UTC, 21:00 hora de Chile).

Para terminar, después de la renovación:
1. `kerna/front/desplegar.sh --ref HEAD`
2. `kerna/operaciones/despertar_front.sh` y comprobar `/salud` = 200.
3. Prueba en pantalla (`/tmp/.../scratchpad/clientes_e2e.py` si sigue; si no, repetir: agregar un cliente, ver que el núcleo le da token, darlo de baja, ver que ya no lo da; abrir «Borrar por ley» solo para mirar el diálogo).
4. El cliente de verificación `prueba-panel-clientes` quedará en «Dados de baja»; borrarlo o dejarlo lo decide la usuaria (no se ejecuta el borrado por ley sobre datos reales sin su orden).
