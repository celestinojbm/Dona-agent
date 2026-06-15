# CLAUDE.md — Guía para Claude Code en el repo de Dona

> Este archivo se carga automáticamente por Claude Code al trabajar en este
> proyecto. Contiene identidad, convenciones y decisiones que NO son
> derivables leyendo el código.

---

## 1. Identidad del proyecto

Este repo es **Dona**. La visión canónica actual está en
`docs/vision/DONA_CANONICAL_CONTEXT.md` y debe leerse antes de cambios de
producto, UX, agentes, acciones externas, créditos, permisos o narrativa.

Definición corta: Dona es una **plataforma-agente multimodelo de negocio y
ejecución controlada**. Convierte situaciones, recursos, objetivos e intención
en activos, workflows/playbooks, documentos, diseños, campañas,
automatizaciones, software, acciones externas reales, reportes y medición.

La implementación actual atiende usuarios principalmente por **WhatsApp** y ya
opera con primeros usuarios, pero WhatsApp es un canal de entrada, no la visión
completa del producto.

- **NO** es solo chatbot, CRM genérico, growth tool estrecha, galería de tools
  ni marketplace prematuro.
- **NO** es un generador/builder de agentes (como lo fue una versión previa
  llamada “AgentKit”). Si ves referencias a AgentKit en comentarios o docs,
  son legado pendiente de limpieza.
- **NO** es multi-tenant “deploy-tu-propio-agente”: hoy es un servicio
  compartido que atiende múltiples usuarios identificados por su teléfono,
  aunque la visión de plataforma es más amplia.
- El usuario de este repo (el desarrollador) opera desde **EEUU**. Marco
  legal aplicable: **CCPA/CPRA + FTC + TCPA** (y variantes por estado).
  **No aplicar LFPDPPP ni marcos legales mexicanos.**

Regla de oro: Dona prepara, propone y ejecuta acciones reales solo con costo,
riesgo, permisos, trazabilidad y control humano claros.

---

## 2. Terminología y tono

- **Idioma**: español. Comentarios, nombres descriptivos, logs, mensajes al
  usuario, commit messages — todo en español.
- Los primeros usuarios de Dona son simplemente **“usuarios”**.
  **No usar “Fundadores”**, “beta testers”, “early adopters”, ni variantes
  marketineras. Es solo “usuarios”.
- Respuestas de Dona al usuario final: claras, directas, cálidas pero sin
  exagerar. Sin emojis salvo que el contenido lo pida (headers de preview,
  alertas, etc.). Nunca “¡Hola amigo!”, sí “Hola Celestino”.

---

## 3. Convenciones críticas

### 3.1 Tools de 2 pasos — naming LITERAL

Cualquier acción con efecto secundario irreversible o costo (cobra créditos,
envía correo, agenda cita, genera imagen, etc.) DEBE usar el patrón:

- `preparar_X(args) → preview`
- `confirmar_X() → resultado`
- `cancelar_X() → bool`

**Usa el verbo literal `preparar` y `confirmar`.** No inventes nombres como
`enviar_correo_y_confirmar`, `crear_y_notificar`, `X_final`, etc. La razón:
Claude (el LLM) alucina éxito cuando el nombre de la tool sugiere que la
acción ya sucedió. `preparar_X` deja claro que solo está preparando, y
`confirmar_X` es la única que materializa.

El prompt del sistema y los ejemplos few-shot en brain.py dependen de esta
convención. Al agregar tools nuevas, respétala.

### 3.2 Comandos determinísticos ANTES del LLM

Comandos con intent claro (generar imagen, saldo, recargar, privacidad,
STOP/START TCPA, onboarding) se detectan con **regex en main.py antes de
llamar al LLM**. No los delegues al routing del brain.

Razón: determinismo (no depende de tool call del LLM), latencia (no gasta
un round trip) y costo (no gasta tokens). `agent/creativos/comandos.py` es
el ejemplo canónico.

### 3.3 Billing — créditos enteros, idempotencia, audit trail

- Saldo es **entero** (créditos). No usar decimales.
- Cobros y acreditaciones dejan fila en `transacciones_credito`.
- Webhook de Stripe es idempotente vía `stripe_session_id`: reentregar un
  evento NO duplica créditos.
- Toda tool paga debe pasar por `cobrar_o_rechazar` antes de ejecutar
  trabajo caro.

### 3.4 Privacidad y TCPA

- Páginas legales: `/privacy`, `/terms` (servidas desde `agent/legal_pages.py`).
- Endpoints CCPA: `/privacy/export`, `/privacy/delete`.
- Comandos TCPA: `STOP` / `START` (case-insensitive, con o sin “dona”).
  Se evalúan antes que cualquier otro routing y no consumen créditos ni
  LLM.

### 3.5 Seguridad

- Tokens admin: siempre comparar con `hmac.compare_digest`.
- Datos externos (Gmail, Drive, web) pasan por `_PATRONES_INYECCION` en
  brain.py antes de inyectarse al prompt.
- Rate limiting por teléfono en `rate_limiter.py`. No bypassar.
- Deduplicación de mensajes por `mensaje_id` (primero Postgres, fallback
  in-memory). Los proveedores reintentan webhooks: asume reentrega.

---

## 4. Stack y arquitectura (resumen)

- **Runtime**: Python 3.11+ · FastAPI + Uvicorn/Gunicorn
- **LLM principal**: `claude-sonnet-4-6` (Anthropic)
  - Fallbacks: DeepSeek, GPT-4o, Haiku (ver `agent/brain.py`)
- **DB**: PostgreSQL prod / SQLite dev · SQLAlchemy 2 async · Alembic
- **Queue**: Redis + **arq** (fallback `inproc` si no hay `REDIS_URL`)
- **Storage**: Cloudflare R2 (S3 compatible vía `aioboto3`) · fallback local
- **Pagos**: Stripe Checkout + webhook (ver `agent/billing.py`)
- **Imagen**: Google Gemini 2.5 Flash Image / Pro (ver `agent/creativos/imagen.py`)
- **WhatsApp**: Whapi.cloud (default), Meta Cloud API, Twilio
- **Deploy**: Render (web service + opcional background worker)

Ver `README.md` para el mapa completo de módulos.

---

## 5. Testing

```bash
pytest                    # 1237 tests, ~8 min
pytest -x --ff            # fail-fast
pytest -k <keyword>       # filtra por nombre
pytest --cov=agent        # con cobertura (CI: piso 46% + diff-cover 80% en código nuevo)
```

Reglas:
- Tests usan SQLite en archivo temporal (`tmp_path`) con fixtures que
  **recargan módulos con `importlib.reload`** tras setear env vars. Respeta
  ese patrón al añadir módulos que cachean estado en import-time.
- Mocks de httpx para proveedores externos (Gemini, OpenAI, Whapi). No
  hacer llamadas reales en tests.
- Tests asíncronos: `pytest-asyncio` en modo auto. Usa `async def` y
  `@pytest.mark.asyncio` solo si hace falta override.

---

## 6. Git y despliegue

- `main` es la rama de producción. Render redespliega el web service
  automáticamente en cada push.
- **No force-push a main.** Commits nuevos, no amends sobre commits ya
  pusheados.
- Commit messages en español, en imperativo, con scope:
  `feat(creativos): detección natural de solicitud de imagen`.
- Antes de commit: correr `pytest` completo. Si algo rompe, arreglar antes
  de pushear.

---

## 7. Cosas que NO hacer

- No escribir en español neutro gringo (“recomendamos”, “te sugerimos”).
  Prefiere imperativo directo.
- No agregar abstracciones “por si acaso”. El repo ya tiene fallbacks donde
  hace falta; no duplicar.
- No crear archivos Markdown de planning, notas de tareas, o resúmenes de
  sesión salvo que el usuario los pida explícitamente.
- No referirse a los primeros usuarios como “Fundadores”.
- No usar marco legal mexicano (LFPDPPP, IFT, etc.).
- No romper el patrón `preparar_X` / `confirmar_X` para tools pagadas o con
  efecto irreversible.
- No delegar al LLM comandos que ya tienen detección determinística en
  `main.py` (saldo, recargar, imagen, privacidad, STOP/START).

---

## 8. Endpoints admin útiles (diagnóstico)

Todos requieren `Authorization: Bearer $ADMIN_TOKEN`.

- `GET  /admin/metrics` — contadores in-memory
- `GET  /admin/jobs-recientes?telefono=...&limite=10` — estado de jobs
  creativos de un usuario (útil para debug de imagen)
- `POST /admin/seed-creditos?telefono=...&creditos=100&razon=...` — acreditar
  manualmente
- `GET  /admin/recordatorios?telefono=...` — ver recordatorios programados
- `GET  /admin/onboarding?telefono=...` — ver fase/paso del onboarding
- `POST /admin/onboarding/reset?telefono=...&fase=0&paso=0` — reiniciar
  onboarding
- `GET  /admin/inbound/token?telefono=...` — generar token de webhook
  inbound (Zapier/Make/n8n)
