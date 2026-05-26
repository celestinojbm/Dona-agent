# Run Ledger — RUN-2026-05-26-high-audit-log

## 0. Metadatos

- Fecha: 2026-05-26
- Responsable/orquestador: Hermes
- Agentes participantes previstos: Claude Code (implementador principal), Hermes (orquestación/verificación), Codex (revisión read-only), Browser Use/Tavily (referencias read-only)
- Branch: `feat/high-audit-log`
- PR: pendiente
- Estado: completado local / PR pendiente

## 1. Objetivo exacto

Agregar trazabilidad persistente y testeada para previews, confirmaciones y ejecución de acciones HIGH, empezando por `enviar_mensaje_whatsapp`, sin habilitar envíos reales nuevos ni tocar proveedores/secrets/deploy.

## 2. Riesgo

- Nivel: MEDIUM-HIGH
- Justificación: toca auditoría, permisos, créditos/reservas y ruta HIGH; no debe abrir ejecución genérica ni filtrar PII/secrets.
- Capa de auditoría dominante: permisos / seguridad / datos / costo / observabilidad / UX

## 3. Scope permitido

- Archivos permitidos esperados:
  - `agent/automation/**`
  - `agent/main.py` solo si hace falta conectar helpers existentes de endpoints HIGH
  - `tests/test_automation_*.py` y tests focales relacionados
  - `landing/lib/automation-*` y `landing/app/dashboard/seccion-action-center*` solo si hay UI mínima necesaria
  - `landing/lib/control-room-*` solo si se expone resumen estático/local sin live APIs
  - `docs/ops/agent-runs/2026-05-26-high-audit-log/*`
- Sistemas permitidos: repo local en rama; tests con mocks/fakes; investigación pública read-only con Browser Use/Tavily.
- Acciones permitidas: implementar helpers/modelos internos, registrar eventos auditables, pruebas unitarias/focales, revisión read-only.

## 4. No-scope explícito

- Prohibido tocar: `.env`, secretos, credenciales, deploy settings, workflows CI, Stripe live, Meta/WhatsApp provider real, DB prod, scheduler, auth/billing/webhooks/RLS.
- Prohibido activar scheduler o proveedores reales.
- Prohibido permitir ejecución HIGH por endpoint genérico.
- Prohibido loguear tokens, números completos o cuerpos completos de mensajes en audit logs no estrictamente owner-scoped.
- Prohibido merge automático.

## 5. Contexto que se va a leer

| Fuente | Motivo | Leído |
| --- | --- | --- |
| `AGENTS.md` | Reglas globales | [x] |
| `CLAUDE.md` | Convenciones técnicas | [x] |
| `docs/vision/DONA_CANONICAL_CONTEXT.md` | Canon de producto | [x] |
| `docs/ops/agent-runs/2026-05-25-pr56-high-dedicated-confirmation/*` | Estado previo HIGH | [ ] |
| Archivos `agent/automation/**` y tests | Entender implementación actual | [ ] |
| Referencias Stripe/Vercel/Linear | Patrones audit/control-room | [x] |

## 6. Estado inicial

- Workspace msi: `C:/Users/celes/Dona-current`
- Branch inicial: `main` limpio en `706191e`
- Branch de trabajo: `feat/high-audit-log`
- Workspace VPS: `/root/projects/Dona-agent` limpio en `main` `706191e5`
- Credencial prevista: PR_WRITE para push/PR desde msi; sin DEPLOY/ADMIN/secrets.

## 7. Supuestos

- El confirmador HIGH de PR #56 ya está mergeado y probado.
- Control Room lee agent-runs estáticos, no observabilidad viva.
- Audit log puede empezar como persistencia/test local en backend antes de UI completa.
- Browser Use y Tavily se usan solo para inspiración pública/read-only.

## 8. Plan paso a paso

1. Investigar referencias públicas con Tavily/Browser Use y extraer criterios mínimos.
2. Pedir a Claude Code implementar un cambio acotado en la rama.
3. Mantener endpoint genérico HIGH bloqueado.
4. Agregar audit events para preview/confirmación/rechazo/claim/éxito/fallo/duplicado.
5. Persistir/registrar costo estimado mostrado y estado de reserva/créditos donde aplique.
6. Agregar tests backend primero; UI mínima sólo si el backend queda sólido.
7. Verificar diff, tests focales, secret scan y `git diff --check`.
8. Codex review read-only.
9. PR sin merge automático.

## 9. Referencias extraídas con plugins

- Stripe Activity Logs: eventos de seguridad con actor, timestamp, recursos afectados, metadata contextual, filtros por action group/type, retención explícita.
- Vercel Activity/Audit Logs: timeline cronológico; actor, tipo de evento, cuenta, timestamp exacto; privacidad/acceso restringidos; exports separados para auditoría enterprise.
- Linear (Browser Use intento read-only): el acceso visual live a `linear.app` tuvo timeout, pero se conserva criterio de UI sobria: dark mode real, bordes sutiles, acento único, metadata densa, badges/chips de estado.

## 10. Herramientas permitidas

| Herramienta | Uso permitido | Límite |
| --- | --- | --- |
| Claude Code | Implementación | Sin commit/push/secrets/deploy/provider real |
| Codex | Revisión read-only | No editar |
| Tavily | Research público | No tratar como verdad automática |
| Browser Use | Observación pública read-only | No login/formularios/compras |
| pytest/npm | Tests focales | Sin llamadas reales externas |
| git/gh | Branch/PR/checks | No merge automático |

## 11. Pruebas/verificaciones previstas

- `pytest tests/test_automation_send_message_high.py tests/test_automation_endpoints.py tests/test_automation_execution.py tests/test_automation_creditos_reservas.py tests/test_automation_action_center.py -q`
- Tests nuevos de audit log HIGH.
- Si toca frontend: `cd landing && npm test -- automation-bridge.test.ts high-confirmar/route.test.tsx seccion-action-center.test.tsx`
- `python scripts/validate_agent_runs.py` si se indexa el run al final.
- `git diff --check`
- Secret/PII scan count-only.

## 12. Aprobación requerida

- Aprobación recibida: Celestino aprobó Run Ledger para audit log HIGH y pidió aprovechar plugins recién activados.
- Aprobación pendiente: implementación exacta puede avanzar dentro de este scope; cualquier secreto/deploy/provider real/scheduler/producción requiere nueva aprobación explícita.

## 13. Rollback esperado

- Antes de merge: cerrar PR/borrar rama.
- Después de merge: revert del commit/PR.
- Sin feature flag/env nuevo previsto.

## 14. Estado final

- Estado: completado local / PR pendiente
- PR/commit/evidencia: pendiente
- Estado: completado local / PR pendiente
- Evidencia local:
  - Claude Code hizo primer pase; Hermes corrigió hallazgos de seguridad.
  - Codex read-only bloqueó varias rondas por orden de claim, sanitización, IDOR y contaminación de audit; la revisión final quedó APROBADO.
  - Tests focales: `109 passed`.
  - `python scripts/validate_agent_runs.py`: `agent-runs OK: 7 runs`.
  - `git diff --check`: OK.
  - Secret scan de archivos modificados: `secret_scan_hits: 0`.
- Próxima acción: commit, push y abrir PR para revisión/merge manual.


## 15. Ejecución real

### 15.1 Archivos modificados

- `agent/automation/audit.py`
- `agent/automation/execution.py`
- `agent/automation/executors/send_message.py`
- `agent/main.py`
- `tests/test_automation_high_audit_log.py`
- `tests/test_automation_send_message_high.py`
- `docs/ops/agent-runs/2026-05-26-high-audit-log/run-ledger.md`
- `docs/ops/agent-runs/2026-05-26-high-audit-log/cost-ledger.md`
- `docs/ops/agent-runs/2026-05-26-high-audit-log/tool-ledger.md`

### 15.2 Decisiones y correcciones clave

- El preview/confirmación HIGH ahora reciben `telefono_actor` y usan lectura owner-scoped.
- Los intentos contra acciones ajenas responden como `accion_no_existe` sin auditar metadata del owner.
- `high_execution_claimed` se emite sólo después del claim atómico y sólo cuando la ejecución llega desde el confirmador dedicado.
- Errores upstream se clasifican en códigos cerrados; no se persiste texto crudo del provider.
- `destino_short` se recalcula desde el payload de la acción y nunca se confía en `result_payload` del ejecutor.
- Endpoint genérico HIGH sigue cubierto por tests existentes.

### 15.3 Validaciones ejecutadas

| Verificación | Resultado |
| --- | --- |
| `pytest tests/test_automation_high_audit_log.py tests/test_automation_send_message_high.py::TestConfirmacionDedicadaHigh tests/test_automation_endpoints.py -q` | 39 passed |
| `pytest tests/test_automation_high_audit_log.py tests/test_automation_send_message_high.py tests/test_automation_endpoints.py tests/test_automation_execution.py tests/test_automation_creditos_reservas.py tests/test_automation_action_center.py -q` | 109 passed |
| `python scripts/validate_agent_runs.py` | agent-runs OK: 7 runs |
| `git diff --check` | OK |
| Secret scan de archivos modificados | 0 hits |
| Codex read-only final | APROBADO |

### 15.4 Riesgos residuales

- `destino_short` conserva prefijo/sufijo truncado; aceptado como metadata parcial útil para correlación, pero debe revisarse si se exige cero dato derivado del destino.
- Tests usan números ficticios con forma telefónica porque los validadores exigen formato numérico; no son datos reales.
- No se agregó UI nueva ni observabilidad viva; este PR fortalece backend/audit trail.
