# Respaldo y retiro de servicios antiguos (J2)

Objetivo: retirar Render y el Railway antiguo **sin perder datos** y sin
afectar otros proyectos. Lo ejecuta Celestino. Este documento dice qué
inventariar, cómo respaldar, cómo comprobar el respaldo y en qué orden
retirar.

Reglas:

- Nada se borra antes de un respaldo **comprobado** (restaurado en aislado).
- Los valores de variables van **solo** al gestor de secretos de Celestino.
  En los documentos, únicamente nombres.
- No se reactiva ningún servicio para poder respaldarlo sin decidirlo antes
  explícitamente (reactivar puede volver a enviar mensajes o cobrar: ver J4).
- El borrado en un proveedor **no es reversible**. La marcha atrás es
  recrear desde configuración y respaldo.

---

## 1. Lo que el código dice (verificado en el repo, `main` = `958b525`)

Sirve para saber qué buscar en los paneles; no sustituye al inventario.

| Pieza | Qué hace | Dónde |
|---|---|---|
| Web (FastAPI + gunicorn, 1 worker) | API, webhooks, `/internal/*` para la landing | `Dockerfile`, `agent/main.py` |
| APScheduler **dentro del proceso web** | 15 jobs al arrancar, siempre: recordatorios (1 min), Google Calendar (5 min), seguimientos CRM (10 min), **self-ping a `RENDER_EXTERNAL_URL` (10 min)**, onboarding y proactividad (1 h), monitoreo `enhanced/` (15 min), resúmenes/insights semanales, simulaciones MiroFish (lun/mié/vie), limpieza (1 h) | `agent/scheduler.py` `iniciar_scheduler` |
| Worker arq (opcional) | jobs creativos (imagen, video, voz) si `JOBS_BACKEND=arq` + `REDIS_URL` | `agent/jobs/worker.py` |
| Redis (opcional) | cola y resultados de arq (`keep_result` 1 h); contadores de rate limiting | `agent/jobs/queue.py`, `agent/rate_limiter.py` |
| Postgres | **Supabase** (según `docs/CURRENT_STATE.md`); SQLite solo en dev | `DATABASE_URL` |
| Archivos generados | **R2** si `R2_*` está configurado; si no, **disco local `./assets/`** del contenedor | `agent/storage.py` |

Consecuencias:

- **Redis no es necesariamente efímero.** El estado canónico de cada job
  creativo vive en la BD (`jobs_creativos`), y al arrancar un reaper marca
  como error y reembolsa los que quedaron `running`. Pero Redis puede tener
  jobs **encolados aún no tomados** (su fila sigue `pending` en la BD) y
  resultados recientes. Hay que inspeccionarlo antes de declararlo
  desechable (§ 3.3).
- **Si R2 no estaba configurado**, las imágenes generadas quedaron en el
  disco del contenedor de Render. Sin un *Disk* persistente, ya se
  perdieron en cada redeploy. Con *Disk*, están ahí y no se pueden bajar
  con el servicio suspendido (§ 3.4).

---

## 2. Inventario (Celestino, en los paneles)

Rellena una tabla por proveedor. Solo nombres y datos no sensibles.

### 2.1 Render (dashboard.render.com, workspace de Dona)

| Recurso | Tipo | Plan | Región | Estado | Auto-Deploy | Repo/rama | Build / start | Disk | Dominio | Cargo mensual |
|---|---|---|---|---|---|---|---|---|---|---|
| | Web Service | | | suspendido | | | | | | |
| | Background Worker | | | | | | | | | |
| | Key Value / Redis | | | | | | | | | |
| | Postgres | | | | | | | | | |
| | Cron Job | | | | | | | | | |

Además:

- **Environment** de cada servicio: copia los **nombres** a una lista; los
  valores, solo al gestor de secretos.
- **Billing**: cargos del mes en curso, cargos devengados pendientes y
  próximo cargo estimado.
- ¿Algún recurso **no** es de Dona (compartido con otro proyecto)? Márcalo
  y no lo toques.

### 2.2 Railway (proyecto antiguo, desplegado desde este repo en abril)

Hay *deployments* de Railway asociados al repo (13–14 abr 2026). Comprueba
si el proyecto existe, si tiene servicios, volúmenes o bases, y si factura.
Misma tabla que Render.

### 2.3 Supabase (proyecto de Dona)

- Proyecto, versión de Postgres, tamaño, plan de la **organización**.
- **La organización también sostiene `manos-venezuela` en producción.** No
  modificar organización, facturación ni recursos de ese proyecto. Las
  acciones de este documento se limitan al proyecto de Dona.
- Componentes usados de verdad (marcar):
  - [ ] Tablas del esquema `public` (55 según el inventario del 7 oct).
  - [ ] Extensiones (`vector` si se activó pgvector para `agent/vector_memory.py`; otras).
  - [ ] **Storage** (buckets): el código **no** usa Supabase Storage (usa R2); confirmar que no hay buckets con datos.
  - [ ] Auth de Supabase: el código **no** la usa; confirmar que no hay usuarios.
  - [ ] Edge Functions, cron (`pg_cron`), webhooks de base de datos.
  - [ ] Políticas RLS y roles propios.
- Backups del plan (diarios / PITR): fecha del último disponible.

### 2.4 Cloudflare R2

- Bucket de Dona (`R2_BUCKET`): nº de objetos y tamaño. Si existe, entra en
  el respaldo (§ 3.5). Si no existe o está vacío, anotarlo.

---

## 3. Respaldos

Hazlos desde una máquina de confianza (la MSI vale), con las credenciales
fuera de cualquier repo. Guarda cada artefacto con su **SHA-256** en un
manifiesto.

### 3.1 Supabase: dump consistente

Conexión **directa** o por *session pooler* (el *transaction pooler* no
sirve para `pg_dump`). Versión del cliente `pg_dump` ≥ versión del
servidor (Postgres 17).

```bash
# Variables solo en tu shell; nunca en un archivo del repo.
export PGURL='postgresql://...'          # cadena de conexión del proyecto Dona
umask 077
mkdir -p ~/dona-respaldos/$(date +%F) && cd ~/dona-respaldos/$(date +%F)

# Esquema + datos, formato custom (permite restaurar selectivo).
pg_dump "$PGURL" --format=custom --no-owner --no-privileges \
  --schema=public --file=dona-public.dump

# Esquema solo (para revisar a ojo extensiones, políticas, funciones).
pg_dump "$PGURL" --schema-only --file=dona-schema.sql

# Recuentos exactos por tabla en el ORIGEN (para comparar al restaurar).
psql "$PGURL" -At -c "
  select format('select %L, count(*) from public.%I;', tablename, tablename)
  from pg_tables where schemaname = 'public' order by tablename" \
| psql "$PGURL" -At -F ' ' > recuentos-origen.txt

# Extensiones activas.
psql "$PGURL" -At -c "select extname, extversion from pg_extension order by 1" > extensiones.txt

sha256sum dona-public.dump dona-schema.sql recuentos-origen.txt extensiones.txt > MANIFIESTO.sha256
```

Cifrado (elige una herramienta y documenta cuál):

```bash
# age (recomendado): clave pública de Celestino; la privada fuera de la máquina.
age -r <clave-publica-age> -o dona-public.dump.age dona-public.dump
# o GPG simétrico (mismo patrón que el backup de n8n):
gpg --symmetric --cipher-algo AES256 dona-public.dump
sha256sum dona-public.dump.* >> MANIFIESTO.sha256
```

Borra los `.dump` en claro **solo después** de comprobar la restauración
(§ 4). Guarda dos copias del cifrado en ubicaciones distintas.

### 3.2 Render / Railway: configuración

- Nombres de variables por servicio, build/start command, región, plan,
  health check path, dominios, Auto-Deploy, instancias. Es lo que permite
  recrear el servicio.
- **Postgres de Render o Railway**, si existe: export desde su panel o
  `pg_dump` como en § 3.1. Según la documentación del repo no lo hay (la BD
  es Supabase): confirmarlo.

### 3.3 Redis

Antes de declararlo desechable, mira qué tiene (solo lectura):

```bash
redis-cli -u "$REDIS_URL" --scan --count 1000 | sed 's/:.*//' | sort | uniq -c
redis-cli -u "$REDIS_URL" zcard arq:queue      # jobs de arq encolados (sorted set)
```

- Si la cola de arq tiene jobs: anota cuántos; sus filas en `jobs_creativos`
  siguen `pending` en la BD. No se ejecutan (Dona en pausa).
- Rate limiting y resultados de arq: efímeros por diseño.
- Si el Redis de Render está suspendido y no se puede leer: anótalo como
  "no inspeccionable" y decide; no lo declares vacío.

### 3.4 Disco (Render Disk)

Si el web service tenía *Disk*: contiene `./assets/` (archivos generados) si
R2 no estaba configurado. Con el servicio suspendido **no** se puede
descargar. Opciones, **todas decisión de Celestino**:

1. Aceptar la pérdida (si R2 sí estaba configurado, el disco no tiene nada
   único).
2. Reactivar el servicio **solo** para copiar el disco, con J4 aplicado
   antes (sin scheduler, sin WhatsApp, sin Stripe). No hacerlo con el código
   actual de `main`: el scheduler enviaría mensajes al arrancar.

### 3.5 R2

```bash
# rclone o aws-cli con perfil de solo lectura.
aws s3 sync s3://<bucket> ./r2-dona/ --endpoint-url https://<account>.r2.cloudflarestorage.com
find r2-dona -type f | wc -l; du -sh r2-dona
tar -cf r2-dona.tar r2-dona && age -r <clave-publica-age> -o r2-dona.tar.age r2-dona.tar
sha256sum r2-dona.tar.age >> MANIFIESTO.sha256
```

---

## 4. Prueba de restauración aislada

En la MSI o en la máquina del respaldo. **Sin red hacia fuera, sin
credenciales de envío ni de cobro, sin arrancar Dona.**

```bash
cd ~/dona-respaldos/<fecha>
sha256sum -c MANIFIESTO.sha256                      # integridad
age -d -i <clave-privada> -o dona-public.dump dona-public.dump.age

docker run -d --name dona-restore-test --network none \
  -e POSTGRES_PASSWORD=solo-local -v "$PWD":/respaldo:ro postgres:17
# (si hace falta pgvector: imagen pgvector/pgvector:pg17)
docker exec dona-restore-test sh -c 'until pg_isready; do sleep 1; done'
docker exec dona-restore-test createdb -U postgres dona_restore
# Extensiones del origen (extensiones.txt viene de `psql -At`: separador "|").
# Las de gestión propias de Supabase pueden no existir en la imagen: anota
# cuáles fallan en vez de ignorarlas.
docker exec dona-restore-test sh -c 'for e in $(cut -d"|" -f1 /respaldo/extensiones.txt); do psql -U postgres -d dona_restore -c "create extension if not exists \"$e\"" || echo "EXTENSION NO DISPONIBLE: $e"; done'
docker exec dona-restore-test pg_restore -U postgres -d dona_restore --no-owner --no-privileges /respaldo/dona-public.dump

# Recuentos en el restaurado y comparación con el origen.
docker exec dona-restore-test psql -U postgres -d dona_restore -At -c "
  select format('select %L, count(*) from public.%I;', tablename, tablename)
  from pg_tables where schemaname='public' order by tablename" \
| docker exec -i dona-restore-test psql -U postgres -d dona_restore -At -F ' ' > recuentos-restaurado.txt
diff recuentos-origen.txt recuentos-restaurado.txt && echo "RECUENTOS IGUALES"
```

Lectura funcional mínima (solo `select`, sin imprimir datos personales):

- `select count(*) from suscripcion_stripe;` y estados agregados
  (`select status, count(*) ... group by status`).
- `select count(*), sum(delta) from transacciones_credito;`
- `select max("timestamp") from mensajes;` (último mensaje guardado).
- `select estado, count(*) from jobs_creativos group by estado;` (jobs
  `pending`/`running` que quedaron a medias).

Guarda en el manifiesto: fecha, tamaño, SHA-256, nº de tablas, resultado
del `diff`, errores de `pg_restore` (si los hubo, cuáles). **No** guardes
salidas con datos personales.

Al terminar: `docker rm -f dona-restore-test` (contenedor de prueba, no
datos de origen).

---

## 5. Retiro (Celestino, tras § 4 en verde)

Orden:

1. **Render → Auto-Deploy: Off** en todos los servicios de Dona (esto va
   **antes de cualquier merge a `main`**, incluido el PR de pausa).
2. Quitar a Render (y Railway, si existe) el acceso al repo en GitHub:
   *Settings → Applications → Installed GitHub Apps*, o limitar el repo.
3. Borrar los recursos **de Dona** aprobados en el inventario: web, worker,
   Redis, cron, disk. No borrar nada compartido.
4. Railway antiguo: mismo patrón (respaldo de configuración → borrado).
5. Supabase: **no** pausar ni borrar en esta fase. La BD es la que se
   reutiliza en J5 (no se traslada solo por cambiar el alojamiento).
6. Facturación: comprobar en cada proveedor que no quedan recursos
   facturables **y** revisar los cargos devengados del periodo. Un `404` en
   la URL antigua no prueba "próximo cargo cero".

Acta de retiro (rellenar en `ESTADO.md`):

| Proveedor | Recurso | Respaldo comprobado (fecha, SHA) | Acción | Fecha | Facturación tras el retiro |
|---|---|---|---|---|---|
| | | | borrado / bloqueado / conservado | | |

## 6. Marcha atrás

- Servicio borrado: recrear desde el `Dockerfile` del SHA elegido + nombres
  de variables + valores del gestor de secretos. Con J4 aplicado, arrancar
  en perfil de pausa.
- Datos: restaurar desde el dump cifrado verificado.
- El borrado en el proveedor **no** es reversible.
