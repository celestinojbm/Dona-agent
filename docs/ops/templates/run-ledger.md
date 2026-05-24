# Run Ledger — <RUN_ID>

## 0. Metadatos

- Fecha:
- Responsable/orquestador:
- Agentes participantes:
- Branch:
- PR:
- Estado: pre-flight / en progreso / completado / parcial / bloqueado / requiere aprobación

## 1. Objetivo exacto

Una frase verificable: qué resultado debe existir al final.

## 2. Riesgo

- Nivel: LOW / MEDIUM / HIGH / CRITICAL
- Justificación:
- Capa de auditoría dominante: objetivo / canon / herramientas / permisos / seguridad / código / datos / costo / UX / observabilidad / red-team

## 3. Scope permitido

- Archivos permitidos:
- Sistemas permitidos:
- Acciones permitidas:

## 4. No-scope explícito

- Archivos prohibidos:
- Sistemas prohibidos:
- Acciones prohibidas:
- Producción/secrets/deploy/billing/auth/webhooks/RLS: permitido sí/no y bajo qué aprobación.

## 5. Contexto que se va a leer

| Fuente | Motivo | Leído |
| --- | --- | --- |
| `AGENTS.md` | Reglas globales | [ ] |
| `CLAUDE.md` | Convenciones técnicas | [ ] |
| `docs/vision/DONA_CANONICAL_CONTEXT.md` | Canon de producto | [ ] |
| Archivos afectados | Entender antes de escribir | [ ] |
| PRs/issues/logs relacionados | Evitar repetir errores | [ ] |

## 6. Estado inicial

- Workspace:
- Branch inicial:
- Commit inicial:
- `git status --short --branch`:
- Entorno usado: VPS / msi / otro
- Credencial prevista: READ / PR_WRITE / CI_READ / DEPLOY / ADMIN / ninguna

## 7. Supuestos

- Supuesto 1:
- Supuesto 2:
- Información no verificada:

## 8. Plan paso a paso

1. Leer contexto.
2. Verificar estado inicial.
3. Crear branch si aplica.
4. Implementar solo scope aprobado.
5. Validar diff y pruebas.
6. Ejecutar review read-only si aplica.
7. Crear PR si aplica.
8. Reportar cierre con Cost Ledger y próxima acción.

## 9. Herramientas permitidas

| Herramienta | Uso permitido | Límite |
| --- | --- | --- |
| read_file/search_files | Leer contexto | No imprimir secrets |
| write_file/patch | Modificar solo archivos autorizados | No tocar fuera de scope |
| terminal | Git/tests/checks permitidos | No deploy/secrets/live services |
| gh | PR/checks si aplica | No settings/secrets/workflows |
| delegate_task/Codex | Revisión read-only | No editar archivos |

## 10. Herramientas prohibidas

- Deploy CLI:
- Edición de workflows:
- Secrets/.env:
- Stripe/Meta/WhatsApp/DB live:
- Scheduler/workers:
- Auth/billing/webhooks/RLS:
- Merge:

## 11. Pruebas/verificaciones previstas

- `git diff --stat`
- `git diff --check`
- Validación JSON/YAML si aplica
- Tests unitarios si aplica
- Lint/build si aplica
- Scope check: solo archivos autorizados

## 12. Aprobación requerida

- Aprobación recibida:
- Aprobación pendiente:
- Condición de bloqueo:

## 13. Rollback esperado

- Antes de merge:
- Después de merge:
- Feature flag/env off si aplica:
- Revert commit si aplica:

## 14. Ejecución real

### 14.1 Archivos leídos

-

### 14.2 Archivos modificados

-

### 14.3 Desvíos respecto al plan

-

## 15. Tool Ledger

Ver `tool-ledger.md` o completar tabla resumida:

| Tool | Acción | Motivo | Resultado | Riesgo |
| --- | --- | --- | --- | --- |

## 16. Cost Ledger

Ver `cost-ledger.md` o completar resumen:

- Modelo principal:
- Subagentes:
- Tool calls:
- Duración:
- Reintentos:
- Costo exacto/estimado:

## 17. Verificaciones ejecutadas

| Comando/verificación | Resultado | Evidencia |
| --- | --- | --- |

## 18. Riesgos encontrados

-

## 19. Estado final

- Estado: completado / parcial / bloqueado / requiere aprobación
- PR/commit/evidencia:
- Checks:

## 20. Próxima acción requerida

Una sola acción concreta:

-
