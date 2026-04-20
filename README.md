# Dona — Asistente de WhatsApp para dueños de negocio

Dona es un asistente de IA por WhatsApp diseñado para dueños de pequeños
negocios en Estados Unidos. Atiende a tus clientes, administra tu operación
y genera contenido — todo desde el chat de WhatsApp, sin apps adicionales.

> **Estado:** primeros usuarios en producción.
> No es un producto “arma-tu-agente”: es un agente listo para usar que se
> conecta al WhatsApp del negocio.

---

## Capacidades principales

### Conversación inteligente
- Motor de IA con **Claude Sonnet 4.6** (Anthropic) como modelo principal.
- **Fallbacks automáticos** a DeepSeek, GPT-4o y Haiku si el proveedor primario
  falla o se satura.
- Memoria persistente por número de teléfono + resumen automático para mantener
  contexto en conversaciones largas.
- Transcripción de notas de voz (Whisper/Groq) y respuesta en audio (TTS).
- Análisis de imágenes recibidas (visión).

### Gestión del negocio
- **CRM** — contactos, etapas, notas y seguimiento.
- **Finanzas** — registro de ingresos/gastos, categorías, reportes.
- **Pedidos** — toma y seguimiento de órdenes.
- **Cotizaciones** — armado y envío de cotizaciones al cliente.
- **Contenido** — generación de posts, descripciones y material de marketing.
- **Reportes** — resúmenes de actividad al teléfono del dueño.
- **Recordatorios** en lenguaje natural (“recuérdame mañana llamar a Juan”).

### Creativos
- Generación de imágenes con **Gemini 2.5 Flash Image / Pro**.
- Flujo determinístico de 2 pasos (`preparar` → `confirmar`) para cobrar solo
  cuando el usuario confirma.
- Comando literal (`dona imagen <prompt>`) y detección en lenguaje natural
  (“hazme una imagen de …”, “dibuja …”, “imagen de …”).

### Integraciones Google (OAuth opcional)
- **Gmail** — consultar y redactar correos con adjuntos.
- **Calendar** — leer y crear eventos reales.
- **Drive** — búsqueda y consulta de archivos.
- **Contacts** — lectura y actualización.
- **Tasks / Sheets** — lectura y actualización.

### Cumplimiento y seguridad
- Marco legal **CCPA/CPRA + FTC + TCPA** (multi-estado EEUU).
- Endpoints públicos `/privacy`, `/terms`, `/privacy/export`, `/privacy/delete`.
- Comandos `STOP` / `START` para opt-out/opt-in TCPA.
- Sanitización de contenido externo para mitigar prompt injection.
- Rate limiting por teléfono (Redis o in-memory).
- Tokens admin con `hmac.compare_digest`.
- Deduplicación persistente de mensajes para resistir reintentos del proveedor.

### Billing
- Modelo de **créditos prepagos** (entero, sin decimales, sin drift).
- Checkout vía **Stripe**; webhook idempotente (re-entregar un evento no
  duplica créditos).
- Cada tool creativa declara su `costo_creditos`; `cobrar_o_rechazar` es el
  gate que todas deben pasar.

---

## Arquitectura (vista rápida)

```
WhatsApp (cliente)
      │
      ▼
Proveedor (Whapi / Meta / Twilio)
      │  POST /webhook
      ▼
agent/providers/  (normaliza payload → MensajeEntrante)
      │
      ▼
agent/main.py  (rate limit → dedupe → comandos determinísticos → brain)
      │
      ▼
agent/brain.py  (Claude + fallbacks + tool use)
      │
      ├── agent/memory.py          — historial por teléfono
      ├── agent/business/*         — CRM / finanzas / pedidos / ...
      ├── agent/creativos/*        — imagen (Gemini)
      ├── agent/jobs/*             — cola asíncrona (arq o inproc)
      ├── agent/google_*           — integraciones Google
      └── agent/billing.py         — créditos + Stripe
```

Las **herramientas de 2 pasos** (pagadas o con efecto secundario irreversible)
siguen el patrón `preparar_X` → `confirmar_X` para evitar que el LLM alucine
éxito antes de confirmar.

---

## Stack técnico

| Capa | Tecnología |
|------|-----------|
| Runtime | Python 3.11+ |
| Servidor | FastAPI + Uvicorn/Gunicorn |
| LLM primario | Anthropic Claude Sonnet 4.6 |
| LLM fallback | DeepSeek, OpenAI GPT-4o, Claude Haiku |
| WhatsApp | Whapi.cloud (default) / Meta Cloud API / Twilio |
| Base de datos | PostgreSQL (prod) / SQLite (dev), SQLAlchemy 2, Alembic |
| Cache/queue | Redis + **arq** (cola asíncrona) — opcional, hay fallback inproc |
| Storage de assets | **Cloudflare R2** (S3 compatible vía `aioboto3`) — opcional |
| Pagos | Stripe Checkout + webhook |
| Visión | Anthropic Claude (vision) |
| Imagen | Google Gemini 2.5 Flash Image / Pro |
| Voz (STT) | OpenAI Whisper o Groq |
| Voz (TTS) | OpenAI TTS |
| Web agent | Playwright (opcional) |
| Scheduler | APScheduler |
| Deploy | Render |

---

## Desarrollo local

### Requisitos
- Python 3.11+
- (Opcional) PostgreSQL si no quieres usar SQLite
- (Opcional) Redis si vas a probar jobs con `arq`

### Setup

```bash
git clone https://github.com/celestinojbm/Dona-agent.git
cd Dona-agent
python -m venv .venv
source .venv/bin/activate        # en Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env              # llena las keys mínimas
```

Keys mínimas para que arranque algo útil:
- `ANTHROPIC_API_KEY`
- `WHATSAPP_PROVIDER=whapi` + `WHAPI_TOKEN` (o equivalentes para Meta/Twilio)
- `DATABASE_URL` (SQLite por default está OK)

### Correr

```bash
# Servidor
uvicorn agent.main:app --reload --port 8000

# Tests
pytest                            # suite completa (~50s)
pytest tests/test_creativos_imagen.py -v   # módulo específico

# Migraciones
alembic upgrade head
```

### Jobs asíncronos

Hay dos modos controlados por `JOBS_BACKEND`:

- `inproc` (default sin Redis): los jobs corren en tasks del web service. OK
  para volúmenes bajos; bloquea el event loop si la carga sube.
- `arq` (requiere `REDIS_URL`): cola Redis + worker aparte.

Worker arq:
```bash
python -m arq agent.jobs.worker.WorkerSettings
```

---

## Deploy (Render)

Servicio web:
```
Build:  pip install -r requirements.txt
Start:  gunicorn agent.main:app -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:$PORT --workers 1
```

Variables críticas: `ANTHROPIC_API_KEY`, `DATABASE_URL` (PostgreSQL gestionada),
`WHATSAPP_PROVIDER`, token del proveedor elegido, `ADMIN_TOKEN`, y las keys
opcionales según integraciones (`GEMINI_API_KEY`, `STRIPE_SECRET_KEY`,
`R2_*`, `OPENAI_API_KEY`, etc.).

Para producción con volumen real, levantar además un **Background Worker**
con el comando de arq y `JOBS_BACKEND=arq` en ambos servicios.

---

## Estructura del repo

```
agent/
├── main.py                 FastAPI app + webhook + endpoints admin
├── brain.py                LLM + fallbacks + tool use
├── memory.py               Historial, dedupe, ubicación, mirofish state
├── memory_summary.py       Resumen automático de historial largo
├── providers/              Adaptadores WhatsApp (whapi, meta, twilio)
├── business/               CRM, finanzas, pedidos, cotizaciones, contenido, reportes, quotas
├── creativos/              Generación de imagen (Gemini) + comandos
├── jobs/                   Cola asíncrona (arq) + handlers creativos
├── google_*.py             Gmail, Calendar, Drive, Contacts, Tasks, Sheets
├── web_agent/              Automatización con Playwright (opcional)
├── billing.py              Créditos + paquetes + audit trail
├── billing_commands.py     Comandos de texto ("dona saldo", "dona recargar", ...)
├── comandos_info.py        "dona ayuda", "dona privacidad", "mis_assets", etc.
├── onboarding.py           Flujo inicial guiado para nuevos usuarios
├── business/onboarding_negocio.py
│                           Onboarding del negocio (nombre, rubro, horario, ...)
├── proactivity.py          Proactividad, STOP/START TCPA
├── learning.py             Registro de interacciones
├── location.py             Detección de ubicación/viajes
├── transcriber.py          STT (Whisper/Groq)
├── tts.py                  TTS (OpenAI)
├── vision.py               Análisis de imágenes entrantes
├── real_world.py           Clima, noticias, tráfico
├── reminders_nl.py         Recordatorios en lenguaje natural
├── scheduler.py            APScheduler loop
├── storage.py              R2 (S3 compatible) + fallback local
├── rate_limiter.py         Redis o in-memory
├── legal_pages.py          HTML de /privacy y /terms
├── inbound_tokens.py       Webhooks externos (Zapier/Make/n8n)
└── logging_config.py

alembic/                    Migraciones
config/                     business.yaml, prompts.yaml
tests/                      370+ tests (pytest + pytest-asyncio)
landing/                    Sitio web (Next.js, /landing)
```

---

## Pruebas

```bash
pytest                    # 370+ tests
pytest -x --ff            # fail-fast con “failed first”
pytest -k imagen -v       # solo tests cuyo nombre contenga "imagen"
```

Los tests usan SQLite en memoria, mocks de httpx para proveedores externos
(Gemini, OpenAI, Whapi) y `monkeypatch` de env vars para aislar módulos.

---

## Licencia

MIT.
