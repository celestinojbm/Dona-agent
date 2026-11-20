# FEATURE_MAP — Dona-agent

> Mapa de funcionalidades para agentes y humanos: **qué hace Dona, dónde vive
> cada cosa, qué tests la cubren y cómo verificarla** antes de entregar un
> cambio. Complementa a [README.md](README.md), [CLAUDE.md](CLAUDE.md) y a la
> política de autonomía [docs/ops/zonificacion-autonomia.md](docs/ops/zonificacion-autonomia.md).
>
> Zona = la de `zonificacion-autonomia.md` (🟢 verde · 🟡 gris · 🔴 roja). Lo no
> clasificado se trata como 🔴. Recuerda: **`main` es producción** (Render
> redespliega en cada push).

## Cómo verificar (general)

```bash
# Backend (Python 3.12) — SQLite temporal, sin llamadas reales a proveedores
pip install -r requirements.txt -r requirements-dev.txt
pytest                         # suite completa (CI: "Suite completa (pytest)")
pytest tests/test_smoke_e2e.py # humo extremo a extremo del webhook → respuesta
pytest -k <palabra>            # subset de una funcionalidad
ruff check agent               # CI: "Ruff (lint backend)"
alembic upgrade head && alembic downgrade -1   # CI: "Cadena Alembic"

# Landing / dashboard (Next.js) — desde landing/
npm ci && npm run lint && npm run typecheck && npm test && npm run build   # CI: "Landing (...)"
```

Checks obligatorios en `main` (branch protection): `Suite completa (pytest)`,
`Cadena Alembic (head único + upgrade/downgrade)`, `gitleaks (secret scan)`,
`pip-audit (deps Python)`, `Validar agent-runs offline`. `Landing (...)` y
`Ruff (...)` corren solo cuando cambian sus carpetas (filtros de `paths`).

## Funcionalidades

### 1. Entrada de mensajes WhatsApp y routing crítico — 🔴
- **Archivos:** `agent/main.py` (webhooks, STOP/START TCPA antes de dedup y
  rate-limit, comandos deterministas pre-LLM, `/privacy/*`),
  `agent/providers/{base,whapi,meta}.py` (firma de webhook + envío real),
  `agent/rate_limiter.py`, `agent/memory.py` (dedup por `mensaje_id`).
- **Tests:** `tests/test_smoke_e2e.py`, `tests/test_providers.py`,
  `tests/test_dedup_atomico.py`, `tests/test_rate_limiter.py`,
  `tests/test_tcpa_stop_durable.py`, `tests/test_optout_normalizacion.py`,
  `tests/test_security_fixes.py`, `tests/test_admin_auth_bearer_only.py`,
  `tests/test_main_request_id_y_admin_catalog.py`.
- **Verificar:** `pytest tests/test_smoke_e2e.py tests/test_providers.py tests/test_dedup_atomico.py tests/test_tcpa_stop_durable.py`.

### 2. Cerebro LLM, tools y anti-inyección — 🔴 (`brain.py`, `config/prompts.yaml`) / 🟡 (catálogo)
- **Archivos:** `agent/brain.py` (system prompt, `_sanitizar_datos_externos`,
  contrato `preparar_X`/`confirmar_X`), `config/prompts.yaml`, `agent/llm.py`,
  `agent/tools_catalog.py`, `agent/tools_registry.py`, `agent/tool_handlers/`,
  `agent/sanitize.py`, `agent/prompt_cache.py`, `agent/memory_summary.py`.
- **Tests:** `tests/test_brain_tools.py`, `tests/test_sanitizar_inyeccion.py`,
  `tests/test_sanitizacion_contactos_tareas_vision.py`, `tests/test_tools_registry.py`,
  `tests/test_observability_y_catalog.py`, `tests/test_prompt_cache_f16.py`,
  `tests/test_memory_summary.py`.
- **Verificar:** `pytest tests/test_brain_tools.py tests/test_sanitizar_inyeccion.py tests/test_tools_registry.py`.

### 3. Multi-modelo (selección, presupuesto, combinación) — sin clasificar → 🔴
- **Archivos:** `agent/multi_model/` (`catalogo.py`, `seleccion.py`,
  `combinacion.py`, `providers.py`, `preferencias.py`, `sugerencias.py`),
  UI en `landing/components/selector-modelo*.tsx`, `comparacion-modelos*.tsx`.
- **Tests:** `tests/test_multi_model_f23.py`, `landing/components/selector-modelo.test.tsx`,
  `landing/components/comparacion-modelos.test.tsx`.
- **Verificar:** `pytest tests/test_multi_model_f23.py`; en `landing/`: `npx vitest run components/selector-modelo.test.tsx components/comparacion-modelos.test.tsx`.

### 4. Presupuesto de runtime y medición de tokens — 🟡
- **Archivos:** `agent/presupuesto_runtime.py` (RuntimeBudgetGuard, kill-switches).
- **Tests:** `tests/test_presupuesto_runtime.py`, `tests/test_budget_adversarial.py`,
  `tests/test_budget_wire_brain.py`, `tests/test_budget_wire_tools.py`,
  `tests/test_budget_wire_aux.py`, `tests/test_medicion_uso_tokens.py`.
- **Verificar:** `pytest -k "budget or presupuesto or medicion"`.

### 5. Billing, créditos y Stripe — 🔴
- **Archivos:** `agent/billing.py` (`cobrar_o_rechazar`, webhook idempotente,
  `verificar_firma_stripe`), `agent/billing_commands.py`, `agent/automation/credits.py`,
  `agent/tarifa.py`, `agent/recibos.py`; landing: `landing/app/api/{webhook,checkout,billing-portal,cancel-subscription}/route.ts`,
  `landing/lib/stripe.ts`, `landing/lib/internal-bridge.ts`.
- **Tests:** `tests/test_billing.py`, `tests/test_billing_commands.py`,
  `tests/test_dinero_atomico.py`, `tests/test_creditos_de_plan.py`,
  `tests/test_procesar_evento_suscripcion.py`, `tests/test_suscripcion_stripe_models.py`,
  `tests/test_main_internal_stripe.py`, `tests/test_internal_stripe_topup_dispatch.py`,
  `tests/test_recibos_f3.py`, `tests/test_automation_creditos_reservas.py`,
  `landing/app/api/webhook/route.test.tsx`, `landing/app/api/checkout/route.test.tsx`,
  `landing/app/checkout/checkout-client.test.tsx`.
- **Verificar:** `pytest -k "billing or dinero or credito or stripe or suscripcion or recibos"`; en `landing/`: `npx vitest run app/api/webhook app/api/checkout`.

### 6. Automatización — Action Center, oportunidades, misiones — 🟡 (🔴 `permissions.py`, `send_message.py`, `consent_terceros.py`)
- **Archivos:** `agent/automation/` (`action_center.py`, `execution.py`,
  `opportunities.py`, `playbooks.py`, `missions.py`, `permissions.py`,
  `scheduler.py`, `pruning.py`, `audit.py`, `models.py`, `costos.py`,
  `executors/send_message.py`), dashboard: `landing/app/dashboard/seccion-action-center*`,
  `seccion-oportunidades*`, `landing/lib/automation-bridge.ts`,
  `landing/app/api/automation/acciones/[id]/high-confirmar/route.ts`.
- **Tests:** `tests/test_automation_*.py` (action_center, execution, permissions,
  misiones*, opportunities, playbooks, scheduler, pruning, audit*, send_message_high,
  high_audit_log, executors_real, next_required_action, endpoints, models,
  perfil_estado, creditos_reservas), `tests/test_exec_segundo_factor.py`,
  `landing/app/api/automation/acciones/[id]/high-confirmar/route.test.tsx`,
  `landing/lib/automation-bridge.test.ts`, `landing/app/dashboard/seccion-action-center.test.tsx`,
  `landing/app/dashboard/seccion-oportunidades.test.tsx`.
- **Verificar:** `pytest -k automation`; en `landing/`: `npx vitest run lib/automation-bridge.test.ts app/dashboard/seccion-action-center.test.tsx`.

### 7. Envío saliente, TCPA y consentimiento — 🔴 (`envio_gate.py`) / 🟡 (proactividad)
- **Archivos:** `agent/envio_gate.py`, `agent/automation/consent_terceros.py`,
  `agent/proactivity.py`, `agent/scheduler.py`, `agent/welcome.py`.
- **Tests:** `tests/test_envio_gate.py`, `tests/test_consent_terceros.py`,
  `tests/test_consent_terceros_bordes.py`, `tests/test_tcpa_stop_durable.py`,
  `tests/test_proactivity_comandos.py`, `tests/test_recurrencias_tope.py`,
  `tests/test_scheduler_claims.py`, `tests/test_welcome_premium.py`.
- **Verificar:** `pytest -k "envio_gate or consent or tcpa or proactivity or recurrencias or scheduler or welcome"`.

### 8. Autonomía con autorizaciones y reservas — sin clasificar → 🔴
- **Archivos:** `agent/autonomia/` (`politica.py`, `autorizaciones.py`,
  `reservas.py`, `comandos.py`, `models.py`).
- **Tests:** `tests/test_autonomia_f1.py`.
- **Verificar:** `pytest tests/test_autonomia_f1.py`.

### 9. Gestión del negocio (CRM, finanzas, pedidos, cotizaciones, contenido, reportes) — 🟡
- **Archivos:** `agent/business/` (`crm.py`, `finanzas.py`, `pedidos.py`,
  `cotizaciones.py`, `contenido.py`, `reportes.py`, `quotas.py`,
  `onboarding_negocio.py`), `agent/onboarding.py`, `agent/reporting.py`;
  dashboard `landing/app/dashboard/seccion-reportes*`, `landing/lib/reportes-bridge.ts`.
- **Tests:** `tests/test_business.py`, `tests/test_quotas.py`,
  `tests/test_onboarding_negocio.py`, `tests/test_onboarding_negocio_extendido.py`,
  `tests/test_reporting.py`, `tests/test_reporting_destino.py`,
  `tests/test_internal_reportes.py`, `landing/lib/reportes-bridge.test.ts`,
  `landing/app/dashboard/seccion-reportes.test.tsx`.
- **Verificar:** `pytest -k "business or quotas or onboarding or reporting or reportes"`.

### 10. Recordatorios en lenguaje natural — sin clasificar → 🔴
- **Archivos:** `agent/reminders_nl.py`, `agent/scheduler.py`.
- **Tests:** `tests/test_reminders_nl.py`, `tests/test_reminders_nl_bordes.py`.
- **Verificar:** `pytest -k reminders`.

### 11. Creativos (imagen, video, voz, PDF) y cola de trabajos — 🟡
- **Archivos:** `agent/creativos/` (`imagen.py`, `video.py`, `video_avatar.py`,
  `voz.py`, `pdf.py`, `bg_remove.py`, `prompt_imagen.py`, `prompt_video.py`,
  `pendientes.py`, `comandos.py`), `agent/jobs/` (`queue.py`, `worker.py`,
  `handlers_creativos.py`), `agent/storage.py`.
- **Tests:** `tests/test_creativos_imagen.py`, `tests/test_creativos_ajustar.py`,
  `tests/test_creativos_comandos_render.py`, `tests/test_creativos_prompt_imagen.py`,
  `tests/test_creativos_prompt_video.py`, `tests/test_pendientes_creativos.py`,
  `tests/test_jobs.py`, `tests/test_jobs_handlers_creativos.py`, `tests/test_storage.py`,
  `tests/test_internal_assets.py`, `landing/lib/assets-bridge.test.ts`.
- **Verificar:** `pytest -k "creativos or jobs or storage or assets"`.

### 12. Integraciones Google (Gmail, Calendar, Drive, Contacts, Tasks, Sheets) — 🟡
- **Archivos:** `agent/gmail.py`, `agent/google_calendar.py`, `agent/google_drive.py`,
  `agent/google_contacts.py`, `agent/google_tasks.py`, `agent/google_sheets.py`,
  `agent/google_reauth.py`, `agent/tool_handlers/{gmail,google_tasks}.py`,
  `agent/automation/{email_actions,email_audit,email_crypto}.py`.
- **Tests:** `tests/test_gmail_query.py`, `tests/test_gmail_adjuntos.py`,
  `tests/test_google_drive.py`, `tests/test_google_contacts.py`,
  `tests/test_google_tasks.py`, `tests/test_google_sheets.py`,
  `tests/test_email_*.py`, `tests/test_ccpa_borrado_gcal_exacto.py`.
- **Verificar:** `pytest -k "gmail or google or email"`.

### 13. Voz, visión, emoción y ubicación — sin clasificar → 🔴
- **Archivos:** `agent/transcriber.py`, `agent/tts.py`, `agent/vision.py`,
  `agent/emotion.py`, `agent/location.py`, `agent/real_world.py`.
- **Tests:** `tests/test_transcriber.py`, `tests/test_tts.py`,
  `tests/test_voice_reenviar.py`, `tests/test_emotion_deteccion.py`,
  `tests/test_location_deteccion.py`, `tests/test_real_world.py`.
- **Verificar:** `pytest -k "transcriber or tts or voice or emotion or location or real_world"`.

### 14. Memoria vectorial y aprendizaje — 🟡
- **Archivos:** `agent/memory.py`, `agent/vector_memory.py`, `agent/learning.py`.
- **Tests:** `tests/test_vector_memory.py`, `tests/test_learning_patrones.py`,
  `tests/test_dedup_atomico.py`.
- **Verificar:** `pytest -k "vector_memory or learning or dedup"`.

### 15. Plan vivo y primer valor — sin clasificar → 🔴
- **Archivos:** `agent/plan_vivo/`, `agent/primer_valor/`,
  `landing/components/plan-vivo-panel*.tsx`, `landing/components/primer-valor-hero*.tsx`.
- **Tests:** `tests/test_plan_vivo_f14.py`, `tests/test_primer_valor_f12.py`,
  `landing/components/plan-vivo-panel.test.tsx`, `landing/components/primer-valor-hero.test.tsx`.
- **Verificar:** `pytest tests/test_plan_vivo_f14.py tests/test_primer_valor_f12.py`.

### 16. Agente web (navegación) — 🟡
- **Archivos:** `agent/web_agent/` (`runner.py`, `session.py`, `registro.py`, `tareas/`).
- **Tests:** `tests/test_web_agent.py`, `tests/test_web_agent_tareas.py`.
- **Verificar:** `pytest -k web_agent`.

### 17. Seguridad, cifrado, entorno fail-closed y readiness — 🔴
- **Archivos:** `agent/entorno.py`, `agent/readiness.py`, `agent/crypto.py`,
  `agent/inbound_tokens.py`, `agent/dashboard_lockout.py`, `agent/rls_policy.py`,
  `agent/efectos.py`.
- **Tests:** `tests/test_fail_closed_entorno.py`, `tests/test_tema0_failclosed.py`,
  `tests/test_readiness_secrets.py`, `tests/test_crypto.py`, `tests/test_crypto_cifrado.py`,
  `tests/test_crypto_roundtrip.py`, `tests/test_inbound_tokens.py`,
  `tests/test_dashboard_lockout.py`, `tests/test_security_fixes.py`,
  `tests/test_efectos_arranque.py`, `tests/test_salida_fase0.py`, `tests/security/`.
- **Verificar:** `pytest -k "fail_closed or failclosed or readiness or crypto or inbound or lockout or security"`.

### 18. Privacidad y legal (CCPA/CPRA, ToS) — 🔴
- **Archivos:** `agent/legal_pages.py`, endpoints `/privacy/export` y
  `/privacy/delete` en `agent/main.py`; landing `landing/app/politica-de-privacidad/`,
  `landing/app/terminos-y-condiciones/`.
- **Tests:** `tests/test_ccpa_solicitud_verificada.py`, `tests/test_ccpa_borrado_gcal_exacto.py`,
  `tests/test_email_audit_privacidad.py`.
- **Verificar:** `pytest -k ccpa`.

### 19. Comandos informativos deterministas — 🟡
- **Archivos:** `agent/comandos_info.py`, `agent/creativos/comandos.py`.
- **Tests:** `tests/test_comandos_info.py`, `tests/test_comandos_info_estado.py`,
  `tests/test_creativos_comandos_render.py`.
- **Verificar:** `pytest -k comandos`.

### 20. Dashboard web, login y chat interno (landing) — 🟡 (🔴 auth y bridges firmados)
- **Archivos:** `landing/app/dashboard/`, `landing/app/login/`, `landing/auth.ts`,
  `landing/lib/{dashboard-auth,auth-matcher,auth-lockout-bridge,pausa,panel-auth,panel-bridge,chat-bridge,backend-url,control-room,control-room-data}.ts`,
  `landing/app/api/{chat,dashboard-data,reportes,assets,whatsapp-webhook}/`,
  backend `tests/test_internal_chat.py`, `tests/test_main_internal_usuario_resumen.py`.
- **Tests:** `landing/app/dashboard/*.test.tsx`, `landing/lib/*.test.ts`,
  `landing/app/api/chat/route.test.tsx`, `landing/app/api/pausa-rutas.test.tsx`,
  `landing/app/api/whatsapp-webhook/route.test.tsx`, `tests/test_internal_chat.py`,
  `tests/test_usuarios.py`.
- **Verificar:** en `landing/`: `npm test`; navegar `npm run dev` → `/login` y `/dashboard`.

### 21. Landing pública de marketing — 🟡
- **Archivos:** `landing/app/page.tsx`, `landing/app/useCinematicMotion.ts`,
  `landing/components/`, `landing/app/{soporte,success,cancel,checkout,prototipo}/`.
- **Tests:** `landing/app/page.test.tsx`, `landing/app/checkout/checkout-client.test.tsx`.
- **Verificar:** en `landing/`: `npm run build && npm start` → abrir `/`; en producción `https://usadona.com` debe responder 200.

### 22. Panel de ingeniería personal — 🟢
- **Archivos:** `landing/app/engineering/`, `landing/app/api/engineering/`.
- **Tests:** cubierto indirectamente por `npm test` / `npm run build` del landing.
- **Verificar:** `npm run build` en `landing/`.

### 23. Observabilidad y logging — 🟢
- **Archivos:** `agent/observability.py`, `agent/logging_config.py`.
- **Tests:** `tests/test_observability_y_catalog.py`, `tests/test_logging.py`.
- **Verificar:** `pytest tests/test_observability_y_catalog.py tests/test_logging.py`.

### 24. Migraciones de base de datos — 🟡 (aprobación humana por migración)
- **Archivos:** `alembic/`, `alembic.ini`, `migration.py`.
- **Tests:** CI `Cadena Alembic (head único + upgrade/downgrade)` (`.github/workflows/alembic.yml`).
- **Verificar:** `alembic heads` (debe haber uno) y `alembic upgrade head && alembic downgrade -1 && alembic upgrade head`.

### 25. Validación de corridas de agentes (CI auxiliar) — 🟢
- **Archivos:** `scripts/validate_agent_runs.py`, `.github/workflows/agent-runs-validation.yml`.
- **Tests:** `tests/test_validate_agent_runs.py`; CI `Validar agent-runs offline`.
- **Verificar:** `pytest tests/test_validate_agent_runs.py`.

### 26. Módulo legacy `enhanced/` — clasificar por archivo antes de tocar
- **Archivos:** `enhanced/`.
- **Tests:** `tests/test_safe_module.py` (parcial).
- **Verificar:** no tocar sin clasificar primero (ver §4 de la zonificación).

## Mantener este mapa

- Al añadir un módulo o test nuevo, agrega o actualiza su fila aquí en la misma PR.
- Si una funcionalidad queda "sin clasificar", proponer su zona en
  `docs/ops/zonificacion-autonomia.md` (cambio de política → Celestino).
