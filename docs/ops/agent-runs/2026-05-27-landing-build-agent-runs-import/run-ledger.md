# Run Ledger — Landing build agent-runs import

Run ID: RUN-2026-05-27-landing-build-agent-runs-import
Fecha: 2026-05-27
Estado: ready_for_pr
Riesgo: MEDIUM
Branch: fix/landing-build-agent-runs-import
Tipo: frontend build fix

## Objetivo

Corregir el fallo de `npm run build` en `landing/` causado por el import de `docs/ops/agent-runs/index.json` desde fuera del proyecto Next/Turbopack.

## Evidencia reproducida

`npm run build` desde `landing/` falla con:

- `Module not found: Can't resolve '../../docs/ops/agent-runs/index.json'`
- archivo: `landing/lib/control-room-data.ts`

El archivo JSON existe en el repo, pero Turbopack no resuelve ese import externo al root de la app Next durante build.

## Scope

Permitido:

- `landing/lib/control-room-data.ts`
- `landing/lib/control-room-data.test.ts`
- archivo local estático bajo `landing/` si hace falta para build.
- ledgers de este run.

## No-scope

- No backend/runtime.
- No secrets/env.
- No deploy settings.
- No workflows.
- No scheduler.
- No providers externos.
- No Stripe/Meta/WhatsApp live.
- No DB prod.

## Enfoque

- Reproducir fallo.
- Agregar test RED para que el import usado por Control Room sea compatible con build Next/Turbopack y no salga de `landing/`.
- Mantener el Control Room estático usando los mismos datos no sensibles de `docs/ops/agent-runs/index.json`.
- Validar `npm run build`, tests y lint.

## Criterios de aceptación

- `npm run build` en `landing/` pasa.
- Tests frontend pasan.
- El Control Room sigue leyendo datos estáticos y no sensibles.
- No se modifica runtime backend ni secretos.

## Verificaciones ejecutadas

- Reproduccion: `npm run build` fallo por `Module not found: Can't resolve '../../docs/ops/agent-runs/index.json'`.
- TDD RED: `npm test -- lib/control-room-data.test.ts` fallo por import externo a `../../docs`.
- GREEN: `npm test -- lib/control-room-data.test.ts` OK, 4 passed.
- `npm run build` OK con Next/Turbopack.
- `npm test` OK, 62 passed.
- `npm run lint` OK sin errores; quedan 2 warnings preexistentes en `landing/app/layout.tsx`.
- `python scripts/validate_agent_runs.py` OK, `agent-runs OK: 7 runs`.
- `pytest tests/test_validate_agent_runs.py -q` OK, 5 passed.
- `git diff --check` OK.
- Secret scan local sobre archivos modificados: OK.
- Revision read-only independiente: APROBADO, sin hallazgos bloqueantes.

## Root cause

Turbopack/Next build resuelve desde el root de la app `landing/` y no acepta de forma confiable el import JSON relativo que sale a `../../docs/ops/agent-runs/index.json` desde `landing/lib/control-room-data.ts`.

## Fix aplicado

- Crear copia estatica local `landing/data/agent-runs-index.json`.
- Cambiar `control-room-data.ts` para importar `../data/agent-runs-index.json`.
- Agregar test que exige import local compatible con build y compara que el JSON local coincida con `docs/ops/agent-runs/index.json`.

## Riesgos residuales

- Hay duplicacion entre `docs/ops/agent-runs/index.json` y `landing/data/agent-runs-index.json`; el test detecta drift, pero a futuro conviene automatizar copia/generacion.
- Este run no se registra en `docs/ops/agent-runs/index.json`, por decision previa de no priorizar Control Room estatico para cada run.

## Archivos modificados

- `landing/lib/control-room-data.ts`
- `landing/lib/control-room-data.test.ts`
- `landing/data/agent-runs-index.json`
- `docs/ops/agent-runs/2026-05-27-landing-build-agent-runs-import/run-ledger.md`
- `docs/ops/agent-runs/2026-05-27-landing-build-agent-runs-import/cost-ledger.md`
- `docs/ops/agent-runs/2026-05-27-landing-build-agent-runs-import/tool-ledger.md`

## Proxima accion

Publicar PR para revision/merge manual.

## Rollback

Revertir PR. No hay migraciones ni cambios backend.
