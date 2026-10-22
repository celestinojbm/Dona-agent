"""Política RLS de Dona — fuente única de verdad (0B).

Este módulo declara el inventario de tablas existentes que deben quedar con
Row Level Security habilitado y genera el SQL para habilitarlo/revertirlo. Lo
consume la migración `alembic/versions/004_rls_tablas_existentes.py` y los tests
de `tests/security/test_rls.py`, de modo que la migración, la matriz de acceso y
las pruebas no se desincronicen.

Contrato de acceso (ver docs/security/supabase-access-matrix.md):

  Objetivo decidido por Celestino (2026-10-21): contrato (b) — Supabase Auth con
  `auth.uid()` como identidad (cuenta = persona). Pero (b) exige un mapeo real
  `auth.uid()` ↔ propietario que aún NO existe en el esquema (tablas por
  `telefono`), así que esta migración mantiene el estado base, que es
  compatible hacia adelante con (b):

      RLS habilitado + SIN políticas para `anon`/`authenticated` → denegado por
      defecto. El navegador no accede directo (pasa por FastAPI con bridge HMAC);
      el backend conecta con el rol dueño/`service_role` (que evita RLS). Las
      políticas `USING (auth_user_id = auth.uid())` se añaden en un follow-up,
      recién cuando exista la columna de mapeo y su backfill verificado (NO usar
      `auth.uid() = usuario_id` sin correspondencia real).

Límite honesto: `service_role`/dueño EVITAN RLS. RLS protege contra acceso
directo del navegador vía PostgREST, NO contra errores de la propia FastAPI
(que corre con un rol que evita RLS). La defensa frente a bugs del backend es el
filtrado por propietario en los endpoints, no RLS.

El teléfono del cliente NO prueba identidad: estas tablas nunca deben quedar
expuestas a `anon`/`authenticated` sólo porque la fila tenga una columna
`telefono`.
"""

from __future__ import annotations

# Inventario autoritativo de tablas existentes (modelos ORM sobre el Base único
# de agent.memory). El test test_rls.py cruza esta lista contra
# Base.metadata.tables para que no se desincronice al agregar modelos.
TABLAS_RLS: tuple[str, ...] = (
    # agent/memory.py
    "mensajes",
    "timezone_usuarios",
    "recordatorios",
    "usuario_ubicacion",
    "noticias_enviadas",
    "usuario_estado_emocional",
    "eventos_emocionales",
    "usuario_onboarding",
    "usuario_proactividad",
    "eventos_comportamiento",
    "perfil_aprendizaje",
    "usuario_mirofish",
    "usuario_google_auth",
    "memoria_largo_plazo",
    "tareas",
    "listas",
    "items_lista",
    "eventos_usuario",
    "mensajes_procesados",
    "recordatorios_gcal_enviados",
    "solicitudes_privacidad",
    "sesiones_conversacion",
    "assets_generados",
    "jobs_creativos",
    "saldo_creditos",
    "transacciones_credito",
    "idempotencia_credito",
    # F3 · telemetría de uso por proveedor (recibo por acción). Declarada aquí
    # para que test_rls.py cuadre la lista contra los modelos (su modelo vive en
    # agent/memory.py). RLS se habilita además en la migración 005 y en
    # _MIGRACIONES.
    "uso_proveedor_accion",
    "suscripcion_stripe",
    "evento_stripe_procesado",
    "usuarios",
    # agent/business/models.py
    "perfil_negocio",
    "clientes_negocio",
    "productos_negocio",
    "transacciones_negocio",
    "pedidos_negocio",
    "seguimientos_negocio",
    "cotizaciones_negocio",
    # agent/automation/models.py
    "acciones_automatizacion",
    "automation_reservas_credito",
    "audit_log_automatizacion",
    "automation_consentimientos_tercero",
    "automation_envios_tercero",
    "automation_misiones",
    # enhanced/models.py
    "system_catalog",
    "user_systems",
    "system_activity_logs",
    # agent/dashboard_lockout.py
    "dashboard_login_intentos",
)

# Roles de Supabase expuestos al navegador vía PostgREST. Se les revoca todo
# acceso como defensa en profundidad (RLS ya los deniega por defecto).
ROLES_NAVEGADOR: tuple[str, ...] = ("anon", "authenticated")


def _revoke_do_block(tabla: str) -> str:
    """REVOKE ALL role-gated: sólo revoca si el rol existe (Supabase lo tiene;
    un Postgres de pruebas genérico puede no tenerlo)."""
    cuerpos = "\n".join(
        f"""  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{rol}') THEN
    EXECUTE 'REVOKE ALL ON TABLE \"{tabla}\" FROM {rol}';
  END IF;"""
        for rol in ROLES_NAVEGADOR
    )
    return f"DO $$\nBEGIN\n{cuerpos}\nEND\n$$;"


def _grant_do_block(tabla: str) -> str:
    """Reverso del revoke: re-GRANT ALL role-gated (sólo para downgrade)."""
    cuerpos = "\n".join(
        f"""  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{rol}') THEN
    EXECUTE 'GRANT ALL ON TABLE \"{tabla}\" TO {rol}';
  END IF;"""
        for rol in ROLES_NAVEGADOR
    )
    return f"DO $$\nBEGIN\n{cuerpos}\nEND\n$$;"


def sentencias_habilitar_rls(tablas: tuple[str, ...] = TABLAS_RLS) -> list[str]:
    """SQL (PostgreSQL) para habilitar RLS y revocar grants del navegador.

    Devuelve una lista de sentencias independientes; la migración las ejecuta en
    orden. NO incluye políticas porque el contrato (a) deniega por defecto a
    anon/authenticated (sin política = sin acceso bajo RLS).
    """
    out: list[str] = []
    for t in tablas:
        out.append(f'ALTER TABLE "{t}" ENABLE ROW LEVEL SECURITY;')
        out.append(_revoke_do_block(t))
    return out


def sentencias_revertir_rls(tablas: tuple[str, ...] = TABLAS_RLS) -> list[str]:
    """SQL (PostgreSQL) para revertir: deshabilita RLS y re-otorga grants.

    ADVERTENCIA: ejecutar esto reabre el acceso directo del navegador. Es el
    reverso formal de la migración; no debe correrse en producción como atajo.
    Regla operativa: nunca desactivar RLS globalmente (ver el plan).
    """
    out: list[str] = []
    for t in tablas:
        out.append(_grant_do_block(t))
        out.append(f'ALTER TABLE "{t}" DISABLE ROW LEVEL SECURITY;')
    return out
