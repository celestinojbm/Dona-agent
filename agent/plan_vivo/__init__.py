"""Plan vivo de tarea (F14).

Un plan generado en preparar_X (pasos, entregables, efectos externos, coste
estimado y máximo, destinatarios) que Dona va actualizando en vivo. La
confirmación liga versión + hash: cambiar el plan exige nueva autorización.

- El plan vivo vive SÓLO en la app (panel `PlanVivoPanel`). Decisión de
  Celestino (2026-10-21): NO hay plan vivo en WhatsApp; a WhatsApp sólo puede ir
  un aviso terminal breve de cierre (ver agent/plan_vivo/formato.py).
- Estado con concurrencia optimista (campo `revision`): una revisión vieja no
  pisa una nueva; un retry no regresa pasos ya terminados.
- Outbox `notificaciones_plan` idempotente (UNIQUE por notificación lógica): un
  fallo de notificación no bloquea ni reejecuta el job ni rompe el cobro.

Flag DONA_LIVE_PLAN_ENABLED=false por defecto.
"""
