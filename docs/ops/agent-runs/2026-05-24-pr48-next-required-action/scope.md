# scope · PR #48 · next_required_action

- **Objetivo**: exponer en el backend un contrato explícito
  (`next_required_action` + `execution_block_reason`) para que la UI del
  Action Center deje de hardcodear el motivo por el que una acción HIGH
  aprobada o CRITICAL no se ejecuta desde el control genérico.

- **Por qué ahora**: PRs #46 y #47 dejaron la UX correcta (no se ejecuta
  HIGH desde el endpoint genérico, se muestra "Aprobada · requiere
  confirmación dedicada"). Pero el texto que justificaba el bloqueo
  vivía sólo en el componente React. Si el backend cambia su razón
  (p. ej. al introducir un confirmador dedicado real), la UI quedaría
  desincronizada. Faltaba un contrato.

- **Conexión con el canonical**:
  - `DONA_CANONICAL_CONTEXT.md` §9.3 (Aprobación fuerte) y §9.4
    (CRITICAL): cada acción sensible debe llevar preview, costo, riesgo
    y permiso requerido. Que el backend nombre la "siguiente acción
    requerida" es la mecánica que materializa esa regla en producto.
  - `CLAUDE.md` §3.1: refuerza la convención `preparar_X` / `confirmar_X`.
    El nuevo contrato no introduce ejecución; sólo declara qué paso
    falta.

- **No incluido**:
  - No se construye el confirmador dedicado real para HIGH (queda como
    siguiente PR).
  - No se habilita el scheduler ni se expone HIGH desde el control
    genérico.
  - No se tocan integraciones externas (Whapi, Stripe, Gemini).

- **Criterios de aceptación**:
  - El payload del Action Center incluye, cuando aplica,
    `next_required_action` y `execution_block_reason`.
  - El componente React respeta esos campos si llegan, y cae a copy
    local si no llegan (backwards compat).
  - El endpoint genérico de ejecución sigue rechazando HIGH/CRITICAL.
  - Tests cubren contrato API + UI para HIGH (con y sin contrato) y
    CRITICAL.
