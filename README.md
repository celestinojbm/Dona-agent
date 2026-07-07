# Dona — Plataforma-agente de ejecución para dueños de pequeños negocios

Dona convierte el contexto y la intención de un dueño de negocio en
**diagnósticos, oportunidades, activos y acciones reales ejecutadas con
control humano** — con créditos operativos, permisos por nivel de riesgo,
audit trail y medición.

WhatsApp es hoy el canal principal de entrada, **no el producto**: Dona es
multi-canal por diseño (WhatsApp, dashboard web; más canales en el roadmap).

> **Estado: beta controlada.** Producto en producción con primeros usuarios,
> en fase de hardening de seguridad/readiness antes de abrir adquisición.
> Ver [auditoría](docs/auditorias/Auditoria_Fable5_2026-06-09.md) y
> [roadmap a launch-ready](docs/auditorias/Roadmap_Launch_Readiness_Fable5_2026-06-09.md).

El core loop de Dona:

```
diagnóstico → oportunidad → activo → acción propuesta → permiso humano
→ créditos → ejecución controlada → medición → reporte → siguiente paso
```

---

## Capacidades principales

### Conversación inteligente (canal WhatsApp)
- Motor de IA con **Claude Sonnet 4.6** (Anthropic) como modelo principal,
  con fallbacks automáticos (GPT-4o, Claude Haiku).
- Memoria persistente por usuario + resumen automático de historial largo.
- Notas de voz (STT Whisper/Groq, respuesta TTS) y análisis de imágenes.

### Automatización — Action Center
- **Detección de oportunidades** a partir del perfil y contexto del negocio.
- **Acciones con nivel de riesgo** (`LOW`/`MEDIUM`/`HIGH`/`CRITICAL`):
  - LOW se auto-ejecuta; MEDIUM/HIGH requieren aprobación humana;
  - HIGH exige confirmación dedicada (el ejecutor real no tiene trigger
    expuesto por defecto); CRITICAL está bloqueado.
- **Créditos con reserva** (write-ahead) + reconciliación post-crash +
  scheduler de reconciliación (apagado por defecto, opt-in por env var).
- **Audit log** dedicado del pipeline de automatización.
- Visible y operable desde el dashboard web (`landing/`).

### Gestión del negocio
- **CRM**, **finanzas** (ingresos/gastos/reportes), **pedidos**,
  **cotizaciones**, **contenido** y **reportes** al teléfono del dueño.
- **Recordatorios** en lenguaje natural ("recuérdame mañana llamar a Juan").

### Creativos
- Generación de imágenes con **Gemini 2.5 Flash Image / Pro**.
- Flujo de 2 pasos (`preparar_X` → `confirmar_X`) para todo lo que cobra
  créditos o tiene efecto irreversible: el cobro solo ocurre al confirmar.

### Integraciones Google (OAuth opcional)
- **Gmail**, **Calendar**, **Drive**, **Contacts**, **Tasks**, **Sheets** —
  lectura y acciones reales, siempre detrás del patrón preparar/confirmar
  cuando hay efecto externo.

### Dashboard web (`landing/`)
- Next.js + NextAuth. Login derivado de Stripe con **lockout persistente**
  anti fuerza-bruta (estado en backend vía bridge HMAC).
- Créditos, plan, movimientos, Action Center y Customer Portal de Stripe.

### Cumplimiento y seguridad
- Marco legal **CCPA/CPRA + FTC + TCPA** (EEUU).
- Comandos `STOP`/`START` (TCPA) evaluados **antes** de dedup y rate-limit.
- Endpoints `/privacy`, `/terms`, `/privacy/export`, `/privacy/delete`.
- **Fail-closed por defecto**: los paths permisivos solo existen con
  `ENVIRONMENT=development/test` explícito (`agent/entorno.py`); un typo de
  configuración ya no desactiva controles.
- Verificación de firma de webhooks (Stripe, Meta, Whapi), tokens admin con
  `hmac.compare_digest`, cifrado de tokens OAuth (Fernet), sanitización de
  contenido externo contra prompt injection, rate limiting por teléfono,
  deduplicación persistente de mensajes (los proveedores reintentan).

### Billing
- **Créditos operativos prepagos** (enteros, sin decimales).
- Stripe Checkout + webhook idempotente; suscripciones + top-ups +
  Customer Portal.
- Toda tool paga pasa por `cobrar_o_rechazar` antes del trabajo caro; cada
  movimiento deja fila en `transacciones_credito`.

---

## Arquitectura (vista rápida)

```
Canales de entrada
  ├── WhatsApp (Whapi / Meta Cloud API / Twilio)
  │         │  POST /webhook
  │         ▼
  │   agent/providers/   (normaliza payload → MensajeEntrante)
  │         │
  │         ▼
  │   agent/main.py      (TCPA STOP/START → dedupe → rate limit
  │         │             → comandos determinísticos → brain)
  │         ▼
  │   agent/brain.py     (Claude + fallbacks + tool use)
  │
  └── Dashboard (landing/, Next.js)
            │  bridge HMAC (X-Internal-Signature)
            ▼
      /internal/*        (usuario-resumen, automation, auth-lockout)

agent/automation/   Action Center: oportunidades → acciones → permisos
                    → créditos/reservas → ejecutores LOW/MEDIUM/HIGH → audit
agent/business/     CRM / finanzas / pedidos / cotizaciones / ...
agent/creativos/    Imagen (Gemini) — preparar/confirmar
agent/billing.py    Créditos + Stripe + audit trail
agent/memory.py     Historial, dedupe, DB (SQLAlchemy 2 async)
agent/entorno.py    Helper único de entorno (fail-closed por defecto)
```

---

## Stack técnico

| Capa | Tecnología |
|------|-----------|
| Runtime | Python 3.11+ · FastAPI + Uvicorn/Gunicorn |
| LLM primario | Anthropic Claude Sonnet 4.6 |
| LLM fallback | OpenAI GPT-4o, Claude Haiku |
| WhatsApp | Whapi.cloud / Meta Cloud API / Twilio (seleccionable por env) |
| Base de datos | PostgreSQL (prod) / SQLite (dev) · SQLAlchemy 2 async · Alembic |
| Cache/queue | Redis + **arq** — opcional, fallback inproc |
| Storage | Cloudflare R2 (S3 compatible) — opcional, fallback local |
| Pagos | Stripe Checkout + webhook + Customer Portal |
| Imagen | Google Gemini 2.5 Flash Image / Pro |
| Voz | STT Whisper/Groq · TTS OpenAI |
| Dashboard | Next.js 16 + NextAuth (Vercel) |
| Deploy | Render (web service + background worker) |

---

## Desarrollo local

```bash
git clone https://github.com/celestinojbm/Dona-agent.git
cd Dona-agent
python -m venv .venv
source .venv/bin/activate        # en Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env             # llena las keys mínimas
```

Keys mínimas para arrancar:
- `ENVIRONMENT=development` — **obligatorio en local**: sin entorno explícito
  el arranque es fail-closed y exige secrets de producción.
- `ANTHROPIC_API_KEY`
- `WHATSAPP_PROVIDER=whapi` + `WHAPI_TOKEN` (o equivalentes Meta/Twilio)
- `DATABASE_URL` (SQLite por default está OK)

```bash
# Servidor
uvicorn agent.main:app --reload --port 8000

# Dashboard (landing/)
cd landing && npm install && npm run dev

# Tests
pytest                    # 980+ tests (~14 min local, ~4 min en CI)
pytest -x --ff            # fail-fast
pytest -k <keyword>       # filtra por nombre
cd landing && npx vitest run   # tests del dashboard
```

### Jobs asíncronos

`JOBS_BACKEND=inproc` (default sin Redis) o `arq` (requiere `REDIS_URL`):

```bash
python -m arq agent.jobs.worker.WorkerSettings
```

---

## Deploy (Render)

```
Build:  pip install -r requirements.txt
Start:  gunicorn agent.main:app -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:$PORT --workers 1
```

`main` es la rama de producción: Render redespliega automáticamente en cada
push. El arranque es **fail-closed**: con `ENVIRONMENT` distinto de
`development`/`test`, faltar un secret crítico (Stripe, cifrado, bridge,
inbound, provider activo) aborta el deploy en vez de arrancar degradado.

CI (GitHub Actions) corre la suite completa de pytest como gate en cada PR
y push a `main`.

---

## Estructura del repo

```
agent/
├── main.py                 FastAPI app + webhooks + endpoints /internal y /admin
├── brain.py                LLM + fallbacks + tool use
├── entorno.py              Helper único de entorno (fail-closed por defecto)
├── memory.py               Historial, dedupe, DB
├── providers/              Adaptadores WhatsApp (whapi, meta, twilio)
├── automation/             Action Center: oportunidades, acciones, permisos,
│                           créditos/reservas, ejecutores, audit, scheduler
├── business/               CRM, finanzas, pedidos, cotizaciones, contenido, reportes
├── creativos/              Imagen (Gemini) + comandos determinísticos
├── jobs/                   Cola asíncrona (arq) + handlers
├── google_*.py             Gmail, Calendar, Drive, Contacts, Tasks, Sheets
├── billing.py              Créditos + Stripe + audit trail
├── dashboard_lockout.py    Lockout persistente del login del dashboard
├── inbound_tokens.py       Webhooks externos firmados (Zapier/Make/n8n)
├── legal_pages.py          /privacy y /terms
├── rate_limiter.py         Redis o in-memory
└── logging_config.py       JSON + redaction de PII en entorno estricto

landing/                    Dashboard web (Next.js + NextAuth, Vercel)
docs/auditorias/            Auditorías de seguridad/readiness y PR bodies
alembic/                    Migraciones
config/                     business.yaml, prompts.yaml
tests/                      980+ tests (pytest + pytest-asyncio)
```

---

## Licencia

MIT.
