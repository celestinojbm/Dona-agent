# Matriz de acceso a Supabase / PostgreSQL (0B)

**Fecha:** 2026-10-20 · **Alcance:** las 47 tablas ORM del `Base` único de
`agent/memory.py` (incluye `business`, `automation`, `enhanced`,
`dashboard_lockout`). Fuente única de verdad de la lista y el SQL:
`agent/rls_policy.py`. Migración: `alembic/versions/004_rls_tablas_existentes.py`.

> Esta matriz documenta **qué accede a cada tabla hoy** y **qué contrato de RLS
> se aplica**. No cambia precios, cobros ni integraciones. Los tests reales de
> RLS corren contra PostgreSQL aislado (`tests/security/test_rls.py`,
> gated por `DONA_TEST_POSTGRES_URL`); NO se aplicó ninguna migración remota.

## Arquitectura de acceso real (verificada en el código)

- El **navegador** (dashboard `landing/`, Next.js) **no habla con Supabase
  directamente**. Llama a FastAPI (`/internal/*`, `/api/*`) con el bridge HMAC
  (`X-Internal-Signature`). No hay cliente de Supabase en el front.
- El **backend** (FastAPI + worker `arq`) usa un único `DATABASE_URL`
  (SQLAlchemy async). En Supabase ese rol es el dueño / `service_role`, que
  **evita RLS**.
- El **teléfono del cliente no prueba identidad**: una columna `telefono` en una
  fila no autoriza a nadie; la autorización vive en los endpoints de FastAPI.

## Contrato elegido: (a) acceso sólo-backend

Se elige el contrato **(a)** del plan: el navegador no tiene acceso directo a la
base; todo pasa por FastAPI. Por tanto:

- RLS **habilitado** en las 47 tablas.
- **Sin políticas** para `anon`/`authenticated`: bajo RLS, sin política = acceso
  denegado por defecto. Es exactamente lo que queremos para el navegador.
- **REVOKE ALL** de `anon`/`authenticated` (defensa en profundidad, role-gated).
- El backend (dueño/`service_role`) **evita RLS** y sigue operando sin cambios:
  no se añaden políticas para el rol backend porque no las necesita.

No se adopta el contrato (b) (Supabase Auth con `auth.uid()` + membresías)
porque hoy **no existe** Supabase Auth en la app ni un mapeo verificable
`auth.uid()` ↔ propietario. Usar `auth.uid() = usuario_id` sin esa
correspondencia sería incorrecto. Reabrir a (b) es una decisión de producto
(ver `preguntas-celestino.md`, puntos 2–3).

## Límite honesto (no sobrevender RLS)

`service_role` y el rol dueño **evitan RLS**. RLS protege contra el acceso
directo del navegador vía PostgREST; **no** protege contra bugs de la propia
FastAPI (que corre con un rol que evita RLS). La defensa contra errores del
backend es el **filtrado por propietario en los endpoints**, no RLS. Las tablas
nuevas de este plan (F3/F1/F14/F12) van además **backend-only con políticas
explícitas** y sin acceso de `anon`/`authenticated`.

## Inventario y clasificación

Leyenda sensibilidad: **crítica** (dinero, suscripción, credenciales, permisos),
**alta** (PII/contenido del negocio y del cliente), **media** (telemetría/estado
operativo). Lectores/escritores: todos **backend** (FastAPI/worker); el
navegador siempre es **indirecto** vía FastAPI.

### Dinero, identidad y credenciales — **crítica** (revisar con prioridad)

| Tabla | Clave propietario | Qué guarda | Nota |
|---|---|---|---|
| `usuarios` | id/telefono | identidad interna del usuario | nunca expuesta al navegador |
| `saldo_creditos` | telefono | saldo entero de créditos | sólo backend escribe; jamás escritura directa |
| `transacciones_credito` | telefono | ledger de créditos (audit trail) | append-only de hecho; base de F3 |
| `idempotencia_credito` | clave idempotencia | dedupe de cobros | integridad de cobros |
| `suscripcion_stripe` | telefono/stripe ids | plan, estado, welcome flag | datos de pago |
| `evento_stripe_procesado` | stripe_session_id | idempotencia webhook Stripe | integridad de pagos |
| `usuario_google_auth` | telefono | tokens OAuth (cifrados Fernet) | credenciales |
| `dashboard_login_intentos` | email/clave | lockout anti fuerza-bruta | seguridad de login |

### Negocio y cliente — **alta** (PII / contenido)

| Tabla | Clave | Qué guarda |
|---|---|---|
| `perfil_negocio` | telefono | perfil del negocio del dueño |
| `clientes_negocio` | telefono | **clientes del dueño (PII de terceros)** |
| `productos_negocio` | telefono | catálogo |
| `transacciones_negocio` | telefono | ingresos/gastos |
| `pedidos_negocio` | telefono | pedidos |
| `seguimientos_negocio` | telefono | seguimientos/leads |
| `cotizaciones_negocio` | telefono | cotizaciones |
| `mensajes` | telefono | historial de conversación |
| `memoria_largo_plazo` | telefono | memoria del usuario |
| `sesiones_conversacion` | telefono | sesiones |
| `assets_generados` | telefono | artefactos (imágenes, etc.) |
| `solicitudes_privacidad` | telefono | export/delete CCPA |

### Automatización (Action Center) — **alta/crítica**

| Tabla | Clave | Nota |
|---|---|---|
| `acciones_automatizacion` | telefono | acciones con nivel de riesgo |
| `automation_reservas_credito` | telefono/accion | reservas write-ahead de crédito |
| `audit_log_automatizacion` | telefono/accion | audit log del pipeline |
| `automation_consentimientos_tercero` | telefono | consentimiento de terceros (TCPA) |
| `automation_envios_tercero` | telefono | envíos a terceros |
| `automation_misiones` | telefono | misiones |

### Estado operativo / telemetría — **media**

`timezone_usuarios`, `recordatorios`, `recordatorios_gcal_enviados`,
`usuario_ubicacion`, `noticias_enviadas`, `usuario_estado_emocional`,
`eventos_emocionales`, `usuario_onboarding`, `usuario_proactividad`,
`eventos_comportamiento`, `perfil_aprendizaje`, `usuario_mirofish`, `tareas`,
`listas`, `items_lista`, `eventos_usuario`, `mensajes_procesados`,
`jobs_creativos`, `system_catalog`, `user_systems`, `system_activity_logs`.

Todas: propietario por `telefono` (salvo catálogos del sistema), lectura/
escritura **sólo backend**, navegador indirecto. RLS habilitado igual que el
resto (no se filtra por "ser menos sensible").

## Vistas, funciones y RPCs

No se detectaron vistas `SECURITY DEFINER` ni RPCs propias en el repo (el acceso
es por SQLAlchemy desde el backend). Si Supabase expone RPCs/Views creadas fuera
del repo, revisar su `search_path` y `SECURITY DEFINER` antes de producción
(checklist de despliegue). Esta matriz cubre sólo las tablas de los modelos.

## Pruebas

- **Siempre:** la lista `TABLAS_RLS` no se desincroniza de los modelos; el SQL
  habilita RLS + revoca navegador por tabla; la migración es no-op en SQLite.
- **PostgreSQL aislado (gated):** `anon` denegado (0 filas / INSERT rechazado)
  tras habilitar RLS; el dueño sigue viendo todo. SKIP sin
  `DONA_TEST_POSTGRES_URL`.

## Checklist antes de producción (no ejecutado aquí)

1. Backup restaurable de la base.
2. Ensayo de la migración en **copia aislada** (no producción).
3. Verificar que backend + `arq` + onboarding + cobro + `/admin` válidos siguen
   funcionando bajo RLS.
4. Revisar vistas/RPC/`SECURITY DEFINER`/`search_path` si existen fuera del repo.
5. OK explícito de Celestino.
6. Nunca desactivar RLS globalmente; si una política bloquea un recorrido real,
   corregir la política, no apagar RLS.
