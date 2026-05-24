# Agent-run template

> Copia esta plantilla en `docs/ops/agent-runs/YYYY-MM-DD-pr<num>-<slug>/`
> y desglosa en cinco archivos: `scope.md`, `claude-code.md`,
> `codex-review.md`, `hermes-verification.md`, `pr-summary.md`.
>
> Los resúmenes pueden ser cortos. Lo que no debe faltar: objetivo,
> guardrails respetados, riesgos asumidos y siguiente paso.

---

## scope.md

- **Objetivo**: una frase. Qué problema se resuelve.
- **Por qué ahora**: contexto que no se deriva del código.
- **Conexión con el canonical**: a qué sección de
  `docs/vision/DONA_CANONICAL_CONTEXT.md` o `CLAUDE.md` responde.
- **No incluido**: cosas que parecen relacionadas pero se dejan fuera del
  PR a propósito.
- **Criterios de aceptación**: lista accionable.

## claude-code.md

- **Plan ejecutado**: pasos reales que tomó Claude Code (alto nivel).
- **Archivos tocados**: lista corta.
- **Tests RED**: qué se escribió primero y por qué falló.
- **Tests GREEN**: qué cambió para pasar y outputs relevantes.
- **Desvíos respecto al plan original**: si los hubo.

## codex-review.md

- **Hallazgos**: bugs, regresiones, tests faltantes, riesgos.
- **Sugerencias aceptadas**: qué se incorporó al PR.
- **Sugerencias diferidas**: qué se anotó para futuro.
- **Cobertura técnica**: qué áreas Codex revisó y cuáles no.

## hermes-verification.md

- **Verificación previa**: rama, diff, estado en GitHub/msi, repo canónico.
- **Verificación post-merge**: smoke checks, scheduler/HIGH off, métricas.
- **Riesgo residual**: lo que sigue abierto.
- **Snapshot canonical actualizado**: si tocó `DONA_CANONICAL_CONTEXT.md`.

## pr-summary.md

- **PR**: número, link, autor, reviewers.
- **Commit final**: hash + mensaje.
- **Diff size**: archivos y líneas (resumen).
- **Tests**: estado RED/GREEN y suite completa.
- **Guardrails verificados**: lista corta.
- **Próximos pasos sugeridos**: en orden de prioridad.
