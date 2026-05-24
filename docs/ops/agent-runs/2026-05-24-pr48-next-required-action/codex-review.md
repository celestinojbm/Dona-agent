# codex-review · PR #48

- **Hallazgos**:
  - El contrato `next_required_action` se evalúa en
    `permissions.py`. Revisé que no introduzca dependencias circulares
    con `action_center.py`: el helper es puro, no toca DB.
  - El endpoint genérico (`agent/main.py`) ahora retorna el motivo del
    backend al rechazar HIGH. Antes devolvía sólo `403` sin contexto.
    Mejora la observabilidad sin abrir nuevos vectores.
  - El componente React respeta `execution_block_reason` cuando llega
    y mantiene el fallback local; verificado en los tests
    `HIGH approved con next_required_action` y
    `HIGH approved legacy`.

- **Sugerencias aceptadas**:
  - Renombrar `motivo` interno a `execution_block_reason` para que el
    nombre del campo sea idéntico en backend/frontend/tests.
  - Cubrir el caso CRITICAL con el contrato completo además del
    fallback.

- **Sugerencias diferidas**:
  - El confirmador dedicado real (UI + endpoint) es PR aparte: requiere
    preview con costo, captura de destinatario y audit trail propio.
  - Considerar mover `permissions.py` a un módulo común si crecen los
    helpers de riesgo; por ahora vive bien junto al Action Center.

- **Cobertura técnica**: Codex revisó backend (action_center, permissions,
  main endpoint genérico) y la sección React. No revisó scheduler ni
  ejecutor HIGH real (fuera de scope).
