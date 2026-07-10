# Dona — Current State (snapshot operativo)

**Fecha de actualización:** 2026-07-09

Snapshot de Fase 0 (estabilización). Sirve para retomar el proyecto sin
perder contexto. No contiene secretos ni valores de `.env`.

---

## Git

- **Repo:** repo local `Dona-current` → `origin` = `github.com/celestinojbm/Dona-agent.git`
- **Rama base:** `main` (al día con `origin/main`)
- **Rama de trabajo:** `chore/fase-0-estabilizacion`
- **Último commit base:** `5c39d4b` — feat(landing): checkout propio "Configura tu plan" con Stripe Embedded (2026-07-09)
- **Working tree antes de cambios:** limpio salvo `re-audit-v2-delta.md` sin trackear (pertenecía al proyecto Fluvia; eliminado en esta fase)

---

## Resumen real del producto

- **Qué es:** plataforma-agente multimodelo de negocio y ejecución controlada.
  Convierte intención del usuario en tareas, documentos, imágenes, recordatorios,
  automatizaciones y acciones externas reales, siempre con costo, permisos y
  control humano claros (patrón `preparar_X` / `confirmar_X`). Visión canónica
  en `docs/vision/DONA_CANONICAL_CONTEXT.md`.
- **Canal principal actual:** WhatsApp (Whapi.cloud por default, Meta Cloud API
  como alternativa). WhatsApp es canal de entrada, no la visión completa.
- **Qué existe realmente:** backend FastAPI completo (brain multimodelo, billing
  con créditos Stripe, generación de imagen Gemini, recordatorios, onboarding,
  CCPA/TCPA, rate limiting, dedupe, audit trail), landing Next.js con dashboard
  web (chat con imagen/voz), checkout embebido Stripe; 2224 tests backend y
  215 tests frontend verificados en Fase 0.
- **Qué está incompleto:** provider Twilio declarado pero no implementado
  (readiness aborta si se configura); quiet hours TCPA y detección STOP con
  hallazgos abiertos de auditoría; auth web provisional; cola `inproc` pierde
  jobs si no hay Redis; migraciones Alembic conviven con `metadata.create_all()`.
- **Qué NO construir todavía:** features nuevas, marketplace, multi-tenant,
  builder de agentes (AgentKit es legado). Primero estabilización (Fase 0/1).

---

## Backend (`agent/`, 43 módulos)

- **FastAPI** + Uvicorn/Gunicorn; entrypoint `agent/main.py` (webhooks WhatsApp,
  comandos determinísticos por regex ANTES del LLM, endpoints admin con Bearer).
- **Agente / brain:** `agent/brain.py` — LLM principal `claude-sonnet-4-5`
  (`brain.py:1619`, `:3409`; el módulo de proactividad usa `claude-sonnet-4-6`),
  fallbacks GPT-4o y Haiku (DeepSeek eliminado del fallback por PII). Sanitiza
  datos externos con `_PATRONES_INYECCION`.
- **Billing:** `agent/billing.py` — créditos enteros, `cobrar_o_rechazar`,
  audit trail en `transacciones_credito`, webhook Stripe idempotente por
  `stripe_session_id`.
- **WhatsApp providers:** Whapi (default) y Meta Cloud. Twilio: env vars y
  formato de teléfono contemplados, módulo NO implementado.
- **Jobs / cola:** Redis + arq; fallback `inproc` (sin persistencia — pierde
  jobs en restart si no hay `REDIS_URL`; ver riesgos).
- **DB:** PostgreSQL prod (Supabase) / SQLite dev; SQLAlchemy 2 async; Alembic
  presente (`alembic/`) pero convive con `create_all()` en lifespan.
- **Riesgos principales:** quiet hours TCPA, STOP con set cerrado de palabras,
  `inproc` pierde jobs, twilio.py inexistente, dualidad Alembic/create_all.

## Frontend (`landing/`, Next.js)

- **Landing:** `landing/app/page.tsx` — UI moderna (shadcn/Radix, modo oscuro),
  páginas legales (`/politica-de-privacidad`, `/terminos-y-condiciones`),
  soporte, prototipo. Rediseño hero en rama `design/landing-hero-v2` SIN mergear
  (pendiente veredicto del dueño).
- **Dashboard:** `landing/app/dashboard` — chat web contra `/internal/chat` del
  backend con adjuntos de imagen y nota de voz.
- **Auth actual:** provisional (`landing/app/login` + `api/auth`); no apto para
  producción sin endurecimiento.
- **Checkout embebido:** `/checkout` con Stripe Embedded (commit `5c39d4b`);
  flujo hospedado queda como fallback; mismo webhook/fulfillment.
- **Riesgos principales:** auth provisional, env vars de Vercel vacías,
  CSP ampliada para Stripe (revisar al reactivar prod).

---

## Seguridad (solo nombres de riesgo, sin valores)

- `.env` local con secretos en claro (backend y landing).
- Necesidad de **rotación de secretos antes de reactivar producción**.
- Auth web provisional en el dashboard.
- Quiet hours TCPA incompletas.
- Detección STOP limitada a set cerrado de palabras.
- Migraciones DB: Alembic vs `metadata.create_all()` sin fuente única.

## Producción

- **Producción SUSPENDIDA** (Render web suspendido desde ~2026-06-24; DB
  Supabase restaurada 2026-07-01; env de Vercel vacías).
- **No se tocó producción en esta fase.**
- Reactivar producción **NO** es parte de Fase 0 (se decide en Fase 1).

---

## Archivos limpiados en Fase 0 (rama `chore/fase-0-estabilizacion`)

| Archivo | Acción | Evidencia |
|---|---|---|
| `agent/tools.py` | Eliminado | Ningún módulo importa `agent.tools`; sus 16 funciones no tienen callers (solo `agent.tools_catalog` está vivo, es otro módulo). Referencias restantes solo en docs y comando legacy AgentKit. |
| `privacy.html` (raíz) | Eliminado | `/privacy` y `/terms` se sirven desde `agent/legal_pages.py` (`agent/main.py:385`); nada sirve el HTML de raíz. Contenido de marzo-2026, superseded. |
| `re-audit-v2-delta.md` | Eliminado (con respaldo) | Pertenece al proyecto **Fluvia** (`celestinojbm/Fluvia.git`), no a Dona. Estaba sin trackear; copia de respaldo en el scratchpad de la sesión. |
| `coverage.xml` | Eliminado + añadido a `.gitignore` | Artefacto generado por `pytest --cov`, 100% regenerable; no debía estar trackeado. |
| `test_dona.db` | Eliminado | SQLite temporal de 0 bytes, ya cubierto por `*.db` en `.gitignore`. |
| `SLA_interno.md`, `estrategia_errores.md` | Movidos a `docs/` | Docs internos en raíz; `docs/legacy-inventory.md` ya recomendaba moverlos. |

## Archivos revisados pero NO eliminados

| Archivo | Clasificación | Razón |
|---|---|---|
| `migration.py` | Revisar después | Bootstrap manual a Supabase (psycopg2 sync); redundante con Alembic, pero se depreca cuando Alembic sea fuente única (plan T4.3). |
| `enhanced/` | Mantener | VIVO — código de producción con imports activos. Intocable. |
| `config/business.yaml` | Revisar después | Su único lector era `agent/tools.py` (eliminado); quedó huérfano, pero `config/` sigue vivo por `prompts.yaml` (brain). Decidir en próxima fase. |
| `knowledge/`, `start.sh` | Revisar después | Ya inventariados en `docs/legacy-inventory.md` como deprecables en Phase 4. |
| Docs que citan `agent/tools.py` | Revisar después | `docs/legacy-inventory.md` y `docs/ops/zonificacion-autonomia.md` quedan con referencias stale; son docs históricos, no se editaron en esta fase. |

---

## Próxima fase recomendada (Fase 1)

1. Rotar secretos (Anthropic, OpenAI, Stripe, Whapi, Supabase, R2, admin token).
2. Borrar transcripts temporales que contengan secretos.
3. Corregir quiet hours TCPA.
4. Robustecer detección STOP (más allá del set cerrado).
5. Decidir estado de producción (reactivar o mantener suspendida).
6. Preparar reactivación Render (backend) + Vercel (landing): env vars,
   readiness, webhook Stripe y provider WhatsApp confirmado.
