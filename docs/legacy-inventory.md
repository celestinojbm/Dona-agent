# Inventario legacy — Dona

> Documento de planificación. Modo solo lectura sobre producción: este
> inventario describe el estado actual sin proponer borrados ni mover
> código todavía. Cada item tiene una recomendación tentativa
> (mantener / mover / deprecar fase X) que requiere autorización
> explícita del owner antes de ejecutarse.

**Generado**: rama `pr/legacy-inventory` sobre HEAD `5b7d42d`.
**Alcance**: items señalados en planes v2 / v2.1 como posibles legacy de la era AgentKit y otros candidatos detectados durante el scan.

---

## Resumen de hallazgos

| Item | Estado | Recomendación tentativa |
|---|---|---|
| `enhanced/` | **VIVO** — código de producción con N imports activos | Mantener; renombrar/reorganizar dentro de Phase 4 (T4.6) si se decide unificar bajo `agent/` |
| `config/` | **VIVO** — usado por `agent/brain.py` y `agent/tools.py` | Mantener |
| `config/` mount en `docker-compose.yml` | **VIVO** | Mantener |
| `knowledge/` | Carpeta con solo `.gitkeep`; cero referencias en código | Deprecar en Phase 4 (T4.6) tras 1 release sin reactivación |
| `knowledge/` mount en `docker-compose.yml` | Sin uso real (la carpeta solo tiene `.gitkeep`) | Deprecar junto con la carpeta |
| `start.sh` | Legacy AgentKit (`/build-agent`); no es script de producción | Deprecar en Phase 4 — primero reescribir como `start-dev.sh` mínimo o eliminar |
| `migration.py` | Bootstrap manual a Supabase con psycopg2 sync; redundante con Alembic + `metadata.create_all()` en `agent/main.py:lifespan` | Deprecar en T4.3 cuando Alembic real esté en su lugar |
| `dona.db`, `test_dona.db` | SQLite locales presentes en working tree (no commiteados) | Confirmar `.gitignore` los ignora; sin acción |
| `privacy.html` (raíz) | HTML standalone aparente; revisar contra `agent/legal_pages.py` que ya sirve `/privacy` | Investigar duplicación; recomendación tras revisión |
| `Auditoria_Dona_2026-04-27.pdf` y `generar_auditoria.py` | Untracked; documentos de auditoría previos | Mantener untracked o mover a `docs/` |
| `Plan_Dona_*.pdf` y `generar_plan_*_pdf.py` | Untracked; artefactos de planificación generados desde la conversación | Mantener untracked o mover a `docs/` |
| `SLA_interno.md`, `estrategia_errores.md` | Docs internos en la raíz | Mover a `docs/` en cleanup futuro (no urgente) |

---

## 1. `enhanced/` — VIVO, NO ES LEGACY

**Conclusión**: el directorio paralelo `enhanced/` es código de producción, no
legado de AgentKit. Cualquier propuesta de borrarlo o "fusionarlo" fue
incorrecta y queda descartada hasta más análisis.

### Evidencia

`agent/main.py` tiene 19 imports vivos desde `enhanced/`:

| Línea | Import |
|---|---|
| `agent/main.py:164` | `from enhanced.models import inicializar_tablas_enhanced` |
| `agent/main.py:167` | `from enhanced.catalog import sembrar_catalogo` |
| `agent/main.py:933, 935, 952` | `from enhanced.safe_module import tiene_confirmacion_pendiente, SafeModule, _es_owner` |
| `agent/main.py:984, 996` | `from enhanced.diagnostics import diagnostico` |
| `agent/main.py:1004, 1012` | `from enhanced.execution import ejecucion` |
| `agent/main.py:1028` | `from enhanced.insights import insights as _insights_mod` |
| `agent/main.py:1071, 1088` | `from enhanced.safe_module import tiene_confirmacion_pendiente, AccionConfirmable, NivelPermiso, SafeModule` |
| `agent/main.py:1113-1124` | `from enhanced.nlp_detector import es_consulta_catalogo`; `enhanced.catalog`, `enhanced.system_manager` |
| `agent/main.py:1781-1801` | `enhanced.nlp_detector`, `enhanced.catalog`, `enhanced.system_manager`, `enhanced.system_processor` |

`agent/memory.py:2071`: `from enhanced.models import UserSystem, SystemActivityLog`.
`agent/scheduler.py:380`: `from enhanced.monitoring import job_monitoreo`.
`agent/scheduler.py:390`: `from enhanced.insights import job_reporte_semanal`.

### Funcionalidad expuesta

`enhanced/` provee tres pilares activos:

1. **Catálogo de sistemas** (`catalog.py`, `system_manager.py`, `system_processor.py`, `nlp_detector.py`, `models.py`) — sistemas predefinidos que el usuario puede activar (hábitos, finanzas, salud, etc.). Persiste en tablas `system_catalog`, `user_systems`, `system_activity_logs` que viven en la **misma DB** vía `from agent.memory import Base, engine, async_session as async_session_enhanced`.
2. **SafeModule** (`safe_module.py`) — base de habilidades con tres niveles de permiso (`usuario`, `owner`, `owner_critical`) y patrón de doble confirmación (`CONFIRMAR + DONA-ADMIN`). Lo usa `agent/main.py` para flujos de mantenimiento y diagnóstico.
3. **Diagnostics / Execution / Insights / Monitoring** — endpoints de diagnóstico interno y jobs schedulados.

### Tests asociados

- `tests/test_safe_module.py`
- `tests/test_security_fixes.py` (toca `enhanced.safe_module`)

### Recomendación

- **No tocar** durante Phase 0–3.
- En **Phase 4 (T4.6)** evaluar si las habilidades de `enhanced/` calzan como tipos de Iniciativa dentro del `agent/orchestrator/` (entonces se mueven, no se borran).
- Si se mueve, requiere ADR + plan de migración por módulo + tests de regresión.

---

## 2. `config/` — VIVO

`config/business.yaml` y `config/prompts.yaml` están cargados en runtime:

- `agent/brain.py:1213` — `open("config/prompts.yaml", "r", encoding="utf-8")`
- `agent/tools.py:26` — `open("config/business.yaml", "r", encoding="utf-8")`

El mount `./config:/app/config` en `docker-compose.yml:10` es necesario.
Cualquier cambio en `config/*.yaml` requiere reload del contenedor, lo cual es
intencional (configuración hot-swappable en dev).

**Recomendación**: mantener.

---

## 3. `knowledge/` — vacío, sin uso

Estado de la carpeta:
- Contenido: solo `knowledge/.gitkeep`.
- Referencias en código: cero (`grep -r 'knowledge' agent/` no retorna usos en runtime).
- Mount en `docker-compose.yml:9`: `./knowledge:/app/knowledge`.

Origen: aparente vestigio de la era AgentKit cuando "knowledge base" era un
concepto del producto generador-de-agentes. En Dona actual no aplica.

**Riesgos de borrarlo**:
- Bajo: ninguna referencia activa.
- Medio: si algún script externo (no commiteado) escribe ahí en dev local.

**Recomendación**:
- Phase 4 (T4.6, item independiente): borrar carpeta + mount tras 1 release sin reactivación.
- Antes: documentar la decisión en `docs/decisions/` (ADR 0001 — propuesto).

---

## 4. `start.sh` — legacy AgentKit

Contenido: script bash que verifica Python ≥3.11, verifica Claude Code CLI, y
termina invitando a ejecutar `claude` y luego `/build-agent`. Es un script de
**onboarding del repo de un proyecto AgentKit anterior**, no de Dona en
producción.

**No referenciado** por:
- `Dockerfile` (usa `gunicorn ... agent.main:app` directo).
- `docker-compose.yml`.
- `render.yaml` (no existe).
- CI (no existe).

**Recomendación**:
- Phase 4 (T4.6): deprecar.
- Reemplazo recomendado: un `scripts/dev.sh` que documente el flujo dev real
  (instalar deps, copiar `.env.example`, correr `python -m uvicorn agent.main:app --reload`).
- Mientras tanto, agregar header con WARNING que diga que está obsoleto, sin
  borrar todavía.

---

## 5. `migration.py` — bootstrap legacy redundante con Alembic

Ubicación: raíz del repo. ~252 líneas. Función: conecta a Supabase via
`psycopg2-binary` (sync) y ejecuta DDL hardcoded para crear todas las tablas
de Dona (mensajes, recordatorios, etc.) más unos `ALTER TABLE` migracionales.

**Redundancia**:
- `agent/memory.py` define los mismos modelos via SQLAlchemy declarativa.
- `agent/main.py:lifespan` ejecuta `inicializar_db()` que llama a
  `metadata.create_all()`.
- `alembic/versions/001_estado_inicial.py` es un `pass` (estado actual stamped).

**Riesgo de borrarlo hoy**: bajo si Alembic real (T4.3) está implementado, pero
**no podemos borrarlo todavía** porque T4.3 está en Phase 4 y `001_estado_inicial.py`
no contiene los CREATE TABLEs. Si la DB se rehúsa a partir de cero, hoy se
depende de `metadata.create_all()` o de `migration.py` ejecutado manualmente.

**Recomendación**:
- Mantener hasta T4.3 ("Alembic real con autogenerate") complete.
- En T4.3:
  1. Generar revisión Alembic con autogenerate desde el schema actual.
  2. Verificar que aplica idempotentemente sobre DB vacía y sobre DB en
     producción (compare-only).
  3. Cambiar `inicializar_db()` para invocar `alembic upgrade head` en vez de
     `metadata.create_all()`.
  4. Mover `migration.py` a `scripts/legacy/` con header de deprecación.
  5. Borrar tras 1 release estable.

---

## 6. Items menores

### 6.1 `dona.db`, `test_dona.db`
SQLite locales para dev/tests. Verificar que `.gitignore` los excluye:
si no, agregar. **No borrar**.

### 6.2 `privacy.html` (raíz)
HTML standalone presente en la raíz. `agent/legal_pages.py:privacy_policy_html()`
también genera privacy. Posible duplicación. **Acción**: leer ambos, decidir
canon, alinear con T0.6 (disclaimer del landing).

### 6.3 `SLA_interno.md`, `estrategia_errores.md`
Docs internos en la raíz. Recomendación: mover a `docs/` en cleanup futuro
(no urgente, no afecta runtime).

### 6.4 Untracked artifacts (auditoría + planes)
`Auditoria_Dona_2026-04-27.pdf`, `generar_auditoria.py`,
`Plan_Dona_Refinado_v1_2026-04-29.pdf`, `Plan_Dona_Refinado_v2_2026-04-29.pdf`,
`Plan_Dona_v2_1_2026-04-30.pdf`, `generar_plan_pdf.py`, `generar_plan_v2_pdf.py`,
`generar_plan_v21_pdf.py`. No commiteados. Mover a `docs/` o mantener untracked
es decisión del owner.

---

## 7. Resumen accionable

Para Phase 0 (post-PR2): **ninguna acción inmediata** salvo este documento.
Los cambios reales se ejecutan en Phase 4 (T4.6) tras autorización item por
item:

1. Decisión sobre `knowledge/` + mount → ADR + remove.
2. Decisión sobre `start.sh` → reescribir como `scripts/dev.sh`.
3. Decisión sobre `migration.py` → reemplazar por Alembic real (T4.3 antes).
4. Decisión sobre `enhanced/` → re-evaluar tras Phase 3 si conviene moverlo bajo
   `agent/orchestrator/`.

Cada item requiere autorización explícita y su propio PR pequeño.
