# MSI — Runbook de instalación de Dona (J5/J6)

La MSI (Windows + WSL Ubuntu, 64 GB físicos) aloja el backend de Dona en
**staging**. La OptiPlex **no** aloja Dona (es auditora de solo lectura).

Este runbook no se ejecuta desde Claude web. Lo opera **Hermes MSI**, con
encargos preparados aquí y **autorizados por Celestino**. Cada paso dice si
es de solo lectura o si cambia algo.

Estado: § 1 (preflight) listo para encargar. § 2 (paquete) es la
especificación que implementa el PR de J5; depende de J4 (perfil de
arranque sin efectos externos).

---

## 1. Preflight — solo lectura (encargo a Hermes MSI)

Objetivo: saber qué hay antes de proponer un arranque. **No instala, no
para, no reinicia, no cambia configuración.** Devuelve la salida tal cual
(sin tokens; si un comando imprime uno, se recorta).

### 1.1 Windows (PowerShell, usuario normal)

```powershell
# Memoria física y CPU
Get-CimInstance Win32_ComputerSystem | Select-Object TotalPhysicalMemory, NumberOfLogicalProcessors
Get-CimInstance Win32_OperatingSystem | Select-Object FreePhysicalMemory, Caption, Version

# WSL: versión, distros, configuración global
wsl --version
wsl -l -v
Get-Content "$env:USERPROFILE\.wslconfig" -ErrorAction SilentlyContinue

# Suspensión / hibernación (Dona no corre si la MSI duerme)
powercfg /a
powercfg /query SCHEME_CURRENT SUB_SLEEP STANDBYIDLE

# Puertos escuchando en el host
Get-NetTCPConnection -State Listen | Sort-Object LocalPort |
  Select-Object LocalAddress, LocalPort, OwningProcess -Unique

# Docker Desktop (si se usa) y Tailscale
docker version
docker context ls
tailscale status
```

### 1.2 WSL Ubuntu

```bash
uname -a; cat /etc/os-release | head -3
free -h; nproc; df -h / ~ /mnt/c 2>/dev/null
cat /etc/wsl.conf 2>/dev/null              # ¿systemd=true? ¿automount?
ps -p 1 -o comm=                           # systemd o init

docker info --format '{{.ServerVersion}} {{.OperatingSystem}} cpus={{.NCPU}} mem={{.MemTotal}} root={{.DockerRootDir}}'
docker ps --format '{{.Names}}\t{{.Image}}\t{{.Ports}}\t{{.Status}}'
docker volume ls
docker network ls
docker system df
docker compose ls

ss -ltnp 2>/dev/null | sed 1d              # puertos en WSL
systemctl is-enabled docker 2>/dev/null; systemctl is-active docker 2>/dev/null
command -v cloudflared && cloudflared --version
```

### 1.3 Lo que hay que concluir (no suponer)

| Pregunta | Fuente |
|---|---|
| ¿Docker funciona de verdad (daemon arriba, `docker run hello-world` permitido)? | `docker info`; probar `hello-world` solo con OK |
| Memoria que WSL puede usar (por defecto ~50 % del host salvo `.wslconfig`) | `free -h`, `.wslconfig` |
| Disco libre donde viven los volúmenes (`DockerRootDir`) | `docker info`, `df -h` |
| Servicios existentes y sus puertos (Fluvia, n8n, Hermes, Kuma, …) | `docker ps`, `ss`, `Get-NetTCPConnection` |
| Puertos libres para Dona (propuesta: 127.0.0.1:8010 API) | cruzar con lo anterior |
| ¿WSL sobrevive al cierre de sesión / reinicio? ¿Docker arranca solo? | `wsl.conf`, `systemctl is-enabled`, prueba controlada con OK |
| ¿La MSI se suspende? | `powercfg` |

Si algo no se puede comprobar en lectura, se marca **"no verificado"**, no
se asume.

---

## 2. Paquete (especificación para el PR de J5)

### 2.1 Ubicación

```
<repo>/deploy/msi/              ← versionado en el repo, SIN secretos
  compose.yml
  dona.env.example              ← solo nombres, valores vacíos
  estado.sh  parar.sh           ← herramientas que solo tocan el proyecto "dona"
~/dona/                         ← en la MSI, fuera del repo
  compose.yml (copia del SHA fijado)
~/secretos/dona/dona.env        ← chmod 600, dueño el usuario de Hermes MSI
```

### 2.2 Reglas del compose

- Proyecto `dona` (`name: dona`), redes, volúmenes y contenedores con
  prefijo `dona-` y etiqueta `com.dona.stack=staging`.
- **Imagen construida desde un SHA fijo** (`docker build` sobre un
  `git worktree` en ese SHA, o `git archive <sha>`), etiquetada
  `dona-api:<sha-corto>`. Nunca `latest` ni build desde un árbol con cambios.
- Puertos del host **solo en loopback**: `127.0.0.1:8010:8000`. Dentro del
  contenedor la app escucha en `0.0.0.0:8000` (necesario para que Docker la
  alcance); la restricción de exposición es el puerto **publicado** del host.
- Redis (si se usa) **sin puertos publicados**, solo en la red `dona-net`.
- Postgres: **se mantiene Supabase** al principio (no se migra la BD solo por
  cambiar de alojamiento). Nada de Postgres local en J5.
- API y worker separados si `JOBS_BACKEND=arq`: servicios `dona-api` y
  `dona-worker`, misma imagen, distinto comando.
- **Un único responsable por trabajo recurrente**: el scheduler corre solo
  en `dona-api` (1 worker gunicorn) y **apagado** por defecto en staging
  (perfil de J4). El worker arq no registra cron propios.
- Límites iniciales (revisables con mediciones reales de `docker stats`):
  `dona-api` 768 MB / 1 CPU, `dona-worker` 768 MB / 1 CPU, `dona-redis`
  128 MB / 0.25 CPU.
- `restart: unless-stopped`, healthcheck al endpoint de vida de J4.
- Logs `json-file` con rotación (`max-size: 10m`, `max-file: 5`).
- `env_file: ~/secretos/dona/dona.env`. El repo solo tiene el `.example`.

### 2.3 Variables mínimas en staging (perfil de pausa de J4)

Con efectos externos **apagados por defecto**: sin claves de envío
(WhatsApp, correo), sin `STRIPE_SECRET_KEY`, sin claves de modelos
facturables mientras se pruebe el arranque. Lista exacta en
`deploy/msi/dona.env.example` (PR de J5).

### 2.4 Herramientas

- `estado.sh`: `docker compose -p dona ps` + `docker stats --no-stream`
  filtrado por la etiqueta `com.dona.stack=staging`.
- `parar.sh`: `docker compose -p dona stop`. **Conserva volúmenes.** No hay
  ningún script con `down -v`, `volume rm` ni `system prune`.

---

## 3. Conectividad (J6, solo con autorización de arranque)

- **Administración**: Tailscale privado ya existente. No se cambian
  publicaciones existentes ni se usa Funnel.
- **Vercel → backend**: Cloudflare Tunnel (`cloudflared`) sin puertos
  entrantes. Un túnel **no sustituye la autenticación**.
  - No se publica `/internal/*` completo: lista exacta de rutas necesarias,
    el resto denegado en el ingress.
  - Tráfico servidor-servidor con autenticación verificable (HMAC del
    bridge existente y, si se usa Cloudflare Access, *service token* solo en
    el servidor de Vercel, nunca en el navegador).
  - Webhooks de proveedores (cuando vuelvan): rutas específicas con la firma
    del proveedor; sin login interactivo que rompa sus entregas.
  - `cloudflared` en la red `dona-net` apuntando a `http://dona-api:8000`: su
    `localhost` no es el de otro contenedor.
- WhatsApp y Stripe **siguen desconectados** en J6.
- Un monitor remoto (Kuma en la OptiPlex) no alcanza `127.0.0.1` de la MSI:
  vigila por Tailscale o por el hostname del túnel.

## 4. Marcha atrás

`parar.sh` (solo el stack `dona`, conserva volúmenes). Retirar únicamente el
túnel/acceso nuevo si se autorizó. No se toca Fluvia, n8n, Hermes ni ningún
otro servicio.
