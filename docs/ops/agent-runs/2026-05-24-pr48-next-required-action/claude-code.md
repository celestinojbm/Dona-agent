# claude-code · PR #48

- **Plan ejecutado**:
  1. Definir el contrato en `agent/automation/permissions.py`: helper
     puro que dada una acción devuelve `next_required_action` y
     `execution_block_reason`.
  2. Propagar el contrato en el serializador de
     `agent/automation/action_center.py` y en el endpoint genérico
     de `agent/main.py` para que el rechazo HIGH/CRITICAL use el mismo
     motivo.
  3. Añadir tipos en `landing/lib/automation-types.ts`.
  4. Adaptar `seccion-action-center.tsx` para preferir los campos del
     backend y mantener el fallback local cuando no llegan.

- **Archivos tocados**:
  - `agent/automation/action_center.py` (+13/-2)
  - `agent/automation/permissions.py` (+87/-0)
  - `agent/main.py` (+19/-2)
  - `landing/app/dashboard/seccion-action-center.tsx` (+96/-14)
  - `landing/app/dashboard/seccion-action-center.test.tsx` (+210/-0)
  - `landing/lib/automation-types.ts` (+35/-0)
  - `tests/test_automation_next_required_action.py` (+257/-0)

- **Tests RED**:
  - `tests/test_automation_next_required_action.py` cubre las
    transiciones del contrato (LOW pending, HIGH approved, CRITICAL
    needs_approval). Antes del cambio, los campos no existían en el
    payload y los asserts fallaban con KeyError.
  - En el frontend, los nuevos casos del componente buscaban texto
    proveniente del backend ("MOTIVO_BACKEND_DEDICADO",
    "MOTIVO_API_CRITICAL") que el componente legacy ignoraba.

- **Tests GREEN**:
  - Backend: 257 líneas nuevas pasan, suite completa `pytest` en verde.
  - Frontend: `npm test -- seccion-action-center.test.tsx` pasa los
    casos nuevos + los legacy (fallback local).

- **Desvíos**:
  - Se conservó la copy local del componente como fallback en lugar de
    eliminarla. Razón: payloads previos al deploy del backend pueden
    quedar cacheados en respuestas; quitar el fallback rompería la UI
    para esos clientes durante el redeploy.
