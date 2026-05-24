# AGENT_ORCHESTRATION_LOG

> Bitácora canónica de orquestación entre agentes técnicos en el repo de Dona
> (Celestino, Hermes, Claude Code, Codex, OpenClaw). Versiona contexto que
> normalmente se queda fuera del código y de los commits: por qué se eligió
> un PR, qué agente hizo qué, qué guardrails se respetaron y cuál es el
> próximo paso.
>
> Esta bitácora es **interna** durante desarrollo, pero está diseñada como
> semilla del futuro Control Room operativo de Dona para usuarios: el
> mismo modelo (timeline, agentes, guardrails, siguiente acción requerida)
> se reutilizará para mostrar a un usuario qué está haciendo Dona en su
> nombre, con qué permiso, costo y riesgo.

## Cómo usar esta bitácora

1. Antes de abrir un PR no trivial:
   - Crea una carpeta en `docs/ops/agent-runs/` con la convención
     `YYYY-MM-DD-pr<num>-<slug-corto>/`.
   - Copia `docs/ops/templates/agent-run.md` como base de los archivos por
     agente (`scope.md`, `claude-code.md`, `codex-review.md`,
     `hermes-verification.md`, `pr-summary.md`).
   - No es obligatorio incluir transcripts completos: resúmenes curados
     son suficientes. Lo importante es preservar el **por qué** y el
     **riesgo asumido**, no el detalle de cada tool call.

2. Al cerrar el PR:
   - Actualiza el archivo `pr-summary.md` con el commit final, los tests
     RED/GREEN y los próximos pasos sugeridos.
   - Añade una entrada en la sección **Bitácora cronológica** de este
     archivo.

## Guardrails permanentes

Aplican a todo agent-run, sin importar quién ejecute:

- Respetar `docs/vision/DONA_CANONICAL_CONTEXT.md`: Dona es
  plataforma-agente multimodelo, no chatbot.
- No ejecutar acciones reales (cobros, mensajes, publicaciones, cambios
  en cuentas externas) sin preview, costo, permiso humano y audit trail.
- No tocar `.env`, secretos, credenciales, configuración de Render/Vercel,
  ni integraciones reales sin autorización explícita de Celestino.
- No exponer HIGH/CRITICAL desde controles genéricos: cada nivel requiere
  UX dedicada con preview, costo y confirmación fuerte.
- Tools de efecto secundario siguen `preparar_X` / `confirmar_X` (ver
  `CLAUDE.md` §3.1).
- Scheduler permanece apagado por defecto hasta cerrar smoke T2.1.D.

## Roles

- **Celestino**: dueño estratégico. Aprueba alcance y merges.
- **Hermes**: orquestador. Define el paquete del PR, verifica estado real
  antes de actuar, sintetiza resultados, mantiene este archivo y los
  agent-runs alineados.
- **Claude Code**: implementador principal. Trabaja en el repo local con
  TDD; abre PRs pequeños.
- **Codex**: revisor/implementador complementario. Auditoría de diffs,
  detección de regresiones, segunda opinión.
- **OpenClaw / Dona Control**: memoria estratégica y auditor de visión.
  Detecta contradicciones y rescata ideas legacy. No es fuente canónica
  de código.

## Bitácora cronológica

| Fecha       | PR  | Slug                                              | Agentes principales                       | Resultado |
| ----------- | --- | ------------------------------------------------- | ----------------------------------------- | --------- |
| 2026-05-24  | #48 | [next_required_action](agent-runs/2026-05-24-pr48-next-required-action/pr-summary.md) | Hermes + Claude Code + Codex + OpenClaw  | Merged    |
