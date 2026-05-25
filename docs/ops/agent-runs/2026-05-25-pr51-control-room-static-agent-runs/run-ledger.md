# Run Ledger — 2026-05-25-pr51-control-room-static-agent-runs

## 0. Metadatos

- Fecha: 2026-05-25
- Responsable/orquestador: Hermes
- Agentes participantes: Hermes; subagentes read-only para revisión independiente
- Branch: `feat/control-room-static-agent-runs`
- PR: #51 — `feat(control-room): leer agent-runs estaticos`
- Estado: completado / merged

## 1. Objetivo exacto

Hacer que el Control Room interno lea agent-runs versionados desde `docs/ops/agent-runs/index.json` mediante una capa tipada frontend, sin conectar APIs vivas ni tocar backend/runtime.

## 2. Riesgo

- Nivel: MEDIUM
- Justificación: cambio de UI interna del dashboard; consume documentación versionada y no modifica integraciones productivas.
- Capa de auditoría dominante: UX, observabilidad estática, datos versionados y seguridad de no exponer secrets.

## 3. Scope permitido

- Archivos permitidos:
  - `landing/lib/control-room-data.ts`
  - `landing/lib/control-room-data.test.ts`
  - `landing/app/dashboard/seccion-control-room.tsx`
  - `landing/app/dashboard/seccion-control-room.test.tsx`
- Sistemas permitidos: tests frontend, lint, git diff, secret scan count-only, revisiones read-only.
- Acciones permitidas: abrir PR; no merge automático.

## 4. No-scope explícito

- No modificar `docs/ops/agent-runs/index.json` durante Fase 1B.
- No GitHub/Vercel/Render APIs vivas dentro del producto.
- No producción, deploy settings, workflows, tokens, secrets, `.env`, Stripe, Meta/WhatsApp, DB live, scheduler, auth, billing, webhooks, RLS, backend/agent/providers.

## 5. Contexto leído

| Fuente | Motivo | Leído |
| --- | --- | --- |
| `AGENTS.md` | Reglas globales | Sí |
| `CLAUDE.md` | Convenciones técnicas | Sí |
| `docs/vision/DONA_CANONICAL_CONTEXT.md` | Canon de producto | Sí |
| `docs/ops/agent-runs/index.json` | Fuente estática a consumir | Sí |
| Control Room existente | Integrar sin romper UI | Sí |

## 6. Estado inicial

- Workspace: `C:\Users\celes\Dona-current` y espejo VPS `/root/projects/Dona-agent`
- Branch inicial: `main` post PR #50
- Commit base: `2dc4582`
- Entorno usado: msi para GitHub/PR; VPS como espejo de coordinación
- Credencial prevista: PR_WRITE vía GitHub CLI en msi; sin imprimir tokens

## 7. Plan ejecutado

1. Producir pre-flight Run Ledger en chat.
2. Escribir tests primero para capa de datos y UI.
3. Verificar RED por ausencia de capa `control-room-data` y render de agent-runs.
4. Implementar helper tipado que importa el JSON estático.
5. Renderizar agent-runs, riesgo, costo estimado, fuente y próxima acción en el Control Room.
6. Ejecutar tests focales, suite frontend, lint, diff check y scan básico de secretos.
7. Ejecutar revisiones read-only.
8. Abrir PR sin merge; usuario mergeó después.

## 8. Archivos modificados

- `landing/lib/control-room-data.ts`
- `landing/lib/control-room-data.test.ts`
- `landing/app/dashboard/seccion-control-room.tsx`
- `landing/app/dashboard/seccion-control-room.test.tsx`

## 9. Verificaciones ejecutadas

| Verificación | Resultado | Evidencia |
| --- | --- | --- |
| RED TDD | OK | Tests fallaron antes de implementación por feature ausente |
| `npm test -- control-room-data.test.ts seccion-control-room.test.tsx` | OK | 9 passed |
| `npm test` | OK | 54 passed |
| `npm run lint` | OK | 0 errores, 3 warnings preexistentes |
| `git diff --check` | OK | Sin errores |
| Secret scan count-only | OK | 0 posibles tokens/secrets tras limpiar falsos positivos |
| Revisiones read-only | OK | Sin bloqueantes tras ajuste menor de copy |
| PR/checks | OK | PR #51 mergeado en `main` |

## 10. Riesgos residuales

- Control Room sigue leyendo un índice estático; no hay observabilidad viva.
- El índice no se actualiza automáticamente todavía.
- Gate por email/client-side del Control Room no es frontera de seguridad real, aceptable temporalmente porque no muestra secretos.

## 11. Rollback

- Antes de merge: cerrar PR #51.
- Después de merge: revertir el squash commit `874eba1` si el dashboard regresa.

## 12. Estado final

- Estado: completado / merged
- PR: https://github.com/celestinojbm/Dona-agent/pull/51
- Commit final: `874eba145dac86f942b459c64d665d53fd2cb798`

## 13. Próxima acción requerida

Registrar PR #50 y PR #51 en `docs/ops/agent-runs/index.json` y crear sus ledgers versionados para que el Control Room los muestre.
