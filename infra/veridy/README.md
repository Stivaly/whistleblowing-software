# Veridy en Azure (Terraform propio)

Veridy corre en **Azure Container Instances** con su base en **PostgreSQL Flexible Server**, todo en
`rg-veridy-dev` (Chile Central). Es independiente de Kerna (`infra/terraform`): otro estado, otro grupo de recursos,
otro Key Vault. Solo comparte el Container Registry de Kerna (Azure for Students incluye uno Standard sin costo).

## Uso diario

```bash
infra/veridy/veridy.sh encender      # PostgreSQL y luego Veridy; al final muestra el link (hasta 3 min)
infra/veridy/veridy.sh estado
infra/veridy/veridy.sh apagar
infra/veridy/veridy.sh mantener 3d   # no apagar por inactividad durante 3 días (12h, 90m...); "mantener no" lo revierte
infra/veridy/veridy.sh logs          # registros de Veridy (también: vigia, puertos)
```

- **Encender es manual.** Apagar es automático: el vigía apaga Veridy y PostgreSQL tras 60 minutos sin uso
  (`inactividad_min`). "Uso" = una llamada exitosa a `/api/` que no sea `/api/health`; los bots que recorren IPs
  públicas no ejecutan la aplicación y no la mantienen encendida.
- HTTPS con certificado de Let's Encrypt (administración > red > HTTPS), guardado en la base. Veridy lo renueva
  solo si está encendido en los días previos al vencimiento; si vence apagado, "Reset" y volver a pedirlo.
- Inicio de sesión de administración y destinatarios: `<link>/#/login`.
- Azure vuelve a encender solo un PostgreSQL detenido 7 días. Si nadie usa Veridy, quedará encendido sin Veridy:
  `veridy.sh apagar` lo corrige.

## Qué crea

| Recurso | Para qué | Costo aprox. |
|---|---|---|
| Grupo de contenedores `aci-veridy-dev` | Veridy (1 vCPU, 1,5 GB) + `puertos` (443→8443, 80→8080) + `vigia` | ~US$0,08/hora encendido; nada apagado |
| PostgreSQL Flexible Server B1ms | Base de Veridy (32 GB) | ~US$0,024/hora encendido + almacenamiento (~US$4/mes) |
| Storage + Azure Files | `adjuntos` (10 GB), `archivos` (1 GB), `control` (1 GB) | < US$1/mes |
| Key Vault `kv-veridy-dev-*` | `veridy-db-admin-password`, `veridy-db-app-password` | centavos |
| Identidad `id-veridy-dev` + rol propio | Leer sus secretos, bajar la imagen, apagarse y apagar su PostgreSQL, autorizar su IP | gratis |

Cómo arranca el grupo:

1. **veridy**: antes de iniciar Veridy corre `contenedor/arranque.py`, que lee la contraseña de `veridy_app` de
   Key Vault y la deja en un `.pgpass` dentro del contenedor, y autoriza la IP de salida del grupo en el firewall de
   PostgreSQL (regla `aci-veridy`, cambia en cada encendido). Así la contraseña no queda en el estado de Terraform
   ni en variables de entorno. Imagen de `docker/Dockerfile`; adjuntos y archivos en Azure Files; los **logs en
   memoria**, se pierden al apagar (no se conservan IPs).
3. **puertos**: `socat` reenvía 443 y 80 a Veridy sin abrir el TLS (Veridy maneja su certificado).
4. **vigia** (`contenedor/vigia.py`): apagado por inactividad.

Lo único sensible que queda en el estado de Terraform es la clave de la cuenta de Storage: Container Instances la
exige para montar Azure Files. El estado vive en Azure Storage con acceso solo por Entra ID.

## Instalación (una vez)

Desde `infra/veridy/terraform`. Requiere lo de `infra/terraform/README.md`, pasos 0 a 4 (CLI, sesión, estado remoto).

### 1. Estado y variables

```bash
cp backend.hcl.example backend.hcl            # misma cuenta de Storage que Kerna, clave veridy-dev.tfstate
cp terraform.tfvars.example terraform.tfvars  # completar subscription_id, acr_nombre, postgres_nombre, IP de administración
terraform init -backend-config=backend.hcl
```

### 2. Primera aplicación (sin contenedor)

```bash
terraform plan -out=fase1.tfplan   # con crear_contenedor = false
terraform apply fase1.tfplan
```

### 3. Contraseñas en el Key Vault de Veridy

```bash
KV=$(terraform output -raw key_vault_nombre)
az keyvault secret set --vault-name $KV --name veridy-db-admin-password --value "$(openssl rand -base64 30 | tr -d '/+=')" -o none
az keyvault secret set --vault-name $KV --name veridy-db-app-password   --value "$(openssl rand -base64 30 | tr -d '/+=')" -o none
```

(En dev se copiaron desde el Key Vault de Kerna, donde se crearon primero.)

### 4. PostgreSQL

En dev el servidor ya existía (creado desde `infra/terraform`): se movió a `rg-veridy-dev` con `az resource move`, se
quitó del estado de Kerna (`terraform state rm`) y se importó aquí (`terraform import`). En una instalación nueva lo
crea el `apply` con `TF_VAR_postgres_admin_password` leída de Key Vault:

```bash
export TF_VAR_postgres_admin_password="$(az keyvault secret show --vault-name $KV --name veridy-db-admin-password --query value -o tsv)"
terraform plan -out=pg.tfplan && terraform apply pg.tfplan
unset TF_VAR_postgres_admin_password
```

Roles de la base (`infra/sql/veridy_roles.sql`). La contraseña va en un `.pgpass` temporal, no en el entorno ni en
la línea de comandos:

```bash
H=$(terraform output -raw postgres_servidor); umask 077; P=$(mktemp)
printf '%s:5432:*:veridyadmin:%s\n' "$H" "$(az keyvault secret show --vault-name $KV --name veridy-db-admin-password --query value -o tsv)" > $P
{ printf "\\\\set app_password '%s'\n" "$(az keyvault secret show --vault-name $KV --name veridy-db-app-password --query value -o tsv)"; cat ../../sql/veridy_roles.sql; } \
  | docker run -i --rm --user "$(id -u):$(id -g)" -e PGPASSFILE=/pgpass -v $P:/pgpass:ro postgres:15 \
      psql "host=$H dbname=veridy user=veridyadmin sslmode=require" -f -
: > $P
```

Debe terminar mostrando `veridy_app` con `rolsuper = f`.

**Base vacía:** el contenedor corre solo con `veridy_app`, que no puede crear tablas. En una base nueva, el esquema se
crea una vez con un arranque de Veridy que tenga `GLOBALEAKS_DB_ADMIN_URI` (ver `docker/README-postgres.md`). En dev
ya está creado (34 tablas, versión 68).

### 5. Imágenes

```bash
infra/veridy/subir_imagen.sh --tag v1      # desde la raíz del repo: construye docker/Dockerfile y sube veridy:v1
```

La primera vez también importa `socat` al registro (lo hace el mismo script).

### 6. Segunda aplicación: el contenedor

```bash
sed -i 's/crear_contenedor *= *false/crear_contenedor = true/' terraform.tfvars
terraform plan -out=fase2.tfplan && terraform apply fase2.tfplan
terraform output url
```

## Versiones nuevas de Veridy

```bash
infra/veridy/subir_imagen.sh --tag v2
sed -i 's/imagen_tag *= *".*"/imagen_tag = "v2"/' infra/veridy/terraform/terraform.tfvars
terraform -chdir=infra/veridy/terraform plan -out=v2.tfplan && terraform -chdir=infra/veridy/terraform apply v2.tfplan
```

Cambiar la imagen recrea el grupo de contenedores. Adjuntos y archivos (Azure Files) y la base no se tocan.
