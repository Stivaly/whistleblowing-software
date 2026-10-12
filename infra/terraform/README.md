# Infraestructura Kerna AI en Azure (Terraform)

Qué crea (todo en `eastus2`, grupo `rg-kerna-dev`):

| Recurso | Para qué | Costo aprox. (Azure for Students) |
|---|---|---|
| Log Analytics | logs de los jobs (tope 0,5 GB/día) | centavos |
| Container Registry Basic | imagen `kerna-pipeline` | ~US$5/mes |
| Key Vault | `mongodb-uri`, `qdrant-url`, `qdrant-api-key`, `gemini-api-key` | centavos |
| Identidad administrada | el job lee Key Vault y baja la imagen sin claves | gratis |
| Container Apps Environment + 3 jobs | diario, semanal y 1 de diciembre | dentro de la cuota gratuita mensual |
| PostgreSQL Flexible Server B1ms (opcional, `crear_postgres`) | base operativa de Veridy | verificar cobertura gratuita antes del apply (paso 11) |

Fuera de Terraform (a mano): MongoDB Atlas (ya existe), Qdrant Cloud y la API key de Google Gemini (AI Studio).

Los **valores** de los secretos nunca pasan por Terraform ni quedan en su estado: se cargan con `az keyvault secret set` (paso 6).

Todos los comandos se corren desde la raíz del repo salvo que se indique.

## 0. Instalar Azure CLI y Terraform (una vez)

```bash
# Azure CLI (script oficial de Microsoft para Debian/Ubuntu)
curl -sL https://aka.ms/InstallAzureCLIDeb | sudo bash

# Terraform (repositorio oficial de HashiCorp)
wget -O- https://apt.releases.hashicorp.com/gpg | sudo gpg --dearmor -o /usr/share/keyrings/hashicorp-archive-keyring.gpg
echo "deb [signed-by=/usr/share/keyrings/hashicorp-archive-keyring.gpg] https://apt.releases.hashicorp.com $(lsb_release -cs) main" \
  | sudo tee /etc/apt/sources.list.d/hashicorp.list
sudo apt update && sudo apt install -y terraform

az version && terraform version
```

## 1. Iniciar sesión

```bash
az login --use-device-code          # abre el código en el navegador y aprueba
az account show --query "{suscripcion:name, id:id, tenant:tenantId}" -o table
```

## 2. Revisar regiones permitidas (Azure for Students limita regiones)

```bash
az policy assignment list --query "[].{nombre:displayName, regiones:parameters.listOfAllowedLocations.value}" -o json
```

Si aparece una lista y `eastus2` no está, avisar: hay que cambiar `region` (y conviene que coincida con Mongo).

## 3. Registrar los proveedores de recursos (una vez)

```bash
for p in Microsoft.App Microsoft.OperationalInsights Microsoft.ContainerRegistry Microsoft.KeyVault Microsoft.ManagedIdentity Microsoft.Storage; do
  az provider register --namespace $p
done
az provider list --query "[?namespace=='Microsoft.App' || namespace=='Microsoft.ContainerRegistry'].{ns:namespace, estado:registrationState}" -o table
# Esperar a que digan "Registered" (1-3 minutos).
```

## 4. Estado remoto de Terraform (una vez)

```bash
SUF=$(tr -dc a-z0-9 </dev/urandom | head -c 5)
az group create -n rg-kerna-tfstate -l eastus2 -o none
az storage account create -n stkernatf$SUF -g rg-kerna-tfstate -l eastus2 \
  --sku Standard_LRS --min-tls-version TLS1_2 --allow-blob-public-access false -o none
az storage container create -n tfstate --account-name stkernatf$SUF --auth-mode login -o none
az role assignment create --role "Storage Blob Data Contributor" \
  --assignee $(az ad signed-in-user show --query id -o tsv) \
  --scope $(az storage account show -n stkernatf$SUF -g rg-kerna-tfstate --query id -o tsv) -o none

cd infra/terraform
cat > backend.hcl <<EOF
resource_group_name  = "rg-kerna-tfstate"
storage_account_name = "stkernatf$SUF"
container_name       = "tfstate"
key                  = "kerna-dev.tfstate"
use_azuread_auth     = true
EOF
cp terraform.tfvars.example terraform.tfvars
sed -i "s/00000000-0000-0000-0000-000000000000/$(az account show --query id -o tsv)/" terraform.tfvars
```

(Si `az storage container create` falla por permisos recién asignados, esperar 1-2 minutos y repetir.)

## 5. Primera aplicación: registro, Key Vault y entorno (sin jobs)

```bash
cd infra/terraform
terraform init -backend-config=backend.hcl
terraform validate
terraform plan -out=fase1.tfplan     # revisar: solo "to add", nada "to destroy"
terraform apply fase1.tfplan
```

## 6. Cargar los secretos en Key Vault

Antes: crear el cluster gratuito en [Qdrant Cloud](https://cloud.qdrant.io) (proveedor Azure, región cercana a eastus2) y la API key de Gemini en [Google AI Studio](https://aistudio.google.com/apikey), y agregarlas al `.env` del pipeline:

```
QDRANT_URL='https://xxxx.eastus2-0.azure.cloud.qdrant.io:6333'
QDRANT_API_KEY='...'
GEMINI_API_KEY='...'
```

Luego (los valores se leen del `.env`, no se escriben en la terminal):

```bash
cd infra/terraform
KV=$(terraform output -raw key_vault_nombre)
set -a; . ../../kerna/pipeline_bcn/.env; set +a
az keyvault secret set --vault-name $KV --name mongodb-uri    --file <(printf %s "$MONGODB_URI")    -o none
az keyvault secret set --vault-name $KV --name qdrant-url     --file <(printf %s "$QDRANT_URL")     -o none
az keyvault secret set --vault-name $KV --name qdrant-api-key --file <(printf %s "$QDRANT_API_KEY") -o none
az keyvault secret set --vault-name $KV --name gemini-api-key --file <(printf %s "$GEMINI_API_KEY") -o none
az keyvault secret list --vault-name $KV --query "[].name" -o tsv     # deben salir los 4
```

> Capa gratuita de Gemini: solo denuncias sintéticas (sus términos piden no enviar información confidencial). Ver la pestaña "Arquitectura en Azure" del Resumen técnico.

## 7. Construir y subir la primera imagen

```bash
infra/scripts/subir_imagen.sh --tag v1     # desde la raíz del repo; v1 = imagen_tag de terraform.tfvars
```

El script hace `az acr login`, `docker build` y `docker push` (tag `v1` + `latest`). Construye en local porque ACR Tasks está bloqueado en Azure for Students.

## 8. Segunda aplicación: los jobs

```bash
cd infra/terraform
sed -i 's/crear_jobs *= *false/crear_jobs      = true/' terraform.tfvars
terraform plan -out=fase2.tfplan     # debe agregar 3 jobs
terraform apply fase2.tfplan
```

## 9. MongoDB Atlas: abrir acceso de red (decisión temporal, 1-2 meses)

Atlas → Security → Network Access → Add IP Address → **Allow access from anywhere** (`0.0.0.0/0`). Container Apps no tiene IP de salida fija sin NAT Gateway (de pago). La protección queda en el usuario de mínimo privilegio + TLS.

## 10. Probar un job a mano

```bash
az containerapp job start -n job-kerna-dev-diario -g rg-kerna-dev
az containerapp job execution list -n job-kerna-dev-diario -g rg-kerna-dev \
  --query "[0].{estado:properties.status, inicio:properties.startTime}" -o table
az containerapp job logs show -n job-kerna-dev-diario -g rg-kerna-dev --container pipeline
```

## 11. PostgreSQL de Veridy (servidor, base y firewall)

Antes de crear: Portal de Azure → **Free services** (o "Servicios gratuitos" de Azure for Students) y confirmar que
**Azure Database for PostgreSQL – Flexible Server, Burstable B1ms** aparece con horas disponibles. Si no aparece,
avisar antes de seguir: el servidor cobra por hora mientras está encendido (se puede detener hasta 7 días seguidos).

```bash
cd infra/terraform
KV=$(terraform output -raw key_vault_nombre)

# 1. Contraseñas: se generan aquí y van directo a Key Vault (no se escriben en archivos)
az keyvault secret set --vault-name $KV --name veridy-db-admin-password --value "$(openssl rand -base64 30 | tr -d '/+=')" -o none
az keyvault secret set --vault-name $KV --name veridy-db-app-password   --value "$(openssl rand -base64 30 | tr -d '/+=')" -o none

# 2. IP pública del host donde corre el contenedor de Veridy
curl -s https://ifconfig.me; echo
#    → agregarla en terraform.tfvars:  postgres_ips_permitidas = { "host-veridy" = "<esa IP>" }
sed -i 's/crear_postgres *= *false/crear_postgres  = true/' terraform.tfvars

# 3. Plan y apply (la contraseña entra como valor de solo escritura)
az provider register --namespace Microsoft.DBforPostgreSQL
export TF_VAR_postgres_admin_password="$(az keyvault secret show --vault-name $KV --name veridy-db-admin-password --query value -o tsv)"
terraform plan -out=fase3.tfplan     # debe agregar: servidor, base, 2 configuraciones y las reglas de firewall
terraform apply fase3.tfplan
unset TF_VAR_postgres_admin_password
terraform output postgres_servidor
```

Si `terraform validate` rechaza `administrator_password_wo`, pegar el error: depende de la versión del proveedor azurerm.

## 12. Roles dentro de la base (una vez)

Crea `veridy_app`, el rol con el que corre Veridy (solo lee y escribe datos, sin crear tablas). Usa la imagen
`postgres:15` que ya está en la máquina como cliente `psql`:

```bash
cd infra/terraform
KV=$(terraform output -raw key_vault_nombre)
PGHOST=$(terraform output -raw postgres_servidor)
docker run --rm -i \
  -e PGPASSWORD="$(az keyvault secret show --vault-name $KV --name veridy-db-admin-password --query value -o tsv)" \
  postgres:15 psql "host=$PGHOST dbname=veridy user=veridyadmin sslmode=require" \
  -v app_password="$(az keyvault secret show --vault-name $KV --name veridy-db-app-password --query value -o tsv)" \
  -f - < ../sql/veridy_roles.sql
```

Al final debe mostrar `veridy_app` con `rolsuper = f`. Después, el contenedor de Veridy se conecta según
`docker/README-postgres.md`.

## Probar una versión nueva (sin Terraform)

```bash
infra/scripts/subir_imagen.sh --desplegar --probar diario
```

1. Construye la imagen y la etiqueta con el commit de git (`a1b2c3d`, o `a1b2c3d-sucio-AAAAMMDDHHMM` si hay cambios sin commitear en `kerna/pipeline_bcn`), más `latest`.
2. La sube al registro.
3. `--desplegar`: apunta los 3 jobs a esa imagen (`az containerapp job update`).
4. `--probar diario`: lanza el job y muestra los comandos para ver estado y logs.

Terraform no revierte la imagen desplegada (`ignore_changes` en los jobs): Terraform administra la infraestructura y el script, las versiones. Para volver atrás, desplegar el tag anterior: `infra/scripts/subir_imagen.sh --tag <commit> --desplegar` (reconstruye ese código) o `az containerapp job update -n <job> -g rg-kerna-dev --image <repo>:<tag>`. Ver tags subidos: `az acr repository show-tags -n <acr> --repository kerna-pipeline -o table`.

## Horarios (UTC)

| Job | Cron | Santiago (verano, UTC-3) |
|---|---|---|
| diario | `0 6 * * *` | 03:00 |
| semanal | `0 7 * * 0` | domingo 04:00 |
| vigencia-21719 | `5 3 1 12 *` | 1 de diciembre 00:05 |

En invierno (UTC-4) los jobs corren una hora antes en hora local; no afecta al pipeline.
