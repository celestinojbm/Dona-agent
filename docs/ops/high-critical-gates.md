# HIGH / CRITICAL Gates — Dona Agent

## Principio

Dona puede proponer acciones sensibles, pero no debe ejecutarlas sin preview, costo, riesgo, permiso humano y audit trail. Hermes tampoco debe modificar superficies sensibles sin aprobación explícita.

## HIGH

Una tarea es HIGH si puede afectar:

- Auth o sesiones.
- Billing/Stripe/créditos sin tocar pagos reales directamente.
- Webhooks con riesgo de side effects.
- Workers/scheduler aunque estén apagados.
- WhatsApp/Meta sin envío real.
- ApprovalGate o acciones HIGH.
- Estado persistente con riesgo limitado.

Gate obligatorio:

1. Run Ledger pre-flight.
2. Aprobación humana explícita del scope.
3. Branch separada.
4. Tests con mocks.
5. Revisión técnica.
6. Revisión seguridad.
7. Red-team checklist aplicable.
8. Rollback definido.
9. No deploy manual sin aprobación separada.

## CRITICAL

Una tarea es CRITICAL si toca:

- Secrets/tokens.
- Producción/deploy settings.
- GitHub workflows/actions write.
- Permisos/admin/branch protection.
- DB live/RLS/migraciones productivas.
- Pagos reales o Stripe live.
- Envíos reales Meta/WhatsApp.
- Scheduler activo con efectos externos.
- CRITICAL action execution.

Gate obligatorio:

1. Aprobación humana reforzada antes de cualquier ejecución.
2. Privilegio mínimo demostrado.
3. Plan de rollback o reversión.
4. Revisión seguridad obligatoria.
5. Staging/preview cuando sea posible.
6. Registro en Run Ledger y Cost Ledger.
7. No continuar si validación de seguridad falla o no está disponible.

## Endpoints y UI

- HIGH aprobada no debe ejecutarse desde controles genéricos.
- CRITICAL nunca debe ejecutarse automáticamente.
- UI no debe mostrar botones engañosos para estados bloqueados.
- El backend debe exponer `next_required_action` o equivalente para explicar el siguiente gate.
- Cualquier confirmador dedicado debe mostrar preview, costo, destinatario, riesgo y acción irreversible antes de confirmar.

## Scheduler/workers

- Scheduler permanece apagado por defecto.
- Jobs con side effects requieren idempotencia, lock y audit trail.
- HIGH/CRITICAL no se ejecutan por scheduler sin gate humano.

## Bloqueo

Bloquear si:

- Falta aprobación humana.
- Falta preview/costo/riesgo.
- El endpoint genérico intenta ejecutar HIGH/CRITICAL.
- El agente necesita secrets o deploy y no están en scope.
- El rollback no existe o no está claro.
