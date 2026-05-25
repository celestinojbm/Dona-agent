# Tool Ledger — 2026-05-25-pr51-control-room-static-agent-runs

## Tabla principal

| # | Tool | Acción | Motivo | Entrada sensible | Resultado | Riesgo | Evidencia |
| ---: | --- | --- | --- | --- | --- | --- | --- |
| 1 | read_file/search_files | Leer reglas, canon, index y Control Room | Entender alcance antes de escribir | No | Contexto verificado | LOW | `AGENTS.md`, `CLAUDE.md`, `DONA_CANONICAL_CONTEXT.md`, `docs/ops/agent-runs/index.json` |
| 2 | write_file/patch | Crear tests, helper y actualizar UI | Implementar consumo estático | No | 4 archivos modificados | MEDIUM | Diff PR #51 |
| 3 | terminal/npm | Ejecutar tests y lint | Verificar RED/GREEN y no regresión | No | 9 passed focal, 54 passed suite, lint sin errores | MEDIUM | Salida de npm |
| 4 | terminal/git | Diff, scope y secret scan count-only | Validar límites y ausencia de secretos | No | Checks OK | MEDIUM | `git diff --check`, scan 0 |
| 5 | delegate_task | Revisiones read-only | Segunda opinión independiente | No | Sin bloqueantes | MEDIUM | Resultados de revisión |
| 6 | gh/git | Abrir PR y verificar merge/checks | Flujo PR controlado | Token no impreso | PR #51 mergeado por usuario | MEDIUM | https://github.com/celestinojbm/Dona-agent/pull/51 |

## Cierre

- Total tool calls aproximado: 31.
- Tool calls fuera del plan: no.
- Evidencia principal: PR #51 mergeado, commit `874eba145dac86f942b459c64d665d53fd2cb798`.
