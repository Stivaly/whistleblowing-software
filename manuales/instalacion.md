# Manual de Instalación

## Requisitos Previos

### Docker Desktop
Instale Docker Desktop según su sistema operativo:

| Sistema | Descarga |
|---------|----------|
| Windows | https://docs.docker.com/desktop/install/windows-install/ |
| macOS | https://docs.docker.com/desktop/install/mac-install/ |
| Linux | https://docs.docker.com/desktop/install/linux-install/ |

**Verificar instalación:**
```bash
docker --version
docker compose version
```

---

## Instalación Rápida (Imagen Oficial)

```bash
docker volume create veridy_veridy

docker run -d --name veridy \
  -p 80:8080 \
  -p 443:8443 \
  -v docker_veridy:/var/veridy \
  --restart unless-stopped \
  veridy/veridy:latest
```

**Acceder:** https://localhost:443

---

## Instalación con Docker Compose (Recomendado)

### 1. Crear estructura
```bash
mkdir veridy && cd veridy
```

### 2. Crear docker-compose.yml
```yaml
services:
  veridy:
    image: veridy/veridy:latest
    container_name: veridy
    restart: unless-stopped
    ports:
      - "80:8080"
      - "443:8443"
    volumes:
      - veridy_data:/var/veridy
    healthcheck:
      test: ["CMD", "curl", "-k", "-f", "https://localhost:8443/api/health"]
      interval: 30s
      timeout: 5s
      retries: 12
      start_period: 60s

volumes:
  veridy_data:
```

### 3. Iniciar
```bash
docker compose up -d
```

### 4. Verificar
```bash
docker compose ps
docker compose logs -f
```

---

## Instalación desde Código Fuente

### 1. Clonar repositorio
```bash
git clone https://github.com/veridy/veridy-whistleblowing-software.git
cd veridy-whistleblowing-software
```

### 2. Crear volumen
```bash
docker volume create docker_veridy
```

### 3. Construir y ejecutar
```bash
cd docker
docker compose up -d --build
```

---

## Configuración Inicial

1. Acceda a https://localhost:443
2. Acepte el certificado autofirmado
3. Complete el asistente de configuración:
   - Nombre del proyecto
   - Credenciales del administrador
   - Idioma predeterminado
   - Configuración de canales

---

## Actualización

### Imagen Oficial
```bash
docker pull veridy/veridy:latest
docker stop veridy
docker rm veridy
docker run -d --name veridy \
  -p 80:8080 \
  -p 443:8443 \
  -v docker_veridy:/var/veridy \
  --restart unless-stopped \
  veridy/veridy:latest
```

### Con Docker Compose
```bash
docker compose pull
docker compose up -d
```

### Desde Código Fuente
```bash
git pull origin stable
cd docker
docker compose up -d --build
```

---

## Backup y Restauración

### Backup
```bash
docker run --rm \
  -v docker_veridy:/data \
  -v $(pwd):/backup \
  alpine tar czf /backup/veridy-backup.tar.gz -C /data .
```

### Restauración
```bash
docker stop veridy
docker run --rm \
  -v docker_veridy:/data \
  -v $(pwd):/backup \
  alpine sh -c "rm -rf /data/* && tar xzf /backup/veridy-backup.tar.gz -C /data"
docker start veridy
```

---

## Puertos

| Puerto | Uso |
|--------|-----|
| 8080 | HTTP interno |
| 8443 | HTTPS interno |
| 80 | HTTP externo (mapeo) |
| 443 | HTTPS externo (mapeo) |

---

## Comandos Útiles

```bash
# Ver logs
docker logs -f veridy

# Reiniciar
docker restart veridy

# Detener
docker stop veridy

# Eliminar (conserva datos)
docker rm veridy

# Estado de salud
docker inspect --format='{{.State.Health.Status}}' veridy
```

---

## Solución de Problemas

**El contenedor no inicia:**
```bash
docker logs veridy
```

**Puerto en uso:**
Cambie el puerto en docker-compose.yml o en el comando docker run.

**Permisos de volumen:**
```bash
docker exec -u root veridy chown -R veridy:veridy /var/veridy
```

**Verificar conectividad:**
```bash
curl -k https://localhost:443/api/health
```
