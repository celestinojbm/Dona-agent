# Run Ledger — 2026-05-24-pr50-operational-governance

## 0. Metadatos

- Fecha: 2026-05-24
- Responsable/orquestador: Hermes
- Agentes participantes: Hermes; subagente read-only para revisión independiente
- Branch: `docs/fase-1a-operational-governance`
- PR: #50 — `docs(ops): formalizar run ledger y gates operativos`
- Estado: completado / merged

## 1. Objetivo exacto

Formalizar la gobernanza operativa de Dona con políticas y plantillas versionadas para Run Ledger, Cost Ledger, Tool Ledger, seguridad, red-team, deploy gates, permisos mínimos y gates HIGH/CRITICAL.

## 2. Riesgo

- Nivel: MEDIUM
- Justificación: docs operativos que guían cómo Hermes y agentes ejecutan tareas MEDIUM+; no modifica runtime, producción ni integraciones vivas.
- Capa de auditoría dominante: permisos, seguridad, costo, observabilidad y red-team.

## 3. Scope permitido

- Archivos permitidos: 12 archivos bajo `docs/ops/` y `docs/ops/templates/`.
- Sistemas permitidos: git local, validación JSON, diff/scope checks, revisión read-only.
- Acciones permitidas: crear documentación operativa, abrir PR, verificar checks.

## 4. No-scope explícito

- Producción, tokens, secrets, `.env`, workflows, deploy settings, Stripe, Meta/WhatsApp, DB live, scheduler, auth, billing, webhooks, RLS, backend/runtime y frontend productivo.
- Merge automático: no permitido.

## 5. Contexto leído

| Fuente | Motivo | Leído |
| --- | --- | --- |
| `AGENTS.md` | Reglas globales | Sí |
| `CLAUDE.md` | Convenciones técnicas | Sí |
| `docs/vision/DONA_CANONICAL_CONTEXT.md` | Canon de producto | Sí |
| Auditoría Hermes externa y plan de corrección | Base de brechas operativas | Sí |
| `docs/ops/` existente | Evitar duplicación e integrar estructura | Sí |

## 6. Estado inicial

- Workspace: `C:\Users\celes\Dona-current` y espejo VPS `/root/projects/Dona-agent`
- Branch inicial: `main`
- Commit base: posterior a PR #49
- Entorno usado: msi para GitHub/PR; VPS como espejo de coordinación
- Credencial prevista: PR_WRITE vía GitHub CLI en msi; sin uso de secrets en archivos

## 7. Plan ejecutado

1. Producir pre-flight Run Ledger en chat antes de tocar archivos.
2. Crear branch separada.
3. Crear/actualizar exactamente los 12 docs autorizados.
4. Validar formato JSON, whitespace y scope exacto.
5. Ejecutar revisión independiente read-only.
6. Abrir PR sin merge.
7. Usuario mergeó PR después de revisión.

## 8. Archivos modificados

- `docs/ops/RUN_LEDGER_POLICY.md`
- `docs/ops/templates/run-ledger.md`
- `docs/ops/templates/cost-ledger.md`
- `docs/ops/templates/tool-ledger.md`
- `docs/ops/templates/security-checklist.md`
- `docs/ops/templates/red-team-checklist.md`
- `docs/ops/templates/deploy-gate.md`
- `docs/ops/permissions-model.md`
- `docs/ops/risk-policy.md`
- `docs/ops/high-critical-gates.md`
- `docs/ops/agent-runs/README.md`
- `docs/ops/agent-runs/index.json`

## 9. Verificaciones ejecutadas

| Verificación | Resultado | Evidencia |
| --- | --- | --- |
| `git diff --check` | OK | Sin errores de whitespace |
| `python3 -m json.tool docs/ops/agent-runs/index.json` | OK | JSON válido |
| Scope check | OK | 12 archivos autorizados, 0 extras, 0 faltantes |
| Revisión independiente read-only | OK | Sin bloqueantes |
| PR/checks | OK | PR #50 mergeado en `main` |

## 10. Riesgos residuales

- Las políticas documentan permisos mínimos, pero la separación real de tokens aún no está implementada.
- Run Ledger/Cost Ledger aún no se validan automáticamente por CI.
- Red-team, staging/deploy gates reales y observabilidad viva siguen pendientes.

## 11. Rollback

- Antes de merge: cerrar PR #50.
- Después de merge: revertir el squash commit `2dc4582` si la documentación causa una regresión operativa.

## 12. Estado final

- Estado: completado / merged
- PR: https://github.com/celestinojbm/Dona-agent/pull/50
- Commit final: `2dc4582cbbe8d16872981a0a748475829e39d4b2`

## 13. Próxima acción requerida

Consumir `docs/ops/agent-runs/index.json` desde el Control Room interno antes de conectar APIs vivas.
