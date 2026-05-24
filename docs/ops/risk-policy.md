# Risk Policy — Dona Agent Operations

## Propósito

Clasificar cada tarea antes de ejecutar. La clasificación determina ledger, permisos, revisión, pruebas y aprobación humana.

## LOW

Ejemplos:
- Copy menor.
- Documentación no operativa.
- Lectura/investigación sin modificar repo.
- Estilos visuales no sensibles.

Requisitos:
- Plan breve recomendado.
- No requiere PR si no toca repo.
- Si toca repo, branch/PR recomendado.

Prohibido:
- Acciones externas reales.
- Secrets/producción.

## MEDIUM

Ejemplos:
- Documentación operativa.
- Dashboard interno estático.
- Componentes UI sin datos live.
- Scripts internos sin secretos.
- Cambios backend no sensibles y testeados con mocks.

Requisitos:
- Run Ledger obligatorio.
- Cost Ledger obligatorio.
- Branch separada.
- PR.
- Tests/verificaciones relevantes.
- Scope check.

## HIGH

Ejemplos:
- Auth no crítica pero funcional.
- Billing/Stripe no live o cambios de lógica de créditos.
- Webhooks con mocks.
- Workers/scheduler apagado.
- WhatsApp/Meta sin envío real.
- ApprovalGate/HIGH action paths.

Requisitos:
- Run Ledger antes de ejecutar.
- Aprobación humana explícita.
- Revisión técnica.
- Revisión de seguridad.
- Tests unit/integration con mocks.
- Red-team checklist.
- Rollback.

Prohibido sin aprobación:
- Producción.
- Providers live.
- Activar scheduler.
- Efectos externos.

## CRITICAL

Ejemplos:
- Secrets/tokens.
- Producción/deploy settings.
- GitHub workflows/actions write.
- RLS/DB live/migraciones productivas.
- Pagos reales.
- Envíos reales masivos.
- Cambios de permisos/admin.
- CRITICAL action execution.

Requisitos:
- Aprobación humana reforzada.
- Privilegio mínimo demostrado.
- Plan de rollback explícito.
- Revisión seguridad obligatoria.
- Staging/preview cuando aplique.
- No automatizar sin gate.

## Reglas de promoción de riesgo

Subir el riesgo si:

- Aparece un secret/PII/payload sensible.
- El diff toca archivos fuera del scope.
- Hay acceso a servicio live.
- Se requiere token más amplio.
- Se toca estado persistente.
- Se modifica un path de ejecución HIGH/CRITICAL.
- Hay contradicción de contexto/canon.

## Regla final

El score promedio no compensa fallos críticos. Si falla seguridad, permisos, auth, billing, datos o producción, la tarea se bloquea aunque parezca correcta en otras dimensiones.
