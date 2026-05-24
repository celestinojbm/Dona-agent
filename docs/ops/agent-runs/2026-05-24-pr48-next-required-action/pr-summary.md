# pr-summary · PR #48 · next_required_action

- **PR**: #48 — `feat(automation): exponer next required action`
- **Autor**: celestinojbm
- **Reviewers**: Hermes (coordinación), Codex (revisión), OpenClaw
  (auditoría de visión)
- **Commit final**: `1733d37 feat(automation): exponer next required action (#48)`

- **Diff size**:
  - 7 archivos modificados/creados.
  - +716 / -15 líneas.
  - Backend (`agent/automation/*`, `agent/main.py`), frontend
    (`landing/app/dashboard/seccion-action-center.tsx`,
    `landing/lib/automation-types.ts`), tests
    (`tests/test_automation_next_required_action.py`,
    `landing/app/dashboard/seccion-action-center.test.tsx`).

- **Tests**:
  - RED inicial en backend (`KeyError` por campos faltantes) y en
    frontend (asserts buscaban texto del backend en payloads que aún no
    lo traían).
  - GREEN tras implementación: `pytest` completo y
    `npm test -- seccion-action-center.test.tsx` en verde.

- **Guardrails verificados**:
  - HIGH/CRITICAL siguen sin ejecutarse desde el control genérico.
  - Scheduler apagado, sin cambios en Render/Vercel/secrets.
  - Fallback local conservado para evitar romper UI durante el rollout.
  - Lenguaje en español, sin promesas de ingresos ni claims fuera de
    `DONA_CANONICAL_CONTEXT.md`.

- **Próximos pasos sugeridos** (en orden):
  1. Construir confirmador dedicado real para HIGH (UI con preview de
     mensaje WhatsApp, costo en créditos, captura de destinatario,
     audit log).
  2. Cerrar smoke T2.1.D (reservas/créditos) en producción.
  3. Evaluar exponer `next_required_action` en respuestas del bot por
     WhatsApp para que el usuario vea el mismo motivo desde el canal
     conversacional.
  4. Diseñar la versión usuario-final del Control Room (este PR siembra
     la versión interna).
