# Run Ledger — Computer Use Operating Policy

Run ID: RUN-2026-05-27-computer-use-operating-policy
Fecha: 2026-05-27
Estado: open_pr
Riesgo: MEDIUM
Branch: docs/computer-use-operating-policy
Tipo: docs-only

## Objetivo

Documentar una politica operativa segura para que Hermes use browser/computer use en el desarrollo de Dona y para que Dona integre luego computer use como capability gobernada.

## Motivacion

Computer use es estrategico para Dona porque permite observar interfaces, hacer QA visual, entender referencias y eventualmente preparar o ejecutar acciones en sistemas externos. Tambien aumenta superficie de riesgo: prompt injection visual/web, PII en pantallas, acciones irreversibles, sesiones autenticadas, costos y cumplimiento de terminos.

Antes de usarlo de forma sistematica, el proyecto necesita reglas explicitas de uso, limites y gates.

## Scope autorizado

Archivos permitidos:

- `docs/ops/computer-use-operating-policy.md`
- `docs/ops/agent-runs/2026-05-27-computer-use-operating-policy/run-ledger.md`
- `docs/ops/agent-runs/2026-05-27-computer-use-operating-policy/cost-ledger.md`
- `docs/ops/agent-runs/2026-05-27-computer-use-operating-policy/tool-ledger.md`

## No-scope

- No runtime.
- No providers nuevos.
- No plugins nuevos.
- No Browserbase, RDP, VNC, MCP ni desktop remoto.
- No `.env`, secretos, tokens, OAuth ni credenciales.
- No produccion, deploy settings, Stripe, Meta, WhatsApp live, DB prod ni scheduler.
- No workflows de GitHub Actions.
- No login, formularios, compras, publicaciones o acciones externas.
- No autorizacion implicita futura para HIGH o CRITICAL.

## Agentes y roles

- Celestino: aprobacion de scope docs-only.
- Hermes: redaccion directa por ser cambio documental pequeno y acotado, verificacion y publicacion.
- Codex/Claude Code: no requeridos para primera redaccion; revision read-only opcional si el diff crece o toca reglas sensibles adicionales.

## Criterios de aceptacion

- La politica clasifica `computer_use.observe`, `computer_use.prepare`, `computer_use.assist`, `computer_use.act` y `computer_use.critical`.
- Define que Hermes solo puede usar observe/read-only por defecto.
- Bloquea acciones sensibles sin autorizacion explicita.
- Define reglas de screenshots, PII, prompt injection, costos, audit logs y Action Center.
- Propone contrato futuro para Dona como capability gobernada.
- Mantiene el cambio docs-only.
- Validaciones locales pasan o son justificadas.

## Riesgos

- Riesgo de documentar computer use como si ya estuviera autorizado para acciones reales.
- Riesgo de abrir puerta a sesiones autenticadas sin sandbox.
- Riesgo de capturar PII/secrets en screenshots si no se definen limites.
- Riesgo de prompt injection desde paginas web observadas.

## Mitigaciones

- Politica read-only por defecto.
- HIGH/CRITICAL bloqueados salvo confirmacion dedicada o aprobacion reforzada futura.
- Sesiones autenticadas bloqueadas hasta usuario/cuenta de prueba y permisos minimos.
- Screenshots sensibles no se versionan.
- Contenido web se trata como no confiable.

## Rollback

Revertir el PR documental. No hay cambios runtime ni migraciones.

## Verificaciones ejecutadas

- `git diff --check`: OK.
- `python scripts/validate_agent_runs.py`: OK, `agent-runs OK: 7 runs`.
- `pytest tests/test_validate_agent_runs.py -q`: OK, 5 passed.
- Secret scan local sobre archivos modificados: OK, sin patrones obvios.
- Revision read-only independiente: APROBADO, sin hallazgos bloqueantes.
- Publicacion via msi autenticado: PR #59 abierto.
- Checks PR #59: `Validar agent-runs offline`, `Vercel`, `Vercel Preview Comments` en pass.

## Archivos modificados

- `docs/ops/computer-use-operating-policy.md`
- `docs/ops/agent-runs/2026-05-27-computer-use-operating-policy/run-ledger.md`
- `docs/ops/agent-runs/2026-05-27-computer-use-operating-policy/cost-ledger.md`
- `docs/ops/agent-runs/2026-05-27-computer-use-operating-policy/tool-ledger.md`

## Estado final antes de PR

- Scope: docs-only.
- Runtime: sin cambios.
- Produccion/deploy/secrets/workflows: sin cambios.
- `docs/ops/agent-runs/index.json`: sin cambios por scope; el run no entra al Control Room estatico hasta aprobacion separada o PR de registro.

## Proxima accion

Esperar revision/merge manual de PR #59. Despues del merge, sincronizar workspaces y, si se desea que aparezca en Control Room, registrar el run en `docs/ops/agent-runs/index.json` en un PR separado.
