# Deploy Gate — Dona Agent

## Propósito

Este checklist no ejecuta deploys. Define las condiciones mínimas para permitir que un cambio llegue a producción cuando `main` despliega automáticamente.

## 1. Clasificación del cambio

- Run ID:
- PR:
- Riesgo: LOW / MEDIUM / HIGH / CRITICAL
- Afecta producción: sí/no
- Afecta dominio sensible: auth / billing / webhooks / workers / DB / secrets / deploy / workflows / HIGH actions / ninguno

## 2. Entornos

- Branch de trabajo:
- Preview/Staging URL:
- Producción URL:
- Commit a desplegar:
- Commit actualmente en producción:

## 3. Gates por riesgo

| Riesgo | Gate mínimo |
| --- | --- |
| LOW | PR + revisión ligera |
| MEDIUM | PR + tests relevantes + preview/staging si aplica |
| HIGH | PR + tests + revisión técnica + revisión seguridad + aprobación humana |
| CRITICAL | Todo lo anterior + aprobación reforzada + rollback probado o plan explícito |

## 4. Checklist antes de merge a main

- [ ] Run Ledger completo.
- [ ] Cost Ledger completo.
- [ ] Tool Ledger revisado.
- [ ] Tests/lint/build relevantes ejecutados.
- [ ] No hay cambios fuera de scope.
- [ ] No hay secrets/PII en diff.
- [ ] Preview/staging revisado si aplica.
- [ ] Rollback documentado.
- [ ] Aprobación humana registrada si HIGH/CRITICAL.

## 5. Checklist sensible

Si aplica cualquiera, no hacer merge sin aprobación humana:

- [ ] Auth
- [ ] Stripe/billing/créditos
- [ ] Meta/WhatsApp/envíos reales
- [ ] Webhooks
- [ ] Workers/scheduler
- [ ] DB live/RLS/migraciones
- [ ] Secrets/tokens
- [ ] GitHub workflows/actions
- [ ] Vercel/Render settings
- [ ] HIGH/CRITICAL execution path

## 6. Rollback

- Método primario: revert PR / revert commit.
- Método secundario: feature flag/env off.
- Método de deploy: rollback Vercel/Render si disponible.
- Datos/migraciones: downgrade/forward fix si aplica.
- Responsable humano:

## 7. Decisión

- [ ] No deploy.
- [ ] Deploy a staging solamente.
- [ ] Merge permitido.
- [ ] Producción permitida.
- [ ] Escalar a humano.

Notas:
