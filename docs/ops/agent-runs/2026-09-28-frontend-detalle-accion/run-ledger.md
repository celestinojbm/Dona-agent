# Run Ledger — Detalle de acción y decisión en el Centro de acción

## Metadata

- Run ID: RUN-2026-09-28-frontend-detalle-accion
- Agent-run ID: 2026-09-28-frontend-detalle-accion
- Date: 2026-09-28
- Branch: `feat/action-center-detalle-accion`
- Base: `main` @ 958b525
- Risk: MEDIUM (solo frontend `landing/`, sin cambios de contrato ni de backend)
- Status: entregado para revisión (sin merge, sin deploy)

## Objetivo

Completar el flujo central de Dona en el dashboard: recibir una
solicitud/acción, revisar su estado y detalle, aprobarla o rechazarla
cuando corresponda, y consultar el resultado y su historial.

Hueco de mayor prioridad elegido: el Centro de acción ya listaba
acciones y permitía aprobar/rechazar/ejecutar, pero **no tenía vista de
detalle**, las decisiones se disparaban sin confirmación, el historial
era un `<details>` con JSON crudo y no había foco de teclado ni anuncios
para lectores de pantalla. Se cierra ese flujo sin tocar el backend.

## Alcance

Incluido:

- Panel de detalle por acción (Sheet/Radix ya presente en
  `components/ui/sheet.tsx`) con estado, riesgo, costo, origen
  (tipo/playbook/oportunidad), línea de tiempo, resultado y error.
- Confirmación explícita antes de aprobar, rechazar y ejecutar
  (dry-run), desde la tarjeta y desde el panel.
- Resultado con filas legibles en vez de JSON crudo; el JSON sin formato
  queda disponible como escape.
- Historial con filtro por estado (solo estados presentes en los datos)
  y acceso al detalle de cada acción.
- Accesibilidad: foco atrapado y Escape (Radix), `aria-live` para
  anunciar la decisión, `aria-haspopup` en los disparadores, `<button>`
  reales.
- Tests nuevos de UI y de los helpers de formato.

Excluido:

- No se modificó el backend ni ningún endpoint existente.
- No se agregaron dependencias.
- No se creó el confirmador genérico de CRITICAL (sigue bloqueado).
- No hay merge ni deploy.

## Contrato de backend faltante (documentado también en la UI)

- **No existe `GET /api/automation/acciones/:id`**: el detalle se arma
  con el payload de la lista (`estado`, riesgo, timestamps, `result_json`,
  `next_required_action`, `execution_block_reason`). Si la acción no está
  en la lista cargada, no hay detalle que mostrar.
- **No existe historial de eventos por acción** (audit trail de la
  acción). La sección "Historial de la acción" muestra únicamente los
  timestamps que la acción ya expone (`created_at`, `approved_at`,
  `rejected_at`, `completed_at`, `updated_at`) y lo dice explícitamente
  en el panel.

Cuando esos dos contratos existan, el punto único a cambiar en el
frontend es `landing/lib/accion-formato.ts` (`lineaTiempoAccion`) más el
origen del detalle (`accionEnDetalle` en `seccion-action-center.tsx`).

## Verificación

Ejecutada en `landing/` dentro del worktree aislado:

- `npm test` → 225 pasan / 7 fallan. Los 7 fallos son preexistentes de
  `app/dashboard/dashboard-shell.test.tsx` (`window.localStorage`
  undefined por entorno jsdom), verificados en la base `main` antes de
  empezar: 208 pasan / 7 fallan. No se introdujeron fallos nuevos y no
  se tocó ese archivo.
- `npm run lint` → 0 errores (1 warning preexistente en `app/layout.tsx`
  por `<img>`).
- `npm run typecheck` → limpio.

## Incremento 2 · estados, móvil y accesibilidad

Segundo commit de la misma rama, sobre la entrega anterior.

Defectos cerrados (verificables, dentro del alcance):

- **Error sin mensaje real**: las decisiones fallaban con un toast genérico
  y la UI ignoraba el cuerpo `{ error }` de las rutas. Ahora
  `lib/accion-errores.ts` traduce los códigos que las rutas SÍ emiten
  (`accion_not_found`, `high_confirmation_not_available`, `backend_timeout`,
  `backend_unavailable`, `unauthenticated`, `no_subscription_in_session`,
  `invalid_accion_id`, `confirmacion_invalida`) y el panel muestra el
  motivo inline con `role="alert"`.
- **Sin estado de éxito visible**: tras aprobar/rechazar/ejecutar el panel
  solo cambiaba de estado en la lista. Ahora muestra confirmación inline
  con `role="status"` y anuncia una sola vez (el contenedor deja de
  anunciar cuando la decisión se tomó en el panel).
- **Sin estado de carga en el panel**: ahora `procesando` bloquea los
  controles, marca `aria-busy` y muestra "Enviando la decisión…".
- **Vacío mudo**: una acción `completed`/`failed` sin resultado no decía
  nada; ahora explica que quedó en ese estado sin resultado en el payload.
- **Panel que desaparecía**: si el refresco de la lista fallaba, la acción
  salía del payload y el panel se cerraba de golpe en medio de una
  decisión. Ahora se conserva el último snapshot de la acción abierta.
- **Historial que se cerraba solo**: el `<details>` estaba atado al filtro
  y se cerraba en cada re-render. Ahora su apertura es estado de React y
  filtrar lo mantiene abierto.
- **Foco perdido en el teclado**: al abrir la confirmación, el botón que
  la abría desaparecía y el foco caía al contenedor; al cancelar no
  volvía. Ahora el foco va al bloque de confirmación y regresa al
  disparador (por referencia viva, porque el botón se re-monta).
- **Nombres accesibles repetidos**: cada tarjeta exponía "Ver detalle"
  sin distinguirse. Ahora es "Ver detalle de <título>".
- **Móvil**: cabecera fija del panel (el contexto se perdía al hacer
  scroll), `overscroll-contain` y filas de decisión/chips con `flex-wrap`.

Verificación del incremento (desde `landing/`):

- `npm test` → 237 pasan / 7 fallan. Los 7 fallos siguen siendo los
  preexistentes de `dashboard-shell.test.tsx`; **no cambió ninguno y no
  apareció un fallo nuevo**.
- `npm run lint` → 0 errores (mismo warning preexistente).
- `npm run typecheck` → limpio.
- `npm run build` → correcto.

Tests añadidos en el incremento: 5 en `lib/accion-errores.test.ts` y 7 en
`app/dashboard/seccion-action-center-detalle.test.tsx` (error real inline
sin duplicar el anuncio, éxito inline, panel que sobrevive a un refresco
fallido, resultado vacío explícito, foco de ida y vuelta, nombres
accesibles únicos, historial abierto tras filtrar y re-renderizar).

Límites de backend: sin cambios respecto al incremento 1 (siguen
faltando `GET /api/automation/acciones/:id` y el historial de eventos por
acción).

## Nota de entorno

Los agentes de código externos no estuvieron disponibles en esta sesión:
la sesión cloud de Claude Code no es alcanzable desde este entorno (sin
login web guardado), el CLI local de Claude Code respondió 401 (OAuth
inválido) y Codex CLI quedó bloqueado por incompatibilidad de versión
con el modelo configurado. La implementación se hizo directamente sobre
el worktree aislado, con verificación local de tests/lint/typecheck.