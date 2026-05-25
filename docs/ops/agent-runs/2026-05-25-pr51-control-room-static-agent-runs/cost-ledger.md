# Cost Ledger — 2026-05-25-pr51-control-room-static-agent-runs

## 1. Resumen

- Fecha: 2026-05-25
- Tarea: Fase 1B — Control Room consume agent-runs estáticos.
- Riesgo: MEDIUM
- Orquestador: Hermes
- Estado: completado / merged

## 2. Modelos usados

| Sistema/modelo | Rol | Uso | Tokens reportados | Costo reportado |
| --- | --- | --- | --- | --- |
| Hermes / modelo principal | Orquestación | Plan, edición, validación y síntesis | No disponible | No disponible |
| Subagentes Hermes | Revisión | Dos revisiones read-only de diff/scope | No disponible | No disponible |

## 3. Tool calls

| Categoría | Conteo aproximado | Notas |
| --- | ---: | --- |
| Lectura de archivos | 8 | Contexto, index y componentes existentes |
| Escritura/patch | 7 | Tests, helper y UI |
| Terminal/git/tests | 10 | TDD, suite, lint, diff, scan |
| GitHub/gh | 4 | PR, checks y verificación merge |
| Subagentes | 2 | Revisiones read-only |
| Browser/web | 0 | No usado |
| Otros | 0 |  |

## 4. Reintentos y fallos

| Incidente | Causa | Reintentos | Costo/impacto | Resolución |
| --- | --- | ---: | --- | --- |
| RED esperado | Feature ausente | 1 | Bajo | Implementación mínima para GREEN |
| Path/source de JSON | Ajuste de import y normalización | 1 | Bajo | Se usó `../../docs/ops/agent-runs/index.json` |
| Texto ambiguo en test | Frase repetida en UI | 1 | Bajo | Selector/test ajustado |
| Comando combinado con timeout | Suite/lint juntos | 1 | Bajo | Se dividieron comandos |
| Secret scan falso positivo | Literales de test parecidos a secretos | 1 | Bajo | Se reemplazaron por patrones genéricos |

## 5. Duración

- Inicio aproximado: 2026-05-24
- Fin aproximado: 2026-05-25
- Duración total: no medida con precisión
- Tiempo bloqueado por checks/CI: bajo

## 6. Costo exacto o estimado

- Costo exacto disponible: no.
- Estimación cualitativa: medio.
- Razón: TDD, suite frontend, lint, scan y dos revisiones read-only; sin APIs pagadas/productivas ni builds largos.

## 7. Justificación de eficiencia

- TDD evitó regressiones del Control Room.
- La revisión read-only detectó ajustes menores sin ampliar scope.
- Se evitó conectar APIs vivas hasta tener datos versionados y trazables.

## 8. Cierre

- ¿El costo fue proporcional al valor?: sí.
- Riesgo de costo residual: bajo-medio por actualización manual del índice.
- Acción recomendada: crear generador/check estático para mantener `index.json` sincronizado.
