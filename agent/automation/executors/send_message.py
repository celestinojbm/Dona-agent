# agent/automation/executors/send_message.py — T2.2 · primer HIGH

"""
Ejecutor HIGH para enviar mensajes de WhatsApp via el proveedor
configurado. Sigue el patrón preparar → aprobar → confirmar/ejecutar:

  1. preparar_enviar_mensaje_whatsapp(...)
       → crea la acción HIGH en estado 'needs_approval' con el
         destinatario y el cuerpo guardados en payload. NUNCA envía.
  2. aprobar_accion(accion_id)
       → el usuario aprueba explícitamente la acción.
  3. confirmar_enviar_mensaje_whatsapp(accion_id)
       → atajo que aprueba (si está needs_approval) y ejecuta. Si la
         acción ya estaba 'completed' devuelve el resultado existente
         sin re-enviar (idempotente).

El ejecutor real, llamado por agent.automation.execution.ejecutar_accion
cuando el estado es 'approved':

  - Lee payload (numero_destino + mensaje) y lo valida.
  - Antes de invocar al proveedor, RE-LEE result_json desde DB. Si ya
    contiene <estado_envio='sent' + mensaje_id>, devuelve el dict
    existente con flag idempotent=True · NUNCA llama al proveedor dos
    veces para la misma acción.
  - Llama proveedor.enviar_mensaje. Si retorna False, lanza
    RuntimeError · ejecutar_accion atrapará la excepción y liberará la
    reserva de créditos.
  - Si retorna True, persiste el resultado en result_json INMEDIATAMENTE
    (antes de retornar) para que un crash entre el envío y
    marcar_completada NO pierda la huella de idempotencia.

Seguridad:
  - El payload pasa por sanitización antes de logear. Nunca se logea
    el número destino completo · sólo prefijo+sufijo (telefono_short).
  - El token de Whapi se lee del provider · este módulo no lo toca.
  - Idempotency key: el campo accion_id ya es UNIQUE en
    automation_reservas_credito · garantiza que reservar() no doble
    cobre. La idempotencia de envío se duplica en result_json.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any

logger = logging.getLogger("dona")

# Longitud máxima del mensaje · tope conservador. Whapi permite hasta
# ~4096 chars en mensajes de texto · dejamos 4000 para evitar borderline.
MAX_LEN_MENSAJE = 4000


# ── API de orquestación · preparar / confirmar ───────────────────────


async def preparar_enviar_mensaje_whatsapp(
    *,
    telefono: str,
    numero_destino: str,
    mensaje: str,
    titulo: str = "",
    descripcion: str = "",
    razon_recomendacion: str = "",
) -> dict[str, Any]:
    """Crea una acción HIGH 'enviar_mensaje_whatsapp' en estado
    'needs_approval' (porque clasificar_riesgo la marca HIGH). NUNCA
    envía nada.

    Args:
        telefono: dueño del negocio (usuario de Dona · NO el destinatario).
        numero_destino: a quién se enviará el mensaje.
        mensaje: cuerpo del mensaje.
        titulo / descripcion / razon_recomendacion: metadata para Action
            Center · descripcion default = primeros 300 chars del mensaje.

    Returns:
        dict de la acción creada · estado 'needs_approval' · 'created':
        True/False.

    Raises:
        ValueError si numero_destino o mensaje son inválidos.
    """
    _validar_numero(numero_destino)
    _validar_mensaje(mensaje)

    from agent.automation.action_center import crear_accion
    accion = await crear_accion(
        telefono=telefono,
        tipo_accion="enviar_mensaje_whatsapp",
        titulo=(titulo or "Enviar mensaje WhatsApp")[:200],
        descripcion=(descripcion or mensaje)[:1000],
        razon_recomendacion=razon_recomendacion,
        payload={
            "numero_destino": numero_destino.strip(),
            "mensaje": mensaje.strip(),
        },
    )
    logger.info(
        f"[EXEC-HIGH] preparar_enviar_mensaje_whatsapp "
        f"accion_id={accion['id']} destino_short={_short_num(numero_destino)} "
        f"longitud={len(mensaje)} estado={accion['estado']}"
    )
    return accion


async def preview_confirmacion_high_whatsapp(
    accion_id: int,
) -> dict[str, Any]:
    """Preview dedicado para una acción HIGH de envío WhatsApp.

    No ejecuta, no aprueba, no toca proveedores externos. Sólo devuelve
    datos necesarios para que el dueño vea destino, mensaje, costo y riesgo
    antes de escribir la confirmación literal.
    """
    accion = await _leer_accion_fresca(accion_id)
    if accion is None:
        return {"ok": False, "error": "accion_no_existe", "accion_id": accion_id}
    if accion.get("tipo_accion") != "enviar_mensaje_whatsapp":
        return {
            "ok": False,
            "error": "tipo_accion_no_soportado",
            "accion_id": accion_id,
        }
    if accion.get("riesgo") != "high":
        return {"ok": False, "error": "riesgo_no_high", "accion_id": accion_id}
    if accion.get("estado") != "approved":
        return {
            "ok": False,
            "error": "accion_no_aprobada",
            "estado": accion.get("estado"),
            "accion_id": accion_id,
        }

    payload = _parse_json(accion.get("payload_json")) or {}
    numero_destino = str(payload.get("numero_destino") or "")
    mensaje = str(payload.get("mensaje") or "")
    if not numero_destino.strip() or not mensaje.strip():
        return {
            "ok": False,
            "error": "payload_invalido",
            "accion_id": accion_id,
        }

    return {
        "ok": True,
        "accion_id": accion_id,
        "tipo_accion": "enviar_mensaje_whatsapp",
        "titulo": accion.get("titulo", ""),
        "descripcion": accion.get("descripcion", ""),
        "riesgo": "high",
        "estado": accion.get("estado"),
        "costo_creditos_estimado": accion.get("costo_creditos_estimado", 0),
        "destino_short": _short_num(numero_destino),
        # El número completo y mensaje sólo se exponen al dueño autenticado
        # vía endpoint dedicado; nunca se logean en este helper.
        "numero_destino": numero_destino,
        "mensaje_preview": mensaje,
        "longitud_mensaje": len(mensaje),
        "confirmacion_requerida": "ENVIAR",
    }


async def confirmar_high_whatsapp_dedicado(
    accion_id: int,
    confirmacion: str,
) -> dict[str, Any]:
    """Materializa una acción HIGH ya aprobada desde UX dedicada.

    A diferencia del atajo histórico confirmar_enviar_mensaje_whatsapp(),
    este camino NO auto-aprueba. Exige estado exactamente 'approved' y
    confirmación exactamente 'ENVIAR' sin normalizar/strip, para que
    ' ENVIAR ' o variantes no pasen por accidente.
    """
    if confirmacion != "ENVIAR":
        return {
            "estado_final": "failed",
            "error": "confirmacion_invalida",
            "accion_id": accion_id,
        }

    accion = await _leer_accion_fresca(accion_id)
    if accion is None:
        return {
            "estado_final": "failed",
            "error": "accion_no_existe",
            "accion_id": accion_id,
        }
    if accion.get("tipo_accion") != "enviar_mensaje_whatsapp":
        return {
            "estado_final": "failed",
            "error": "tipo_accion_no_soportado",
            "accion_id": accion_id,
        }
    if accion.get("riesgo") != "high":
        return {
            "estado_final": "failed",
            "error": "riesgo_no_high",
            "accion_id": accion_id,
        }
    if accion.get("estado") != "approved":
        return {
            "estado_final": "failed",
            "error": "accion_no_aprobada",
            "estado": accion.get("estado"),
            "accion_id": accion_id,
        }

    from agent.automation.execution import ejecutar_accion
    return await ejecutar_accion(accion)


async def confirmar_enviar_mensaje_whatsapp(
    accion_id: int,
) -> dict[str, Any]:
    """Aprueba (si hace falta) y ejecuta la acción · operación
    'confirmar' del patrón.

    Idempotente: si la acción ya está 'completed', devuelve el resultado
    existente sin re-enviar. Si está 'failed' o 'rejected', no ejecuta
    (devuelve error claro). Si está 'needs_approval', aprueba primero y
    luego ejecuta. Si está 'approved', ejecuta directo.
    """
    accion = await _leer_accion_fresca(accion_id)
    if accion is None:
        return {
            "estado_final": "failed",
            "error": "accion_no_existe",
            "accion_id": accion_id,
        }

    estado = accion["estado"]

    if estado == "completed":
        # Ya enviada · devolver resultado existente
        resultado_prev = _parse_json(accion.get("result_json"))
        return {
            "estado_final": "completed",
            "result": resultado_prev or {},
            "idempotent": True,
        }
    if estado in ("rejected", "cancelled"):
        return {
            "estado_final": estado,
            "error": f"accion_{estado}",
            "accion_id": accion_id,
        }
    if estado == "failed":
        return {
            "estado_final": "failed",
            "error": "accion_previamente_fallida",
            "accion_id": accion_id,
        }

    if estado == "needs_approval":
        from agent.automation.action_center import aprobar_accion
        await aprobar_accion(accion_id)
        accion = await _leer_accion_fresca(accion_id)
        if accion is None or accion["estado"] != "approved":
            return {
                "estado_final": "failed",
                "error": "no_se_pudo_aprobar",
                "accion_id": accion_id,
            }

    from agent.automation.execution import ejecutar_accion
    return await ejecutar_accion(accion)


# ── Ejecutor real (llamado por ejecutar_accion en execution.py) ──────


async def ejecutor_enviar_mensaje_whatsapp(
    accion: dict[str, Any], perfil: dict[str, Any] | None,
) -> dict[str, Any]:
    """Envía el mensaje vía el proveedor configurado. Idempotente por
    accion_id (dedup en result_json). Lanza RuntimeError si el provider
    falla · ejecutar_accion lo atrapará y liberará la reserva.

    El parámetro perfil no se usa hoy · queda para evoluciones futuras
    (e.g. personalizar el mensaje con datos del negocio).
    """
    accion_id = accion["id"]
    payload = _parse_json(accion.get("payload_json")) or {}
    numero_destino = (payload.get("numero_destino") or "").strip()
    mensaje = (payload.get("mensaje") or "").strip()

    if not numero_destino or not mensaje:
        raise ValueError(
            "payload inválido: numero_destino y mensaje son obligatorios"
        )

    # ── Idempotencia · re-leer result_json desde DB (no del dict stale)
    fresh_result = await _leer_result_actual(accion_id)
    if (
        fresh_result
        and fresh_result.get("estado_envio") == "sent"
        and fresh_result.get("mensaje_id")
    ):
        logger.info(
            f"[EXEC-HIGH] enviar_mensaje_whatsapp accion_id={accion_id} "
            f"ya enviada · skip · mensaje_id={fresh_result['mensaje_id']}"
        )
        return {**fresh_result, "idempotent": True}

    # ── Envío real via proveedor
    proveedor = _obtener_proveedor()
    nombre_proveedor = proveedor.__class__.__name__

    ok = False
    try:
        ok = await proveedor.enviar_mensaje(numero_destino, mensaje)
    except Exception as e:
        # Provider lanzó · propagamos como RuntimeError uniforme · la
        # ejecutar_accion catch atrapará y liberará la reserva.
        logger.error(
            f"[EXEC-HIGH] proveedor.enviar_mensaje raised "
            f"({type(e).__name__}) accion_id={accion_id}"
        )
        raise RuntimeError(
            f"provider_enviar_mensaje_excepcion: {type(e).__name__}"
        ) from e

    if not ok:
        logger.warning(
            f"[EXEC-HIGH] proveedor.enviar_mensaje devolvió False "
            f"accion_id={accion_id} destino_short={_short_num(numero_destino)}"
        )
        raise RuntimeError("provider_enviar_mensaje_failed")

    mensaje_id = _generar_mensaje_id(accion_id)
    resultado: dict[str, Any] = {
        "estado_envio": "sent",
        "mensaje_id": mensaje_id,
        "destino_short": _short_num(numero_destino),
        "longitud_mensaje": len(mensaje),
        "modo": "provider",
        "provider": nombre_proveedor,
        "enviado_en": datetime.utcnow().isoformat(),
    }

    # ── Persistir result_json INMEDIATAMENTE para dedupe en retries
    # (antes de que ejecutar_accion llame marcar_completada · si crash,
    # cualquier retry verá estado_envio=sent y no re-enviará)
    await _persistir_result_inline(accion_id, resultado)

    logger.info(
        f"[EXEC-HIGH] enviar_mensaje_whatsapp accion_id={accion_id} "
        f"destino_short={resultado['destino_short']} "
        f"longitud={resultado['longitud_mensaje']} provider={nombre_proveedor}"
    )
    return resultado


# ── Helpers internos ─────────────────────────────────────────────────


def _validar_numero(num: str) -> None:
    if not num or not num.strip():
        raise ValueError("numero_destino es obligatorio")
    s = num.strip()
    if len(s) < 6 or len(s) > 32:
        raise ValueError("numero_destino fuera de rango (6..32 chars)")
    # Aceptamos sólo dígitos opcionalmente con '+'. WhatsApp usa
    # variantes locales pero como regla general el destinatario es
    # numérico.
    cuerpo = s[1:] if s.startswith("+") else s
    if not cuerpo.isdigit():
        raise ValueError(
            "numero_destino debe contener sólo dígitos (con '+' opcional)"
        )


def _validar_mensaje(msg: str) -> None:
    if msg is None or not msg.strip():
        raise ValueError("mensaje no puede estar vacío")
    if len(msg) > MAX_LEN_MENSAJE:
        raise ValueError(
            f"mensaje supera {MAX_LEN_MENSAJE} caracteres"
        )


def _short_num(num: str) -> str:
    """Trunca al estilo audit (prefijo+sufijo). Nunca logea completo."""
    if not num:
        return "***"
    s = num.strip()
    if len(s) <= 6:
        return "***"
    return f"{s[:2]}****{s[-4:]}"


def _generar_mensaje_id(accion_id: int) -> str:
    """ID local que sirve como huella de idempotencia · NO es un id
    devuelto por el proveedor (Whapi no devuelve uno de forma
    consistente)."""
    return f"acc{accion_id}-{int(datetime.utcnow().timestamp())}"


def _parse_json(s: str | None) -> dict[str, Any] | None:
    if not s:
        return None
    try:
        v = json.loads(s)
        return v if isinstance(v, dict) else None
    except Exception:
        return None


def _obtener_proveedor():
    """Wrapper que permite a los tests monkeypatchear sin tocar
    obtener_proveedor() globalmente."""
    from agent.providers import obtener_proveedor
    return obtener_proveedor()


async def _leer_accion_fresca(accion_id: int) -> dict[str, Any] | None:
    from agent.memory import async_session
    from agent.automation.models import AccionAutomatizacion
    from agent.automation.action_center import _a_dict
    from sqlalchemy import select
    async with async_session() as s:
        row = (await s.execute(
            select(AccionAutomatizacion).where(
                AccionAutomatizacion.id == accion_id
            )
        )).scalar_one_or_none()
    return _a_dict(row) if row else None


async def _leer_result_actual(
    accion_id: int,
) -> dict[str, Any] | None:
    """Lee result_json fresco · None si la fila o el campo están vacíos."""
    from agent.memory import async_session
    from agent.automation.models import AccionAutomatizacion
    from sqlalchemy import select
    async with async_session() as s:
        row = (await s.execute(
            select(AccionAutomatizacion).where(
                AccionAutomatizacion.id == accion_id
            )
        )).scalar_one_or_none()
        if row is None or not row.result_json:
            return None
    return _parse_json(row.result_json)


async def _persistir_result_inline(
    accion_id: int, resultado: dict[str, Any],
) -> None:
    """UPDATE result_json sin cambiar estado · invariante anti doble
    envío."""
    from agent.memory import async_session
    from agent.automation.models import AccionAutomatizacion
    from sqlalchemy import select
    async with async_session() as s:
        row = (await s.execute(
            select(AccionAutomatizacion).where(
                AccionAutomatizacion.id == accion_id
            )
        )).scalar_one_or_none()
        if row is None:
            return
        row.result_json = json.dumps(resultado, ensure_ascii=False)
        row.updated_at = datetime.utcnow()
        await s.commit()
