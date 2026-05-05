# agent/tools_catalog.py — Catálogo declarativo M0 base (T1.6)

"""
Catálogo M0 base del addendum Manus aterrizado en Dona (T1.6).

Sus 3 dimensiones por tool:

  1. **Nivel de riesgo** (M0.1): qué tan irreversible / impactante
     puede ser ejecutar la tool. Tres niveles:

     - "leer": no muta nada externo (DB lectura, fetch info pública,
       resumen). Ej. obtener_saldo, obtener_resumen.
     - "preparar": muta estado interno reversible o costoso de
       deshacer pero NO toca dinero ni terceros. Ej. generar_imagen
       (cobra créditos pero el efecto queda en la cuenta del
       usuario), crear_recordatorio.
     - "ejecutar": efecto irreversible o sobre terceros (envía
       correo, envía mensaje, gasta dinero en Stripe, escribe en
       calendario externo, llamada saliente).

     Esta dimensión hace explícito el patrón `preparar_X` /
     `confirmar_X` ya documentado en CLAUDE.md.

  2. **Categoría de permiso** (M0.2): quién puede ejecutarla y bajo
     qué confirmación. Tres categorías:

     - "autonomo": Dona puede ejecutar sin confirmación humana cada
       vez (lecturas; mutaciones de bajo costo donde el usuario ya
       dio consentimiento implícito al usar el comando).
     - "aprobacion_simple": requiere confirmación corta del usuario
       en el chat ("¿confirmas?"). Aplica a ejecuciones reversibles
       o de costo medio.
     - "aprobacion_fuerte": requiere doble confirmación + permiso
       guardado + límite de gasto si aplica. Reservado para acciones
       irreversibles con impacto externo (cancelación de
       suscripción, envío de correo a terceros, transacciones).

  3. **Costo en créditos** (M0.3): cuántos créditos consume una
     ejecución típica. None si la tool no cobra créditos (ej.
     consultas internas).

El catálogo es **declarativo y read-only**: no muta nada al import.
Lo lee `/admin/tools-catalog` para diagnóstico, y serás extendido
en M1+ cuando los Playbooks consulten qué tools pueden encadenar
según los permisos del usuario.

Convenciones:
  - Toda tool que existe en el código actual debe estar listada acá.
    Si está en código pero falta acá → bug de catálogo, no de runtime.
  - Para no incrementar mantenimiento desproporcionadamente, T1.6
    cataloga los tools _más relevantes_: billing, dashboard, lookup,
    creativos. Las tools internas (rate limiter, dedupe) no entran.
  - Cuando se sume una tool nueva en T1.7+ / M1+, agregarla aquí
    es parte del PR.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


NivelRiesgo = Literal["leer", "preparar", "ejecutar"]
CategoriaPermiso = Literal["autonomo", "aprobacion_simple", "aprobacion_fuerte"]


@dataclass(frozen=True)
class ToolEntry:
    """Una tool catalogada con sus dimensiones M0."""
    nombre: str
    descripcion: str
    nivel_riesgo: NivelRiesgo
    permiso: CategoriaPermiso
    costo_creditos: int | None
    fuente: str  # módulo o endpoint donde vive


# ── Catálogo declarativo ──────────────────────────────────────────────────
# Ordenado por superficie: billing/dashboard primero (los que tocó T1.3-T1.5),
# después lecturas internas, después creativos (anteriores a T1).

CATALOGO: tuple[ToolEntry, ...] = (
    # ── Billing y suscripciones (T1.3 – T1.5) ─────────────────────────────
    ToolEntry(
        nombre="obtener_saldo",
        descripcion="Lee el saldo de créditos del usuario.",
        nivel_riesgo="leer",
        permiso="autonomo",
        costo_creditos=None,
        fuente="agent.billing.obtener_saldo",
    ),
    ToolEntry(
        nombre="obtener_resumen",
        descripcion="Resumen de saldo + total comprado/consumido + últimas 5 trans.",
        nivel_riesgo="leer",
        permiso="autonomo",
        costo_creditos=None,
        fuente="agent.billing.obtener_resumen",
    ),
    ToolEntry(
        nombre="cobrar",
        descripcion="Descuenta créditos del saldo (atómico, falla si insuficiente).",
        nivel_riesgo="ejecutar",
        permiso="aprobacion_simple",
        costo_creditos=None,  # variable según caller
        fuente="agent.billing.cobrar",
    ),
    ToolEntry(
        nombre="acreditar",
        descripcion="Suma créditos al saldo (compra Stripe, regalo, bonus). Idempotente.",
        nivel_riesgo="ejecutar",
        permiso="aprobacion_fuerte",  # nunca debe llamarla el LLM directamente
        costo_creditos=None,
        fuente="agent.billing.acreditar",
    ),
    ToolEntry(
        nombre="crear_checkout_stripe",
        descripcion="Genera URL de Stripe Checkout para que el usuario compre.",
        nivel_riesgo="ejecutar",
        permiso="aprobacion_simple",
        costo_creditos=None,
        fuente="agent.billing.crear_checkout",
    ),
    ToolEntry(
        nombre="cancel_subscription_cap",
        descripcion="Marca subscripción Stripe con cancel_at_period_end=true (T1.4.F).",
        nivel_riesgo="ejecutar",
        permiso="aprobacion_fuerte",
        costo_creditos=None,
        fuente="landing/api/cancel-subscription/route.ts",
    ),
    ToolEntry(
        nombre="abrir_billing_portal",
        descripcion="Crea sesión de Stripe Customer Portal y redirige al usuario (T1.5).",
        nivel_riesgo="ejecutar",
        permiso="aprobacion_simple",  # el usuario ya está logueado y elige acciones dentro del portal
        costo_creditos=None,
        fuente="landing/api/billing-portal/route.ts",
    ),

    # ── Dashboard / read APIs (T1.4) ──────────────────────────────────────
    ToolEntry(
        nombre="leer_usuario_resumen_backend",
        descripcion="Endpoint interno read-only que sirve datos del dashboard (T1.4.C).",
        nivel_riesgo="leer",
        permiso="autonomo",  # protegido por HMAC; solo lo invoca el bridge
        costo_creditos=None,
        fuente="agent.main:/internal/usuario-resumen",
    ),
    ToolEntry(
        nombre="dashboard_data_proxy",
        descripcion="Proxy server-side del landing que sirve /api/dashboard-data (T1.4.D).",
        nivel_riesgo="leer",
        permiso="autonomo",  # protegido por sesión NextAuth
        costo_creditos=None,
        fuente="landing/api/dashboard-data/route.ts",
    ),

    # ── Stripe events (T1.3) ──────────────────────────────────────────────
    ToolEntry(
        nombre="procesar_evento_suscripcion",
        descripcion="Dispatcher de eventos Stripe de suscripción (T1.3.C).",
        nivel_riesgo="ejecutar",
        permiso="aprobacion_fuerte",  # solo el bridge HMAC puede invocarla
        costo_creditos=None,
        fuente="agent.billing.procesar_evento_suscripcion",
    ),

    # ── Creativos (anteriores a T1, ya en producción) ────────────────────
    ToolEntry(
        nombre="generar_imagen_standard",
        descripcion="Genera imagen vía Gemini Flash Image / nanobanana.",
        nivel_riesgo="preparar",  # cobra créditos pero efecto queda en cuenta del usuario
        permiso="aprobacion_simple",
        costo_creditos=2,
        fuente="agent.creativos.imagen",
    ),
    ToolEntry(
        nombre="generar_imagen_premium",
        descripcion="Genera imagen vía Ideogram / Flux Pro Ultra / Recraft.",
        nivel_riesgo="preparar",
        permiso="aprobacion_simple",
        costo_creditos=4,
        fuente="agent.creativos.imagen",
    ),
    ToolEntry(
        nombre="generar_video_corto",
        descripcion="Genera video <10s vía Replicate / Seedance.",
        nivel_riesgo="preparar",
        permiso="aprobacion_simple",
        costo_creditos=150,
        fuente="agent.creativos.video",
    ),
    ToolEntry(
        nombre="generar_voz_tts",
        descripcion="Síntesis de voz vía ElevenLabs.",
        nivel_riesgo="preparar",
        permiso="aprobacion_simple",
        costo_creditos=3,  # cortas; largas=10
        fuente="agent.creativos.voz",
    ),
)


# ── API pública del catálogo ──────────────────────────────────────────────


def listar_tools() -> tuple[ToolEntry, ...]:
    """Retorna todas las tools catalogadas. Read-only."""
    return CATALOGO


def buscar_tool(nombre: str) -> ToolEntry | None:
    """Busca una tool por nombre exacto."""
    for entry in CATALOGO:
        if entry.nombre == nombre:
            return entry
    return None


def tools_por_riesgo(nivel: NivelRiesgo) -> tuple[ToolEntry, ...]:
    """Filtra tools por nivel de riesgo."""
    return tuple(t for t in CATALOGO if t.nivel_riesgo == nivel)


def tools_por_permiso(categoria: CategoriaPermiso) -> tuple[ToolEntry, ...]:
    """Filtra tools por categoría de permiso."""
    return tuple(t for t in CATALOGO if t.permiso == categoria)


def resumen_catalogo() -> dict:
    """
    Snapshot agregado del catálogo para `/admin/tools-catalog`.

    Devuelve:
      - total: int
      - por_riesgo: dict[nivel] -> count
      - por_permiso: dict[categoria] -> count
      - tools: lista serializable
    """
    por_riesgo: dict[str, int] = {}
    por_permiso: dict[str, int] = {}
    tools_serializadas = []
    for entry in CATALOGO:
        por_riesgo[entry.nivel_riesgo] = por_riesgo.get(entry.nivel_riesgo, 0) + 1
        por_permiso[entry.permiso] = por_permiso.get(entry.permiso, 0) + 1
        tools_serializadas.append({
            "nombre": entry.nombre,
            "descripcion": entry.descripcion,
            "nivel_riesgo": entry.nivel_riesgo,
            "permiso": entry.permiso,
            "costo_creditos": entry.costo_creditos,
            "fuente": entry.fuente,
        })
    return {
        "total": len(CATALOGO),
        "por_riesgo": por_riesgo,
        "por_permiso": por_permiso,
        "tools": tools_serializadas,
    }
