# agent/automation/executors/send_message.py — T2.2 · primer HIGH

"""
Ejecutor HIGH para enviar mensajes de WhatsApp via el proveedor
configurado. Sigue el patrón preparar → aprobar → confirmar/ejecutar:

  1. preparar_enviar_mensaje_whatsapp(...)
       → crea la acción HIGH en estado 'needs_approval' con el
         destinatario y el cuerpo guardados en payload. NUNCA envía.
  2. aprobar_accion(accion_id)
       → el usuario aprueba explícitamente la acción.
  3. preview_confirmacion_high_whatsapp(accion_id, telefono_actor)
       + confirmar_high_whatsapp_dedicado(accion_id, "ENVIAR", telefono_actor)
       → ÚNICO camino de materialización: exige acción 'approved', dueño
         autenticado y confirmación literal. (El atajo histórico
         confirmar_enviar_mensaje_whatsapp, que auto-aprobaba sin verificar
         dueño, fue eliminado — ítem 5.1 del roadmap, C4 del audit.)

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
    opportunity_id: str = "",
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
        opportunity_id: identificador de la oportunidad/misión que origina
            la acción. Entra en la idempotency_key (telefono|tipo|playbook|
            opportunity|fecha): pasar uno ÚNICO (ej. "mision-7") evita que
            dos preparaciones distintas del mismo owner el mismo día
            colisionen en la misma acción. Default "" preserva el
            comportamiento previo (un solo enviar_mensaje_whatsapp/owner/día).

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
        opportunity_id=opportunity_id,
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

    # ── Política de terceros (2.5) · límites + consentimiento ───────────
    # El preview evalúa la política ANTES de mostrar nada accionable: si
    # los límites bloquean, el owner lo ve aquí (y confirmar rechazaría
    # igual). Fail-closed: error evaluando → no hay preview accionable.
    from agent.automation.consent_terceros import (
        TEXTO_CONSENTIMIENTO_OWNER,
        componer_mensaje_primer_contacto,
        evaluar_politica_envio_tercero,
        obtener_nombre_owner,
    )

    try:
        politica = await evaluar_politica_envio_tercero(telefono_owner, numero_destino)
    except Exception as e:
        logger.critical(
            f"[CONSENT-2.5] FAIL-CLOSED: error evaluando política en preview "
            f"accion_id={accion_id} ({type(e).__name__}: {e})"
        )
        return {"ok": False, "error": "politica_terceros_error", "accion_id": accion_id}

    if not politica["permitido"]:
        await _audit(
            evento="high_send_blocked_policy",
            telefono=telefono_owner,
            accion_id=accion_id,
            riesgo=riesgo_owner,
            payload={"fase": "preview", "motivo": politica["motivo"]},
        )
        return {"ok": False, "error": politica["motivo"], "accion_id": accion_id}

    # El preview muestra el mensaje FINAL que saldría: con identificación
    # y opt-out PARAR si es el primer contacto con este destino.
    mensaje_final = mensaje
    if politica["es_primer_contacto"]:
        nombre_owner = await obtener_nombre_owner(telefono_owner)
        mensaje_final = componer_mensaje_primer_contacto(nombre_owner, mensaje)

    await _audit(
        evento="high_preview_rendered",
        telefono=telefono_owner,
        accion_id=accion_id,
        riesgo=riesgo_owner,
        payload={
            "tipo_accion": tipo_accion,
            "destino_short": _short_num(numero_destino),
            "longitud_mensaje": len(mensaje_final),
            "costo_creditos_estimado": int(
                accion.get("costo_creditos_estimado", 0) or 0
            ),
            "es_primer_contacto": politica["es_primer_contacto"],
            "requiere_consentimiento": politica["requiere_consentimiento"],
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
        "mensaje_preview": mensaje_final,
        "longitud_mensaje": len(mensaje_final),
        "confirmacion_requerida": "ENVIAR",
        # 2.5 · el ENVIAR tras ver este texto ES el consentimiento afirmativo
        "es_primer_contacto": politica["es_primer_contacto"],
        "requiere_consentimiento": politica["requiere_consentimiento"],
        "texto_consentimiento": (
            TEXTO_CONSENTIMIENTO_OWNER if politica["requiere_consentimiento"] else ""
        ),
    }


async def confirmar_high_whatsapp_dedicado(
    accion_id: int,
    confirmacion: str,
    telefono_actor: str,
) -> dict[str, Any]:
    """Materializa una acción HIGH ya aprobada desde UX dedicada.

    Este camino NO auto-aprueba (el atajo histórico que sí lo hacía fue
    eliminado). Exige estado exactamente 'approved' y confirmación
    exactamente 'ENVIAR' sin normalizar/strip, para que ' ENVIAR ' o
    variantes no pasen por accidente.

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
    numero_destino_payload = str(payload_accion.get("numero_destino") or "")
    destino_short_seguro = _short_num(numero_destino_payload)

    # ── Política de terceros (2.5) · evaluar límites y REGISTRAR el
    # consentimiento afirmativo. El ENVIAR que acaba de validar este flujo
    # llegó tras un preview que mostró el texto de permiso — ese acto es el
    # consentimiento del owner y queda registrado ANTES de ejecutar.
    # Fail-closed: si la política no se puede evaluar/registrar, NO se envía.
    from agent.automation.consent_terceros import (
        TEXTO_CONSENTIMIENTO_OWNER,
        evaluar_politica_envio_tercero,
        registrar_consentimiento,
    )

    try:
        politica = await evaluar_politica_envio_tercero(
            telefono_owner, numero_destino_payload
        )
        if politica["permitido"] and politica["requiere_consentimiento"]:
            await registrar_consentimiento(
                telefono_owner,
                numero_destino_payload,
                accion_id,
                TEXTO_CONSENTIMIENTO_OWNER,
            )
            await _audit(
                evento="high_consent_registered",
                telefono=telefono_owner,
                accion_id=accion_id,
                riesgo=riesgo_owner,
                payload={
                    "destino_short": destino_short_seguro,
                    "es_primer_contacto": politica["es_primer_contacto"],
                    "scope": "este_mensaje",
                },
            )
    except Exception as e:
        logger.critical(
            f"[CONSENT-2.5] FAIL-CLOSED: error evaluando/registrando política "
            f"en confirmación accion_id={accion_id} ({type(e).__name__}: {e}) "
            f"— confirmación BLOQUEADA"
        )
        await _audit(
            evento="high_send_blocked_policy",
            telefono=telefono_owner,
            accion_id=accion_id,
            riesgo=riesgo_owner,
            payload={"fase": "confirmar", "motivo": "politica_error"},
        )
        return {
            "estado_final": "failed",
            "error": "politica_terceros_error",
            "accion_id": accion_id,
        }

    if not politica["permitido"]:
        await _audit(
            evento="high_send_blocked_policy",
            telefono=telefono_owner,
            accion_id=accion_id,
            riesgo=riesgo_owner,
            payload={"fase": "confirmar", "motivo": politica["motivo"]},
        )
        return {
            "estado_final": "failed",
            "error": politica["motivo"],
            "accion_id": accion_id,
        }

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

    # ── Política de terceros (2.5) · DEFENSA EN PROFUNDIDAD ─────────────
    # El camino dedicado (confirmar_high_whatsapp_dedicado) ya evaluó la
    # política y registró el consentimiento. Este check garantiza el
    # invariante aunque un caller futuro llegue al ejecutor por otro
    # camino: destino frío sin consentimiento FRESCO → no se envía.
    # Fail-closed: error evaluando → RuntimeError (libera la reserva).
    telefono_owner_accion = str(accion.get("telefono") or "")
    from agent.automation.consent_terceros import (
        componer_mensaje_primer_contacto,
        evaluar_politica_envio_tercero,
        obtener_nombre_owner,
        registrar_envio_tercero,
        tiene_consentimiento_fresco,
    )

    try:
        politica = await evaluar_politica_envio_tercero(
            telefono_owner_accion, numero_destino
        )
        consentido = (not politica["requiere_consentimiento"]) or (
            await tiene_consentimiento_fresco(
                telefono_owner_accion, numero_destino, accion_id
            )
        )
    except RuntimeError:
        raise
    except Exception as e:
        logger.critical(
            f"[CONSENT-2.5] FAIL-CLOSED: error evaluando política en ejecutor "
            f"accion_id={accion_id} ({type(e).__name__}: {e}) — envío BLOQUEADO"
        )
        raise RuntimeError("politica_terceros_error") from e

    if not politica["permitido"]:
        raise RuntimeError(f"politica_terceros_bloqueada:{politica['motivo']}")
    if not consentido:
        logger.critical(
            f"[CONSENT-2.5] Envío HIGH a destino frío SIN consentimiento "
            f"registrado accion_id={accion_id} "
            f"destino_short={_short_num(numero_destino)} — BLOQUEADO"
        )
        raise RuntimeError("consent_no_registrado")

    # Primer contacto: el mensaje sale con identificación + opt-out PARAR.
    mensaje_envio = mensaje
    if politica["es_primer_contacto"]:
        nombre_owner = await obtener_nombre_owner(telefono_owner_accion)
        mensaje_envio = componer_mensaje_primer_contacto(nombre_owner, mensaje)

    # ── Envío real via proveedor
    proveedor = _obtener_proveedor()
    nombre_proveedor = proveedor.__class__.__name__

    ok = False
    try:
        # AUTOMATICO con es_tercero=True (TCPA-04): el gate evalúa el
        # opt-out del TERCERO destinatario (si alguna vez envió STOP a Dona,
        # no se le escribe), fail-closed, Y quiet hours sobre SU hora local
        # (o, si no se conoce, la del owner como aproximación conservadora).
        # El owner controla cuándo aprueba la acción HIGH — pero el tercero
        # nunca eligió esa hora: sin este flag, un approve a las 2am
        # despertaría a alguien que no controla el timing. Sin límite
        # diario: ese volumen ya lo gobiernan los límites de
        # consent_terceros.py.
        from agent.envio_gate import contexto_envio_automatico
        with contexto_envio_automatico(
            es_tercero=True, telefono_owner=telefono_owner_accion,
        ):
            ok = await proveedor.enviar_mensaje(numero_destino, mensaje_envio)
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
        "longitud_mensaje": len(mensaje_envio),
        "modo": "provider",
        "provider": nombre_proveedor,
        "enviado_en": datetime.utcnow().isoformat(),
        "primer_contacto": politica["es_primer_contacto"],
    }

    # ── Persistir result_json INMEDIATAMENTE para dedupe en retries
    # (antes de que ejecutar_accion llame marcar_completada · si crash,
    # cualquier retry verá estado_envio=sent y no re-enviará)
    await _persistir_result_inline(accion_id, resultado)

    # ── Log de envíos a terceros (2.5) · base de los límites de la
    # política. Best-effort POST-envío: el mensaje ya salió — fallar acá
    # marcaría la acción failed y liberaría la reserva de un trabajo ya
    # entregado (patrón C5). Un hiccup deja el límite sub-contado y queda
    # en ERROR para observabilidad.
    try:
        await registrar_envio_tercero(
            telefono_owner_accion, numero_destino, accion_id
        )
    except Exception as e:
        logger.error(
            f"[CONSENT-2.5] No se pudo registrar el envío a tercero "
            f"accion_id={accion_id} ({type(e).__name__}: {e}) — límites "
            f"quedarán sub-contados para este envío"
        )

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
        # 2.5 · política de terceros
        "consent_no_registrado": "consent_missing",
        "politica_terceros_bloqueada": "third_party_policy_blocked",
        "politica_terceros_error": "third_party_policy_error",
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
    from sqlalchemy import select

    from agent.automation.action_center import _a_dict
    from agent.automation.models import AccionAutomatizacion
    from agent.memory import async_session
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
    from sqlalchemy import select

    from agent.automation.action_center import _a_dict
    from agent.automation.models import AccionAutomatizacion
    from agent.memory import async_session

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
    from sqlalchemy import select

    from agent.automation.models import AccionAutomatizacion
    from agent.memory import async_session
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
    from sqlalchemy import select

    from agent.automation.models import AccionAutomatizacion
    from agent.memory import async_session
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
