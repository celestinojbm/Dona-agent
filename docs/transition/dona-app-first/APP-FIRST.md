# Dona app-first — diseño del producto mínimo (J7)

Objetivo: que **un usuario cree su proyecto, asigne una tarea, supervise su
ejecución y revise la evidencia**, en una aplicación propia de Dona. Sin
WhatsApp, sin Stripe y con proveedores simulados en CI y demo.

Alcance mínimo: **1 área, 1 proyecto, 2 agentes** (responsable y ejecutor).
"Propósito general" significa que el modelo no está atado a un sector;
**no** significa construir para todos a la vez.

Este documento es el diseño previo a escribir código. Cada decisión dice qué
se reutiliza del repo y por qué.

---

## 1. Qué se reutiliza y qué no

| Pieza existente | Decisión | Por qué |
|---|---|---|
| FastAPI `agent/main.py` + bridge HMAC `/internal/*` (`_verificar_y_parsear_internal`) | **Reutilizar** el patrón. Endpoints nuevos en un router propio `agent/app_first/` montado como `/internal/app/*` | El bridge ya resuelve la identidad en el servidor y firma cada llamada. Así se evita meter más código en `main.py` (4.164 líneas) |
| SQLAlchemy 2 async + `create_all` | **Reutilizar** la ruta real de creación del esquema: los modelos `app_*` se registran en `inicializar_db` (tablas nuevas, aditivas). | En la práctica el esquema lo crean `create_all` y las migraciones SQL idempotentes del arranque; Alembic solo tiene 3 versiones y está desfasado. Añadir una versión 004 aislada no lo arregla: se deja como deuda conocida (`docs/CURRENT_STATE.md`) |
| Cola arq + fallback inproc (`agent/jobs/`) | **Reutilizar arq** como transporte. **No** reutilizar `jobs_creativos`: está indexada por teléfono y es de creativos | La ejecución necesita lease, intentos e idempotencia propios |
| `agent/automation/audit.py` (`sanitizar_payload`, `registrar_evento`) | **Reutilizar el sanitizador**. El registro de actividad es una tabla nueva por workspace | El audit log actual está indexado por teléfono |
| `agent/automation/permissions.py` (LOW/MEDIUM/HIGH/CRITICAL) | **Reutilizar la taxonomía de riesgo** | Es el contrato de "operación reservada → aprobación" |
| Créditos (`billing.py`, `automation/credits.py`) | **No en J7**. Presupuesto por workspace en unidades internas; los créditos vuelven con el relanzamiento | Los créditos están indexados por teléfono y atados a Stripe |
| Landing Next.js + NextAuth (`landing/`) | **Reutilizar** el proyecto, los componentes y el bridge. Rutas nuevas bajo `/app/*`. Proveedor de credenciales **propio**, no derivado de Stripe | Un segundo frontend sería una plataforma paralela sin justificación |
| `brain.py` (LLM con ~36 tools) | **No** se reutiliza como agente. Se extraen helpers puntuales si hacen falta | Es un bucle conversacional por teléfono; acoplarlo arrastraría WhatsApp y créditos |
| `automation/missions.py` (sin conectar) | Fuente de ideas para estados y razones cerradas; no se conecta | Modela "recuperar lead" por WhatsApp |

## 2. Separación respecto a la pausa

`DONA_EN_PAUSA` sigue bloqueando lo **comercial y lo antiguo** (checkout,
portal, dashboard anterior, WhatsApp). La app nueva vive detrás de **otro**
interruptor, `PILOTO_APP` (constante en código, `false` hasta J8), y de una
**lista de invitación** en el servidor. Que la web pública siga en pausa y
el piloto esté abierto a invitados no se contradicen.

## 3. Modelo de datos (tablas nuevas, prefijo `app_`)

```
app_usuarios          id, email (único, normalizado), password_hash (argon2id), creado, desactivado
app_workspaces        id, nombre, creado_por, creado
app_membresias        workspace_id, usuario_id, rol (owner|admin|miembro), creado        PK(workspace_id, usuario_id)
app_areas             id, workspace_id, nombre, descripcion
app_proyectos         id, workspace_id, area_id, nombre, objetivo, criterios_aceptacion (json), responsable_usuario_id, estado
app_agentes           id, workspace_id, nombre, rol (responsable|ejecutor), instrucciones,
                      herramientas_permitidas (json), modelo, presupuesto_max_unidades
app_tareas            id, workspace_id, proyecto_id, titulo, descripcion, asignada_a_agente_id,
                      estado, motivo_bloqueo, creada_por, creado, actualizado
app_ejecuciones       id, workspace_id, tarea_id, agente_id, intento, estado, clave_idempotencia (única),
                      lease_hasta, iniciada, terminada, error_codigo, unidades_consumidas
app_aprobaciones      id, workspace_id, ejecucion_id, operacion, riesgo, preview (json), estado
                      (pendiente|aprobada|rechazada|caducada), decidida_por, decidida_en
app_evidencias        id, workspace_id, ejecucion_id, tipo (texto|archivo|enlace|registro), contenido/ruta, hash_sha256, creado
app_actividad         id, workspace_id, actor (usuario|agente|sistema), evento, objeto, datos (json sanitizado), creado
app_consumo           id, workspace_id, ejecucion_id, proveedor, unidades, simulado (bool), creado
app_mensajes_proyecto id, workspace_id, proyecto_id, tarea_id (null), autor, contenido, creado
```

**Toda** fila lleva `workspace_id`, y toda consulta se filtra por el
workspace de la sesión en el servidor. Un id de otro workspace devuelve 404
(no 403), para no revelar que existe.

## 4. Estados

Tarea: `pendiente → en_ejecucion → (necesita_aprobacion ↔ en_ejecucion) → completada | fallida | bloqueada | cancelada`.

Ejecución: `encolada → en_curso → esperando_aprobacion → en_curso → terminada | fallida | cancelada | abandonada`.

- Los agentes **no** son procesos permanentes: la UI muestra
  **ejecuciones** con estado y hora reales, nunca "agente trabajando" sin
  una ejecución viva detrás.
- `bloqueada` siempre lleva `motivo_bloqueo` de un conjunto cerrado
  (`presupuesto_agotado`, `aprobacion_rechazada`, `herramienta_no_permitida`,
  `proveedor_no_disponible`, `criterios_no_cumplidos`).

## 5. Ejecución en segundo plano

- Encolar = insertar `app_ejecuciones(encolada)` con `clave_idempotencia`
  (tarea + intento) **y** encolar en arq. Reintentar encolar no duplica:
  la clave es única.
- El worker **reclama** con `UPDATE ... SET estado='en_curso',
  lease_hasta=now()+N WHERE id=? AND estado='encolada'` (Postgres:
  `FOR UPDATE SKIP LOCKED`). Si no reclama, no ejecuta.
- **Concurrencia**: máximo de ejecuciones en curso por workspace y global
  (`ARQ_MAX_JOBS`).
- **Recuperación**: un reaper marca `abandonada` las ejecuciones con
  `lease_hasta` vencido y crea un nuevo intento si quedan intentos. Efectos
  con side effects **solo** detrás de aprobación y con su propia clave de
  idempotencia: un reintento no repite el efecto.
- **Cancelación**: marca la tarea `cancelada`; el worker comprueba el estado
  entre pasos. Límite documentado: una llamada al proveedor ya en vuelo
  termina; su resultado se descarta.

## 6. Agentes y proveedores

- **Responsable**: descompone el objetivo del proyecto en tareas, revisa la
  evidencia contra los criterios de aceptación y marca completada o
  devuelve la tarea con motivo.
- **Ejecutor**: ejecuta una tarea con sus `herramientas_permitidas`. En J7
  las herramientas son internas: redactar documento, resumir, checklist. Hay
  además una operación **reservada** de ejemplo (`publicar_resultado`) que
  siempre pasa por `app_aprobaciones`.
- Interfaz `ProveedorModelo.generar(mensajes, herramientas, presupuesto)`:
  - `simulado`: determinista, sin red. Es el que usan CI y la demo, y la
    UI lo muestra con la etiqueta **"simulado"**.
  - `anthropic`: solo con variable explícita, y **después** de comprobar el
    presupuesto (reserva antes de llamar, consumo real después). Sin
    llamadas facturables en J7.
- El patrón `preparar_X / confirmar_X / cancelar_X` de `CLAUDE.md` § 3.1 se
  mantiene para toda operación reservada.

## 7. Acceso

- Registro y acceso con **email + contraseña** propios (argon2id en el
  backend). El login no consulta Stripe. Recuperar acceso por correo queda
  para cuando haya un proveedor de correo verificado; en el piloto, reset
  manual de un admin con registro en `app_actividad`.
- NextAuth en la landing con un proveedor `cuenta` que llama a
  `/internal/app/auth/verificar` por el bridge HMAC.
- La sesión lleva `usuario_id`; el **workspace activo se resuelve en el
  servidor** con la membresía. Nunca se toma un `workspace_id` del cliente
  sin comprobarlo.
- Permisos en el servidor: `owner/admin` gestionan agentes y presupuesto;
  `miembro` crea tareas y aprueba solo si es responsable del proyecto.

## 8. Pantallas mínimas

1. **Inicio**: proyectos y actividad reciente.
2. **Área**: una inicial, configurable (nombre, descripción).
3. **Proyecto**: objetivo, criterios de aceptación, responsable, tareas por estado.
4. **Tarea**: ejecuciones con estados reales, evidencia, aprobación
   pendiente, reintentar/cancelar.
5. **Chat del proyecto**: mensajes vinculados al proyecto o a una tarea.
6. **Agentes**: responsable y ejecutor; instrucciones, herramientas, presupuesto.

Diseño: la identidad visual actual (tokens de `landing/app/globals.css`,
tipografía, componentes Radix/shadcn ya instalados). Incluye estados
vacíos, errores y navegación móvil. Ninguna animación se presenta como
prueba de trabajo.

## 9. Pruebas obligatorias (mocks, sin red)

- Dos usuarios en workspaces distintos: lectura y escritura cruzadas → 404.
- Tarea completa: encolar → ejecutar → evidencia → revisión del responsable → completada.
- Aprobación: la operación reservada queda en `necesita_aprobacion`; rechazar → `bloqueada`; aprobar → continúa.
- Fallo del proveedor → `fallida` con código; reintento → nuevo intento **sin** duplicar evidencia ni efectos.
- Reinicio del worker con una ejecución en curso → el reaper la marca `abandonada` y reintenta.
- Presupuesto agotado → `bloqueada` **antes** de llamar al proveedor.
- Encolar dos veces la misma clave → una sola ejecución.

## 10. Entrega en PRs pequeños

| PR | Contenido | Verificable por |
|---|---|---|
| J7.1 | Modelo aditivo + repositorio con aislamiento por workspace | tests de aislamiento y de esquema aditivo (las tablas antiguas siguen intactas) |
| J7.2 | Runner: encolado idempotente, claim con lease, reaper, cancelación; `ProveedorModelo` simulado | tests de concurrencia, reintento y reinicio |
| J7.3 | Agentes responsable/ejecutor, aprobaciones, evidencia, actividad | flujo completo con proveedor simulado |
| J7.4 | Registro/acceso propio + bridge `/internal/app/*` + permisos | tests de auth y de permisos |
| J7.5 | UI `/app/*` (inicio, área, proyecto, tarea, chat, agentes), móvil | vitest + build + capturas |
| J7.6 | Datos sintéticos de demo + guía (qué es real, qué es simulado) | recorrido documentado en `EVIDENCIA.md` |

## 11. Marcha atrás

`PILOTO_APP = false` oculta la app sin borrar datos. Las migraciones son
aditivas (tablas `app_*` nuevas). Revertir un PR no toca las tablas
existentes.
