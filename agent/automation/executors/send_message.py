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
    telefono_actor: str,
) -> dict[str, Any]:
    """Preview dedicado para una acción HIGH de envío WhatsApp.

    No ejecuta, no aprueba, no toca proveedores externos. Sólo devuelve
    datos necesarios para que el dueño vea destino, mensaje, costo y riesgo
    antes de escribir la confirmación literal.

    Cada llamada deja huella en audit log (`high_preview_requested` siempre;
    `high_preview_rendered` cuando el preview es servible). El payload
    auditado nunca contiene número ni cuerpo crudos.
    """
    from agent.automation.audit import registrar_evento as _audit

    accion = await _leer_accion_fresca_para_actor(accion_id, telefono_actor)
    if accion is None:
        return {"ok": False, "error": "accion_no_existe", "accion_id": accion_id}
    telefono_owner = accion.get("telefono", "") or ""
    riesgo_owner = accion.get("riesgo", "") or ""
    tipo_accion = accion.get("tipo_accion", "")
    estado_actual = accion.get("estado", "")

    await _audit(
        evento="high_preview_requested",
        telefono=telefono_owner,
        accion_id=accion_id,
        riesgo=riesgo_owner,
        payload={
            "tipo_accion": tipo_accion,
            "estado_actual": estado_actual,
        },
    )

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

    await _audit(
        evento="high_preview_rendered",
        telefono=telefono_owner,
        accion_id=accion_id,
        riesgo=riesgo_owner,
        payload={
            "tipo_accion": tipo_accion,
            "destino_short": _short_num(numero_destino),
            "longitud_mensaje": len(mensaje),
            "costo_creditos_estimado": int(
                accion.get("costo_creditos_estimado", 0) or 0
            ),
        },
    )

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
    telefono_actor: str,
) -> dict[str, Any]:
    """Materializa una acción HIGH ya aprobada desde UX dedicada.

    A diferencia del atajo histórico confirmar_enviar_mensaje_whatsapp(),
    este camino NO auto-aprueba. Exige estado exactamente 'approved' y
    confirmación exactamente 'ENVIAR' sin normalizar/strip, para que
    ' ENVIAR ' o variantes no pasen por accidente.

    Cada paso deja huella en audit log:
      * `high_confirmation_submitted` cuando el actor autenticado es dueño
        de la acción y el endpoint recibe una confirmación.
      * `high_confirmation_rejected` si el string es inválido o el estado
        bloquea por causa no-duplicada. Los intentos contra acciones ajenas
        se responden como no existentes y no auditan metadata del owner.
      * `high_execution_duplicate_blocked` cuando un segundo intento llega
        sobre una acción ya completada/en curso/fallida, o cuando pierde el
        claim atómico contra otro caller concurrente.
      * `high_execution_claimed` antes de soltar el control al ejecutor.
      * `high_execution_succeeded` / `high_execution_failed` con metadata
        sanitizada del resultado (nunca destino/cuerpo crudos).
    """
    from agent.automation.audit import registrar_evento as _audit

    # Sólo tipo del input para auditoría (str/no-str); el contenido literal
    # nunca se guarda — un string distinto a 'ENVIAR' puede contener PII.
    confirmacion_es_str = isinstance(confirmacion, str)
    confirmacion_valida = confirmacion_es_str and confirmacion == "ENVIAR"

    accion = await _leer_accion_fresca_para_actor(accion_id, telefono_actor)
    if accion is None:
        return {
            "estado_final": "failed",
            "error": "accion_no_existe",
            "accion_id": accion_id,
        }

    telefono_owner = accion.get("telefono", "") or ""
    riesgo_owner = accion.get("riesgo", "") or ""
    tipo_accion = accion.get("tipo_accion", "")
    estado_actual = accion.get("estado", "")

    await _audit(
        evento="high_confirmation_submitted",
        telefono=telefono_owner,
        accion_id=accion_id,
        riesgo=riesgo_owner,
        payload={
            "tipo_accion": tipo_accion,
            "estado_actual": estado_actual,
            "confirmacion_es_str": confirmacion_es_str,
            "confirmacion_valida": confirmacion_valida,
        },
    )

    if not confirmacion_valida:
        await _audit(
            evento="high_confirmation_rejected",
            telefono=telefono_owner,
            accion_id=accion_id,
            riesgo=riesgo_owner,
            payload={
                "razon": "confirmacion_invalida",
                "confirmacion_es_str": confirmacion_es_str,
            },
        )
        return {
            "estado_final": "failed",
            "error": "confirmacion_invalida",
            "accion_id": accion_id,
        }

    if accion.get("tipo_accion") != "enviar_mensaje_whatsapp":
        await _audit(
            evento="high_confirmation_rejected",
            telefono=telefono_owner,
            accion_id=accion_id,
            riesgo=riesgo_owner,
            payload={
                "razon": "tipo_accion_no_soportado",
                "tipo_accion": tipo_accion,
            },
        )
        return {
            "estado_final": "failed",
            "error": "tipo_accion_no_soportado",
            "accion_id": accion_id,
        }
    if accion.get("riesgo") != "high":
        await _audit(
            evento="high_confirmation_rejected",
            telefono=telefono_owner,
            accion_id=accion_id,
            riesgo=riesgo_owner,
            payload={"razon": "riesgo_no_high"},
        )
        return {
            "estado_final": "failed",
            "error": "riesgo_no_high",
            "accion_id": accion_id,
        }
    if accion.get("estado") != "approved":
        estado_actual = accion.get("estado", "")
        # Estados terminales/intermedios típicos de un segundo intento sobre
        # una acción ya en curso o ya enviada. Los marcamos como duplicate
        # para distinguirlos de rechazos genuinos del usuario/sistema.
        if estado_actual in {"completed", "running", "failed"}:
            await _audit(
                evento="high_execution_duplicate_blocked",
                telefono=telefono_owner,
                accion_id=accion_id,
                riesgo=riesgo_owner,
                payload={
                    "razon": "estado_no_aprobado_post_intento",
                    "estado": estado_actual,
                },
            )
        else:
            await _audit(
                evento="high_confirmation_rejected",
                telefono=telefono_owner,
                accion_id=accion_id,
                riesgo=riesgo_owner,
                payload={
                    "razon": "accion_no_aprobada",
                    "estado": estado_actual,
                },
            )
        return {
            "estado_final": "failed",
            "error": "accion_no_aprobada",
            "estado": estado_actual,
            "accion_id": accion_id,
        }

    payload_accion = _parse_json(accion.get("payload_json")) or {}
    destino_short_seguro = _short_num(str(payload_accion.get("numero_destino") or ""))

    from agent.automation.execution import ejecutar_accion
    resultado = await ejecutar_accion(accion, audit_high_dedicado=True)
    estado_final = resultado.get("estado_final", "")
    error_resultado = str(resultado.get("error") or "")
    result_payload = resultado.get("result") or {}
    idempotente = bool(
        isinstance(result_payload, dict) and result_payload.get("idempotent")
    )

    if estado_final == "completed":
        await _audit(
            evento="high_execution_succeeded",
            telefono=telefono_owner,
            accion_id=accion_id,
            riesgo=riesgo_owner,
            payload={
                "tipo_accion": tipo_accion,
                "modo": str(result_payload.get("modo", ""))[:32]
                    if isinstance(result_payload, dict) else "",
                "provider": str(result_payload.get("provider", ""))[:64]
                    if isinstance(result_payload, dict) else "",
                "destino_short": destino_short_seguro,
                "longitud_mensaje": int(result_payload.get("longitud_mensaje", 0) or 0)
                    if isinstance(result_payload, dict) else 0,
                "idempotent": idempotente,
            },
        )
    elif (
        "ya_en_ejecucion" in error_resultado
        or "claim_lost" in error_resultado
        or "running_claim_lost" in error_resultado
    ):
        await _audit(
            evento="high_execution_duplicate_blocked",
            telefono=telefono_owner,
            accion_id=accion_id,
            riesgo=riesgo_owner,
            payload={"razon": "claim_lost"},
        )
    else:
        await _audit(
            evento="high_execution_failed",
            telefono=telefono_owner,
            accion_id=accion_id,
            riesgo=riesgo_owner,
            payload={
                "tipo_accion": tipo_accion,
                # Código cerrado; nunca texto crudo de provider/exception.
                "error_tipo": _audit_error_code(error_resultado),
            },
        )

    return resultado


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
        # AUTOMATICO: el gate evalúa el opt-out del TERCERO destinatario
        # (si alguna vez envió STOP a Dona, no se le escribe), fail-closed.
        # Sin quiet hours/límite diario: la acción fue confirmada por el
        # usuario con confirmación dedicada HIGH.
        from agent.envio_gate import contexto_envio_automatico
        with contexto_envio_automatico():
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


def _audit_error_code(error: str) -> str:
    """Clasifica errores para audit log sin persistir texto upstream.

    El texto de error puede contener PII/secrets si proviene de proveedores o
    excepciones. Por eso se transforma a códigos cerrados y seguros.
    """
    error = str(error or "")
    codigos = {
        "insufficient_credits": "insufficient_credits",
        "critical_blocked_t21a": "critical_blocked_t21a",
        "accion_ya_en_ejecucion_o_no_aprobada": "claim_lost",
        "ejecutor_no_disponible": "executor_unavailable",
    }
    for needle, code in codigos.items():
        if needle in error:
            return code
    if "RuntimeError" in error or "error interno durante ejecución" in error:
        return "executor_exception"
    return "execution_failed"


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


async def _leer_accion_fresca_para_actor(
    accion_id: int,
    telefono_actor: str,
) -> dict[str, Any] | None:
    """Lee una acción sólo si pertenece al actor autenticado.

    La condición de ownership vive en el SELECT (`id` + `telefono`) para no
    hidratar payloads HIGH ajenos antes de la barrera de pertenencia.
    """
    from agent.memory import async_session
    from agent.automation.models import AccionAutomatizacion
    from agent.automation.action_center import _a_dict
    from sqlalchemy import select

    async with async_session() as s:
        row = (await s.execute(
            select(AccionAutomatizacion).where(
                AccionAutomatizacion.id == accion_id,
                AccionAutomatizacion.telefono == telefono_actor,
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
