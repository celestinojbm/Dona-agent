# Run Ledger — Landing reveal/readability fix

Run ID: RUN-2026-05-27-landing-reveal-readable
Fecha: 2026-05-27
Estado: ready_for_pr
Riesgo: MEDIUM
Branch: fix/landing-reveal-readable
Tipo: frontend UX fix

## Objetivo

Corregir la landing publica de Dona para que las secciones intermedias sean visibles/legibles aunque falle una animacion o reveal on-scroll, y mejorar el hero para comunicar mejor el valor de Dona como agente operativo en WhatsApp.

## Evidencia de Browser Use read-only

Reporte local: `/tmp/dona-browser-use-readonly-report-2026-05-27.md`.

Hallazgo principal:

- `https://usadona.com/` muestra hero y footer, pero gran parte del contenido intermedio se percibe como espacio negro vacio.
- Inspeccion DOM encontro contenido existente (`bodyTextLen` ~7967), pero wrappers de secciones como `EL PROBLEMA QUE DONA RESUELVE`, `COMO FUNCIONA`, `CAPACIDADES` y `POR QUE DONA` con `opacity: 0`.
- Console browser sin errores JS visibles.

## Scope autorizado por continuidad

Archivos probables:

- landing page principal y/o componentes de landing bajo `landing/app` o `landing/components`.
- tests frontend asociados.
- este directorio de ledgers.

## No-scope

- No backend/runtime de acciones.
- No scheduler.
- No providers externos.
- No secrets/env.
- No deploy settings.
- No workflows GitHub Actions.
- No Stripe/Meta/WhatsApp live.
- No DB prod.
- No login ni formularios.

## Enfoque tecnico

- TDD: primero agregar test RED que detecte wrappers/secciones invisibles por `opacity-0` o clases equivalentes en contenido clave.
- Fix minimo: hacer contenido base visible por defecto; si hay animacion, debe ser enhancement no dependencia para ver contenido.
- Mantener dark premium, pero mejorar legibilidad de mensajes clave.

## Criterios de aceptacion

- Las secciones clave de landing no dependen de `opacity: 0` persistente para ser visibles.
- El hero comunica mejor: Dona como agente operativo/productividad en WhatsApp, no solo calendario/tarea/memoria rotativa.
- CTA primario mas especifico: WhatsApp o comenzar en WhatsApp.
- Tests frontend relevantes pasan.
- No hay cambios fuera de scope.

## Verificaciones ejecutadas

- TDD RED: `npm test -- app/page.test.tsx` fallo primero por `opacity: 0` en `[data-fade="pending"]` y por ausencia de copy/CTA nuevos.
- TDD RED adicional: test de contador fallo cuando `Counter` inicializaba en cero.
- GREEN: `npm test -- app/page.test.tsx` OK, 3 passed.
- `npm test` OK, 61 passed.
- `npm run lint` OK sin errores; quedan 2 warnings preexistentes en `landing/app/layout.tsx` por `<img>` sin `alt`.
- Browser QA local read-only en `http://127.0.0.1:3001/`: secciones visibles, hero/CTA visibles, contadores `14h`, `$24K`, `73%`, `4x` correctos.
- `python scripts/validate_agent_runs.py` OK, `agent-runs OK: 7 runs`.
- `pytest tests/test_validate_agent_runs.py -q` OK, 5 passed.
- Revision read-only independiente: APROBADO, sin hallazgos bloqueantes.

## Build

- `npm run build` desde `landing/` falla por resolucion de `../../docs/ops/agent-runs/index.json` en `landing/lib/control-room-data.ts`.
- Ese archivo no fue tocado por este cambio; se considera riesgo preexistente/no relacionado para documentar en PR o corregir en PR separado si afecta CI/deploy.

## Archivos modificados

- `landing/app/page.tsx`
- `landing/app/globals.css`
- `landing/app/page.test.tsx`
- `docs/ops/agent-runs/2026-05-27-landing-reveal-readable/run-ledger.md`
- `docs/ops/agent-runs/2026-05-27-landing-reveal-readable/cost-ledger.md`
- `docs/ops/agent-runs/2026-05-27-landing-reveal-readable/tool-ledger.md`

## Resultado

- El contenido de landing deja de depender de un estado invisible persistente si falla `IntersectionObserver` o el reveal.
- El hero comunica mejor a Dona como agente operativo en WhatsApp.
- Los contadores muestran valores reales aunque la animacion no se ejecute.

## Proxima accion

Publicar PR para revision/merge manual.

## Rollback

Revertir PR. No hay migraciones ni impacto backend.
