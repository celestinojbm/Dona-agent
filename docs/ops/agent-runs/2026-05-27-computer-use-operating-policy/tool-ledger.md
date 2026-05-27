# Tool Ledger — Computer Use Operating Policy

Run ID: RUN-2026-05-27-computer-use-operating-policy
Fecha: 2026-05-27
Estado: open_pr

## Herramientas usadas

### skill_view

Uso:

- Cargar `github-pr-workflow` para seguir disciplina de branch/PR.
- Cargar `dona-product-orchestration` para alinear la politica con Dona como plataforma-agente de ejecucion controlada.
- Cargar `hermes-agent` porque la tarea afecta configuracion/uso de Hermes y computer/browser use.

Impacto:

- Solo lectura de skills locales.

### terminal

Uso:

- Verificar fecha UTC.
- Verificar branch, commit y estado git.
- Crear branch docs-only.
- Ejecutar validaciones locales.
- Generar patch/bundle de handoff.
- Transferir patch a msi y publicar PR mediante el workspace autenticado.
- Verificar checks de PR.

Impacto:

- Escritura esperada en git metadata al crear branch y commits.
- Publicacion de branch/PR en GitHub via msi.
- Sin secretos ni produccion.

### read_file

Uso:

- Leer `docs/vision/DONA_CANONICAL_CONTEXT.md`.
- Leer `CLAUDE.md`.
- Leer `README.md`.
- Leer `scripts/validate_agent_runs.py`.

Impacto:

- Solo lectura.

### delegate_task

Uso:

- Revision read-only independiente del diff docs-only.

Impacto:

- Solo lectura y validaciones locales.
- Veredicto: APROBADO, sin hallazgos bloqueantes.

### write_file

Uso:

- Crear `docs/ops/computer-use-operating-policy.md`.
- Crear ledgers del run.

Impacto:

- Escritura docs-only dentro del scope autorizado.

## Herramientas no usadas

- No Browser Use.
- No Tavily.
- No Browserbase.
- No proveedores runtime de Dona.
- No WhatsApp/Meta/Stripe/Vercel/Render live.
- No scheduler.
- No secretos.

## Decisiones de seguridad

- No se incluyeron tokens, claves, credenciales ni rutas sensibles.
- No se realizaron acciones externas.
- Computer use queda documentado como read-only por defecto para Hermes y como capability futura gobernada para Dona.
