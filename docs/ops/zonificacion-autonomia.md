# Zonificación de autonomía — qué puede tocar un agente sin humano

> Política operativa. Define **dónde** un agente de codificación (Claude Code,
> Codex, o cualquier worker) puede trabajar de forma autónoma y **dónde** se
> exige revisión humana antes del merge. Es el complemento de gobierno del gate
> de CI: el CI dice *"esto pasa las pruebas"*; esta política dice *"además, esto
> requiere — o no — un par de ojos humanos"*.
>
> Enganches: [CLAUDE.md](../../CLAUDE.md) (convenciones críticas),
> `high-critical-gates.md`, `permissions-model.md`, `risk-policy.md`,
> `RUN_LEDGER_POLICY.md`, y el exit dossier F (release safety case).

## 0. Principio rector

`main` es producción: Render redespliega en cada push. Más autonomía **no**
significa menos control — significa mover el cuello de botella del *tecleo* a la
*verificación*, y hacer esa verificación barata, automática e **imposible de
saltar**.

Regla base, heredada del kernel `agent/entorno.py` (fail-closed): **lo no
clasificado se trata como ROJO.** Si dudas de la zona de un archivo, es rojo
hasta que se clasifique explícitamente aquí.

La autonomía de un cambio = `min(zona del archivo más sensible que toca)`. Un PR
que toca `tests/` (verde) **y** `agent/billing.py` (rojo) es ROJO.

## 1. Las tres zonas

| Zona | Significado | Gate para mergear |
| --- | --- | --- |
| 🟢 **VERDE** | Sin efecto en runtime de producción, o puramente verificable por CI sin tocar superficies sensibles. | CI verde (pytest + landing + lint). Un agente puede abrir, y otro agente/IA puede aprobar. |
| 🟡 **GRIS** | Efecto real pero acotado y gateable. Orquestación que coordina acciones sensibles sin ejecutarlas/cobrar por sí misma, envíos gateados, trabajo pagado, integraciones, esquema/migraciones. | CI verde **+ el subset de tests del módulo verde + revisión humana focalizada** en el invariante en juego (ver `suggested_gate` por archivo). |
| 🔴 **ROJO** | Dinero, enforcement TCPA/opt-out, verificación de firma/HMAC/tokens, cifrado, clasificación de riesgo, el único ejecutor con efecto externo real, el system prompt + sanitizer anti-inyección, el orden de defensa de `main.py`, texto legal vinculante. | **Humano obligatorio, aunque la suite esté verde.** Diff revisado línea por línea por Celestino. |

## 2. 🟢 VERDE — autonomía permitida (gate = CI verde)

- `tests/` — **agregar** cobertura es seguro (la red de seguridad la hace
  visible). ⚠️ excepción crítica: **aflojar/borrar asserts que cubren rojo, o
  editar `.github/workflows/*` para saltar pruebas, es ROJO** (debilita el
  propio gate). Ver §4.
- `docs/`, `README.md` — documentación, planes, auditorías. Sin runtime.
- `agent/observability.py`, `agent/logging_config.py` — observabilidad/logging
  puro (gateado por `test_observability_y_catalog.py`, `test_logging.py`).
- `scripts/validate_agent_runs.py` y `.github/workflows/agent-runs-validation.yml`
  — tooling de CI auxiliar (se valida a sí mismo). *(Editar `tests.yml` para
  debilitar el gate → rojo.)*
- `landing/app/engineering/` — panel de ingeniería personal, read-only, login
  separado del usuario final.
- Archivos solo-tipos: `landing/lib/*-types.ts`, `agent/.../*` declarativos de
  tipos sin lógica.

## 3. 🔴 ROJO — humano obligatorio

**Dinero / billing**
- `agent/billing.py` — cobrar/acreditar/`cobrar_o_rechazar`, idempotencia del
  webhook Stripe por `stripe_session_id`, `verificar_firma_stripe`, audit trail
  en `transacciones_credito`.
- `agent/automation/credits.py` — reserva write-ahead + reconciliación post-crash.
- `agent/billing_commands.py` — comandos deterministas de billing (saldo/recargar).
- `landing/app/api/webhook/route.ts`, `landing/app/api/checkout/route.ts`,
  `landing/app/api/billing-portal/route.ts`, `landing/app/api/cancel-subscription/route.ts`,
  `landing/lib/internal-bridge.ts`, `landing/lib/stripe.ts` — entrada de dinero y
  puente firmado HMAC al backend.

**TCPA / consentimiento / envío saliente**
- `agent/envio_gate.py` — gate central de salida (opt-out fail-closed, quiet
  hours, límite diario, supresión post-STOP). Riesgo TCPA $500–1500/mensaje.
- `agent/automation/consent_terceros.py` — política de contacto a terceros
  (block-until-consent), copy obligatorio con PARAR.
- `agent/automation/executors/send_message.py` — **único ejecutor HIGH real**:
  envía WhatsApp de verdad. Efecto externo irreversible.
- `agent/automation/permissions.py` — clasificación de riesgo
  (LOW/MEDIUM/HIGH/CRITICAL), fail-closed. Reclasificar una acción afloja la
  autonomía entera.
- `landing/app/api/automation/acciones/[id]/high-confirmar/route.ts` — el trigger
  humano-en-el-loop del único camino con efecto externo.

**Cerebro LLM / orden de defensa**
- `agent/brain.py` — `_PATRONES_INYECCION` + `_sanitizar_datos_externos`, system
  prompt, few-shot, y el contrato `preparar_X`/`confirmar_X`.
- `config/prompts.yaml` — **editar esto = editar el system prompt.**
- `agent/main.py` — routing crítico: STOP/START TCPA antes de dedup/rate-limit,
  dedup atómico por `mensaje_id`, verificación de firmas de webhooks, tokens
  admin con `hmac.compare_digest`, comandos deterministas pre-LLM, endpoints
  `/privacy/export` y `/privacy/delete`.
- `agent/entorno.py` — kernel fail-closed: decide si se verifican firmas, se
  cifran tokens y se exigen secrets. Un cambio puede desactivar **en silencio**
  todos los controles.

**Seguridad / cripto / auth**
- `agent/rate_limiter.py` (CLAUDE.md: no bypassar), `agent/inbound_tokens.py`
  (HMAC de webhooks Zapier/Make/n8n), `agent/crypto.py` (Fernet de tokens OAuth),
  `agent/dashboard_lockout.py` (anti fuerza-bruta), `agent/readiness.py`
  (readiness de secrets al arranque).
- `landing/auth.ts`, `landing/lib/auth-lockout-bridge.ts`,
  `landing/lib/dashboard-auth.ts`, `landing/lib/auth-matcher.ts`.

**Proveedores de mensajería**
- `agent/providers/whapi.py`, `agent/providers/meta.py`, `agent/providers/base.py`
  — verificación de firma de webhook + envío real.

**Legal**
- `agent/legal_pages.py` — Privacy/ToS/DMCA vinculantes (CCPA/CPRA).

## 4. 🟡 GRIS — efecto acotado (gate = CI del módulo verde + revisión humana focalizada)

| Archivo / módulo | Invariante a vigilar | Gate |
| --- | --- | --- |
| `agent/automation/execution.py` | claim atómico, reserva de créditos, bloqueo de CRITICAL, ruteo al ejecutor HIGH | suite `automation` verde + revisar que no reclasifica riesgo ni salta el claim/aprobación |
| `agent/automation/action_center.py` | transiciones de estado, idempotency_key (aprobar/marcar_running preceden al HIGH) | `test_automation_action_center` + `..._next_required_action` verdes |
| `agent/automation/missions.py` | golden path recuperar-lead → camino HIGH; reason-codes | tests de misiones verdes; cambio de flujo de confirmación → firma humana |
| `agent/automation/opportunities.py`, `playbooks.py` | riesgo derivado del playbook se propaga a la autonomía | tests respectivos verdes; cambio de campo `riesgo` → humano |
| `agent/automation/prompts.py`, `agent/automation/scheduler.py`, `pruning.py`, `audit.py`, `models.py` | prompts de ejecutores; reconciliación (opt-in); borrado conservador; audit log; esquema | subset de tests verde; migración Alembic revisada para `models.py` |
| `agent/proactivity.py`, `agent/scheduler.py`, `agent/welcome.py` | envíos gateados (pasan por `envio_gate`) pero TCPA-adyacentes | tests TCPA/recurrencias verdes; debe seguir pasando por el gate |
| `agent/creativos/`, `agent/jobs/` | trabajo pagado; patrón `preparar_X`/`confirmar_X`; idempotencia de cola | `test_creativos_*`/`test_jobs` verdes; revisar punto de cobro |
| `agent/creativos/comandos.py`, `agent/comandos_info.py` | detección determinista pre-LLM; no colisionar con routing de `main.py` | revisión de regex/routing + CI verde |
| `agent/gmail.py`, `google_calendar.py`, `google_drive.py`, `google_sheets.py`, `google_contacts.py`, `google_tasks.py` | `preparar_/confirmar_` con efecto externo; sanitizar datos externos antes de inyectar al prompt | tests Google verdes; escritura → revisión humana |
| `agent/memory.py` | dedup por `mensaje_id`, claims atómicos, esquema | `test_dedup_atomico` verde; migración Alembic si toca esquema |
| `agent/tools.py`, `agent/tools_catalog.py` | catálogo expuesto al LLM; nivel de riesgo por tool | `test_brain_tools`/`test_observability_y_catalog` verdes; cambio de nivel de riesgo → humano |
| `agent/presupuesto_runtime.py` | RuntimeBudgetGuard, kill-switches (criterio Hermes) | `test_presupuesto_runtime` + `test_budget_*` (incl. adversarial) verdes |
| `agent/business/`, `agent/onboarding.py`, `agent/reporting.py`, `agent/learning.py` | quotas/finanzas, flujo de onboarding, qué/ a quién se exporta (PII), ajuste persistente de comportamiento | CI respectivo verde; revisión si cambia esquema, quotas, destino de export o sanitización |
| `alembic/` | toda migración altera el esquema de producción | **aprobación humana obligatoria** por migración + revisar up/down + suite verde contra el nuevo esquema |
| `agent/web_agent/` | navega/consume datos externos (superficie de inyección) | revisión si amplía capacidades; sanitizar todo contenido externo |
| `enhanced/` | legacy/mixto — `execution.py`/`system_processor.py` podrían disparar acciones | **clasificar por archivo antes de tocar**: diagnostics/insights → verde; ejecución → rojo |
| `landing/app/dashboard/`, `landing/lib/automation-bridge.ts`, `landing/app/api/automation/acciones/`, resto de `landing/lib/` | UI/bridges acoplados a aprobar/ejecutar HIGH; identificadores solo server-side | vitest del landing verde; `*-bridge`/`stripe.ts` → rojo, `*-types`/`*-data` read-only → verde |

## 5. Reglas transversales (ninguna edición autónoma las viola)

1. **No aflojar el gate.** Un agente no puede reducir/borrar asserts en
   `test_billing*`, `test_tcpa*`, `test_dedup*`, `test_security_fixes`,
   `test_providers*`, `test_automation_*high*`/`credits`/`execution`,
   `test_fail_closed_entorno`, `test_readiness_secrets`, ni editar
   `.github/workflows/*` para saltar pruebas. → ROJO (humano).
2. **No romper `preparar_X`/`confirmar_X`** para tools pagadas o irreversibles
   (CLAUDE.md §3.1). Verbos literales.
3. **No delegar al LLM comandos con detección determinista** (saldo, recargar,
   imagen, STOP/START, privacidad) — CLAUDE.md §3.2.
4. **Invariantes con `raise` explícito, nunca `assert`** (producción corre bajo
   `-O`; los assert desaparecen → fail-open silencioso).
5. **Identificadores (subscription_id, customerId) solo desde la sesión
   server-side**, jamás del body/query del cliente.

## 6. Cómo se usa

- El prompt de cualquier agente autónomo / del revisor IA en CI debe incluir esta
  zonificación + las reglas §5.
- PR que toca solo 🟢 → puede mergear con CI verde (humano opcional).
- PR que toca 🟡 → CI verde + Celestino revisa el invariante listado.
- PR que toca 🔴 → Celestino revisa línea por línea; para acciones HIGH/CRITICAL
  aplica además el exit dossier F.
- Sugerido para CI: un check que falle si un PR sin label `human-reviewed`
  modifica archivos de la lista 🔴 o reduce asserts en los tests de §5.1.
