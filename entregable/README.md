# Entregable: Veridy y Kerna en un computador

Paquete para que una persona sin conocimientos técnicos pruebe Veridy y Kerna en su computador (Windows o Linux),
desde cualquier red que permita navegar por HTTPS.

## Qué corre dónde

| Parte | Dónde | Puerto en el computador |
|---|---|---|
| Página de inicio (botones, cuentas de prueba, manuales) | contenedor `inicio` | `localhost:8400` |
| Veridy (con datos iniciales: canal Denuncia, cuestionario, cuenta del auditor y del conector) | contenedor `veridy` | `localhost:8401` (http, sin certificado) |
| Panel de Kerna (`kerna/front`) | contenedor `panel` | `localhost:8402` |
| Conector Veridy → Kerna | contenedor `conector` | sin puerto |
| Núcleo, modelos, índices, tablas y Log Analytics | Azure (`rg-kerna-dev`) | se llega por HTTPS 443 |
| Pasarela de identidad (`kerna/pasarela`, `infra/terraform/pasarela.tf`) | Azure, Container App `ca-kerna-dev-pasarela` | se llega por HTTPS 443 |

Los contenedores locales no tienen identidad de Azure (la suscripción no permite registrar aplicaciones). La pasarela
les entrega tokens de su identidad administrada con el protocolo de identidad de App Service: el panel y el conector
reciben `IDENTITY_ENDPOINT` (la pasarela) e `IDENTITY_HEADER` (su clave, secreto `pasarela-clave` del Key Vault de
Kerna) y `DefaultAzureCredential` funciona sin cambios. Solo entrega tokens para Log Analytics, Storage y Azure
Resource Manager; los roles de esa identidad son los del panel de Azure, sin Key Vault. Rotar la clave:
`terraform apply -replace=random_password.pasarela` y volver a construir el paquete.

El conector local usa el cliente `veridy-local` del núcleo (secreto `veridy-local-client-secret` del Key Vault de
Kerna), así sus casos no se mezclan con los de `veridy-dev`. Veridy acepta http en `localhost`, `127.0.0.1` y
`veridy` solo con `VERIDY_HTTP_LOCAL=1` (`backend/globaleaks/rest/api.py`), que solo fija esta imagen.

## Cuentas de prueba

| Para | Usuario | Dónde está la contraseña |
|---|---|---|
| Auditor de Veridy | `auditor.prueba` | `dist/secretos.env` (`VERIDY_AUDITOR_CLAVE`) |
| Panel de Kerna (rol Evaluación: ve todo, no cambia nada) | `evaluador.prueba` | `dist/secretos.env` (`KERNA_PANEL_CLAVE`) |

`dist/secretos.env` (ignorado por git) tiene además la clave de la cuenta `kerna-conector` de Veridy, el cliente
`veridy-local`, la pasarela, la cuenta de la Demo y la firma de sesiones del panel local. Los manuales en PDF y las
capturas llevan las contraseñas de prueba: tampoco van al repositorio.

## Construir el paquete

```bash
entregable/construir.sh            # dist/veridy-kerna-local/ y dist/veridy-kerna-local.zip
```

Toma las imágenes desplegadas (`imagen_tag` y `conector_tag` de `infra/veridy/terraform/terraform.tfvars`), arma los
datos iniciales de Veridy desde el volumen `docker_globaleaks` (personalización de Veridy; se lee sin modificarlo,
sin denuncias), construye `veridy-local`, `kerna-conector-local` y `kerna-panel-local`, y las guarda en
`imagenes.tar.gz` para instalar sin descargar nada.

## Manuales

`manuales/manual-de-usuario.html` y `manuales/manual-de-instalacion.html` → `manuales/generar.sh` (PDF). Las capturas
se toman de la instalación local en marcha con `herramientas/pw.sh`:

```bash
entregable/herramientas/pw.sh entregable/herramientas/capturar_inicio.py
entregable/herramientas/pw.sh entregable/herramientas/capturar_denuncia.py acoso      # envía una denuncia real
entregable/herramientas/pw.sh entregable/herramientas/capturar_auditor.py <id del caso con sugerencia>
OUT=entregable/manuales/capturas/crudas entregable/herramientas/pw.sh entregable/herramientas/capturar_panel.py
```

`capturar_auditor.py` muestra los estados que no se pueden provocar a voluntad (modo alternativo, Kerna no disponible…)
cambiando en el navegador las notas de Kerna del caso; el resto de la pantalla es real. Al final valora y clasifica de
verdad. Después de capturar, volver a construir el paquete (los PDF van dentro de la página de inicio).
