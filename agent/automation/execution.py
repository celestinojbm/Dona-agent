# agent/automation/execution.py — Execution System (T2.1.A → T2.1.C)

"""
Interfaz de ejecutores para acciones del Automation Core.

T2.1.A entregó esqueletos placeholder ("dry-run").
T2.1.C conecta LLM REAL para LOW y MEDIUM internas:

  LOW (auto-ejecutables):
    generar_plan_semanal           → markdown con 5-7 acciones
    generar_calendario_contenido   → JSON 7 ideas de publicación
    generar_checklist_ventas       → markdown checklist 8-12 items
    analizar_diagnostico           → JSON síntesis del perfil
    generar_idea_oferta            → JSON 3 alternativas

  MEDIUM (requieren aprobación · NO envían):
    preparar_mensaje_whatsapp      → texto borrador
    preparar_campana_whatsapp      → JSON 3 mensajes
    preparar_publicacion_redes     → JSON post
    preparar_email_seguimiento     → JSON asunto+cuerpo
    borrador_copy_oferta           → JSON copy A/B

Reglas estrictas que SIGUEN VIGENTES (T2.1.A respetado):
  1. Si estado == 'pending' y riesgo == LOW: ejecuta auto.
  2. Si estado == 'approved': ejecuta.
  3. Si estado != esos dos: marca failed con error claro.
  4. CRITICAL siempre bloqueado (audit action_blocked_critical).
  5. HIGH (enviar_*, contactar_lead, publicar_*) NO tienen ejecutor
     en T2.1.C · siguen siendo "ejecutor no disponible · futuro PR".
     Esto preserva el guardrail: el LLM solo prepara borradores ·
     ningún envío real ocurre desde el Automation Core.

Sanitización (T2.1.C):
  - El contexto del perfil pasa por construir_contexto_perfil() que cap
    cada campo a 400 chars y omite vacíos.
  - El output del LLM se valida y se trunca por límites de cada formato.
  - Si el LLM falla, se usa un fallback determinístico mejorado (más
    útil que los esqueletos T2.1.A pero no inventa datos).
  - Audit log registra la ejecución con modo (llm|fallback) · sin loguear
    el output crudo (puede tener PII inferida).
"""

from __future__ import annotations

import json
import logging
from typing import Any, Awaitable, Callable

from agent.automation.permissions import (
    NivelRiesgo,
    esta_bloqueado_t21,
)
from agent.automation.audit import registrar_evento
from agent.automation.action_center import (
    marcar_running,
    marcar_completada,
    marcar_fallida,
)
from agent.automation.credits import (
    reservar as reservar_creditos,
    confirmar as confirmar_creditos,
    liberar as liberar_creditos,
    CreditosInsuficientesError,
)
from agent.automation.prompts import (
    construir_contexto_perfil,
    SYSTEM_PROMPT_PLAN_SEMANAL,
    SYSTEM_PROMPT_CALENDARIO_CONTENIDO,
    SYSTEM_PROMPT_CHECKLIST_VENTAS,
    SYSTEM_PROMPT_ANALIZAR_DIAGNOSTICO,
    SYSTEM_PROMPT_IDEA_OFERTA,
    SYSTEM_PROMPT_PREPARAR_MENSAJE_WHATSAPP,
    SYSTEM_PROMPT_PREPARAR_CAMPANA_WHATSAPP,
    SYSTEM_PROMPT_PREPARAR_PUBLICACION_REDES,
    SYSTEM_PROMPT_PREPARAR_EMAIL_SEGUIMIENTO,
    SYSTEM_PROMPT_BORRADOR_COPY_OFERTA,
)

logger = logging.getLogger("dona")


# ── Helpers LLM ─────────────────────────────────────────────────────────────


async def _llm_completar(
    system: str, mensaje: str, max_tokens: int = 800,
) -> tuple[str | None, str]:
    """Llama al LLM. Retorna (texto, provider).

    provider es 'llm' si la llamada sucedió y devolvió contenido, o
    'fallback' si no hay LLM disponible o todos los proveedores
    fallaron. El módulo agent.llm ya maneja el fallback DeepSeek →
    Haiku internamente.
    """
    try:
        from agent.llm import completar_con_sistema
        texto = await completar_con_sistema(system, mensaje, max_tokens=max_tokens)
        if texto:
            return texto, "llm"
    except Exception as e:
        logger.warning(
            f"[EXEC] LLM falló · fallback determinístico: "
            f"{type(e).__name__}"
        )
    return None, "fallback"


def _parsear_json_seguro(texto: str | None) -> Any:
    """Parsea texto LLM como JSON · tolerante a fences ```json y prosa
    alrededor. Retorna None si no es JSON válido."""
    if not texto:
        return None
    s = texto.strip()
    # Quitar fences de markdown
    if s.startswith("```"):
        # remover primera línea (e.g. "```json")
        partes = s.split("\n", 1)
        if len(partes) > 1:
            s = partes[1]
        if s.endswith("```"):
            s = s[: -3]
    s = s.strip()
    # Algunos LLMs ponen prosa antes/después · intentar localizar el JSON
    if not (s.startswith("{") or s.startswith("[")):
        # buscar primer '[' o '{'
        for i, ch in enumerate(s):
            if ch in "[{":
                s = s[i:]
                break
        # buscar cierre balanceado al final
        for i in range(len(s) - 1, -1, -1):
            if s[i] in "]}":
                s = s[: i + 1]
                break
    try:
        return json.loads(s)
    except Exception:
        return None


def _trunc(s: str | None, max_chars: int) -> str:
    """Trunca a max_chars · cero side-effects."""
    if not s:
        return ""
    s = str(s)
    return s[:max_chars]


# ── Ejecutores reales · LOW ────────────────────────────────────────────────


async def _ejecutor_plan_semanal(
    accion: dict, perfil: dict | None,
) -> dict[str, Any]:
    """Genera plan semanal en markdown · usa LLM con fallback determinístico."""
    contexto = construir_contexto_perfil(perfil)
    user_msg = (
        f"{contexto}\n\n"
        f"Genera un plan semanal alineado a los datos anteriores. "
        f"Markdown · 5-7 acciones · una por día (Lun-Vie + opcional Sáb)."
    )
    texto, provider = await _llm_completar(
        SYSTEM_PROMPT_PLAN_SEMANAL, user_msg, max_tokens=900,
    )
    if texto:
        return {
            "output_md": _trunc(texto, 4000),
            "modo": "llm",
            "provider": provider,
        }
    # Fallback · esqueleto determinístico mejorado
    nombre = (perfil or {}).get("nombre_negocio") or "tu negocio"
    objetivo = (perfil or {}).get("objetivo_mes") or "(sin objetivo definido)"
    canales = (perfil or {}).get("canales_actuales") or "tus canales actuales"
    plan = (
        f"# Plan semanal · {nombre}\n\n"
        f"**Objetivo del mes:** {objetivo}\n\n"
        f"## Lunes\n- Revisa las últimas 5 conversaciones sin respuesta y "
        f"prioriza las de mayor potencial.\n\n"
        f"## Martes\n- Crea o actualiza una pieza de contenido para "
        f"{canales}.\n\n"
        f"## Miércoles\n- Haz seguimiento a 3 clientes o leads del mes "
        f"pasado.\n\n"
        f"## Jueves\n- Confirma pedidos o agendas pendientes y cierra "
        f"al menos uno.\n\n"
        f"## Viernes\n- Revisa el avance hacia tu objetivo del mes y "
        f"ajusta la siguiente semana.\n\n"
        f"Próximo paso recomendado: actuar sobre el bloqueo principal "
        f"que reportaste en el diagnóstico."
    )
    return {"output_md": plan, "modo": "fallback", "provider": "fallback"}


async def _ejecutor_calendario_contenido(
    accion: dict, perfil: dict | None,
) -> dict[str, Any]:
    contexto = construir_contexto_perfil(perfil)
    user_msg = (
        f"{contexto}\n\n"
        f"Genera el calendario JSON · 7 días · variado · alineado a "
        f"cliente_ideal y oferta_principal."
    )
    texto, provider = await _llm_completar(
        SYSTEM_PROMPT_CALENDARIO_CONTENIDO, user_msg, max_tokens=1200,
    )
    parsed = _parsear_json_seguro(texto)
    if isinstance(parsed, list) and parsed:
        # Validar shape mínimo y truncar
        items: list[dict[str, Any]] = []
        for i, raw in enumerate(parsed[:7]):
            if not isinstance(raw, dict):
                continue
            items.append({
                "dia": int(raw.get("dia", i + 1)) if str(raw.get("dia", "")).isdigit() else i + 1,
                "titulo": _trunc(raw.get("titulo", ""), 100),
                "copy_corto": _trunc(raw.get("copy_corto", ""), 280),
                "formato": _trunc(raw.get("formato", "post"), 30),
                "canal_sugerido": _trunc(raw.get("canal_sugerido", "whatsapp"), 30),
            })
        if items:
            return {"calendario": items, "modo": "llm", "provider": provider}
    # Fallback determinístico
    canal_default = ((perfil or {}).get("canales_actuales") or "WhatsApp").split(",")[0].strip()
    items = [
        {
            "dia": i + 1,
            "titulo": f"Idea día {i + 1}",
            "copy_corto": (
                "Comparte algo útil sobre tu oferta principal · "
                "responde una duda frecuente · sin clickbait."
            ),
            "formato": ["post", "story", "reel", "carrusel", "post", "story", "reel"][i],
            "canal_sugerido": canal_default or "whatsapp",
        }
        for i in range(7)
    ]
    return {"calendario": items, "modo": "fallback", "provider": "fallback"}


async def _ejecutor_checklist_ventas(
    accion: dict, perfil: dict | None,
) -> dict[str, Any]:
    contexto = construir_contexto_perfil(perfil)
    user_msg = (
        f"{contexto}\n\n"
        f"Genera la checklist comercial · 8-12 ítems · imperativo · "
        f"ejecutables esta semana."
    )
    texto, provider = await _llm_completar(
        SYSTEM_PROMPT_CHECKLIST_VENTAS, user_msg, max_tokens=700,
    )
    if texto:
        # Parsear líneas que empiezan con "- [ ]" o "- "
        lineas = [
            ln.strip() for ln in texto.splitlines()
            if ln.strip().startswith(("- [ ]", "- ", "* "))
        ]
        items = [
            ln.lstrip("- ").lstrip("[] ").strip()
            for ln in lineas if len(ln) > 3
        ][:12]
        if items:
            return {
                "checklist": [_trunc(it, 200) for it in items],
                "modo": "llm",
                "provider": provider,
            }
    # Fallback
    items = [
        "Revisa los últimos 5 leads sin respuesta y reactiva los "
        "más calientes.",
        "Confirma pedidos pendientes del día y comunica fechas "
        "claras al cliente.",
        "Cobra facturas vencidas con un mensaje cálido pero firme.",
        "Sube 1 publicación corta sobre tu oferta principal.",
        "Haz 3 seguimientos a clientes recurrentes que no han "
        "comprado este mes.",
        "Actualiza precios en tu lista interna si cambiaron costos.",
        "Agenda 2 conversaciones de cierre esta semana.",
        "Pide 1 testimonio nuevo a un cliente reciente.",
    ]
    return {"checklist": items, "modo": "fallback", "provider": "fallback"}


async def _ejecutor_analizar_diagnostico(
    accion: dict, perfil: dict | None,
) -> dict[str, Any]:
    p = perfil or {}
    llenos = sum(1 for k in (
        "oferta_principal", "cliente_ideal", "objetivo_mes",
        "canales_actuales", "bloqueo_actual", "tareas_delegar",
    ) if (p.get(k) or "").strip())
    completitud_pct = int(llenos / 6 * 100)
    contexto = construir_contexto_perfil(perfil)
    user_msg = f"{contexto}\n\nAnaliza y devuelve el JSON definido."
    texto, provider = await _llm_completar(
        SYSTEM_PROMPT_ANALIZAR_DIAGNOSTICO, user_msg, max_tokens=600,
    )
    parsed = _parsear_json_seguro(texto)
    if isinstance(parsed, dict):
        return {
            "completitud_pct": int(parsed.get("completitud_pct", completitud_pct)),
            "fortalezas": [
                _trunc(s, 200) for s in (parsed.get("fortalezas") or [])
                if isinstance(s, str)
            ][:3],
            "oportunidades_clave": [
                _trunc(s, 200) for s in (parsed.get("oportunidades_clave") or [])
                if isinstance(s, str)
            ][:3],
            "riesgos": [
                _trunc(s, 200) for s in (parsed.get("riesgos") or [])
                if isinstance(s, str)
            ][:2],
            "recomendacion_inicial": _trunc(
                parsed.get("recomendacion_inicial", ""), 300,
            ),
            "campos_llenos": llenos,
            "campos_totales": 6,
            "modo": "llm",
            "provider": provider,
        }
    return {
        "completitud_pct": completitud_pct,
        "fortalezas": [],
        "oportunidades_clave": [],
        "riesgos": [],
        "recomendacion_inicial": (
            "Completa los campos pendientes de tu diagnóstico para que "
            "Dona pueda recomendarte acciones más específicas."
            if llenos < 6 else
            "Genera tu plan semanal o calendario de contenido como "
            "primer paso concreto."
        ),
        "campos_llenos": llenos,
        "campos_totales": 6,
        "modo": "fallback",
        "provider": "fallback",
    }


async def _ejecutor_generar_idea_oferta(
    accion: dict, perfil: dict | None,
) -> dict[str, Any]:
    contexto = construir_contexto_perfil(perfil)
    user_msg = f"{contexto}\n\nDevuelve el JSON con 3 alternativas."
    texto, provider = await _llm_completar(
        SYSTEM_PROMPT_IDEA_OFERTA, user_msg, max_tokens=700,
    )
    parsed = _parsear_json_seguro(texto)
    if isinstance(parsed, list) and parsed:
        alts = []
        for raw in parsed[:3]:
            if not isinstance(raw, dict):
                continue
            alts.append({
                "titulo": _trunc(raw.get("titulo", ""), 60),
                "descripcion": _trunc(raw.get("descripcion", ""), 300),
                "por_que_funciona": _trunc(raw.get("por_que_funciona", ""), 200),
                "riesgo_asumido": _trunc(raw.get("riesgo_asumido", "low"), 20),
            })
        if alts:
            return {"alternativas": alts, "modo": "llm", "provider": provider}
    return {
        "alternativas": [
            {
                "titulo": "Paquete inicial accesible",
                "descripcion": (
                    "Versión simplificada de tu oferta principal a "
                    "precio de entrada · ideal para que clientes "
                    "nuevos prueben tu trabajo."
                ),
                "por_que_funciona": (
                    "Reduce fricción de primera compra · acerca a "
                    "cliente_ideal con menor riesgo percibido."
                ),
                "riesgo_asumido": "low",
            },
            {
                "titulo": "Servicio recurrente mensual",
                "descripcion": (
                    "Conviértete en proveedor de cabecera con un "
                    "mantenimiento o entrega periódica."
                ),
                "por_que_funciona": "Estabiliza ingresos · genera vínculo.",
                "riesgo_asumido": "medio",
            },
            {
                "titulo": "Bundle premium con asesoría",
                "descripcion": (
                    "Producto/servicio + sesión 1:1 contigo o con "
                    "alguien del equipo · margen mayor."
                ),
                "por_que_funciona": "Diferencia tu oferta · aumenta ticket.",
                "riesgo_asumido": "medio",
            },
        ],
        "modo": "fallback",
        "provider": "fallback",
    }


# ── Ejecutores reales · MEDIUM (preparan, NO envían) ───────────────────────


async def _ejecutor_preparar_mensaje_whatsapp(
    accion: dict, perfil: dict | None,
) -> dict[str, Any]:
    contexto = construir_contexto_perfil(perfil)
    proposito = _trunc(accion.get("descripcion") or "", 300) or "mensaje cálido al cliente"
    user_msg = (
        f"{contexto}\n\n"
        f"Propósito del mensaje: {proposito}\n\n"
        f"Genera el borrador. Recuerda: tú NO envías nada, esto es solo "
        f"un draft que el dueño revisará antes de enviarlo manualmente."
    )
    texto, provider = await _llm_completar(
        SYSTEM_PROMPT_PREPARAR_MENSAJE_WHATSAPP, user_msg, max_tokens=400,
    )
    if texto:
        return {
            "borrador": _trunc(texto, 800),
            "modo": "llm",
            "provider": provider,
            "estado_envio": "pending_user_review",
            "aviso": (
                "Este es un borrador · revisa antes de enviarlo. "
                "Dona NO envía mensajes automáticamente."
            ),
        }
    # Fallback
    nombre = (perfil or {}).get("nombre_negocio") or "tu negocio"
    return {
        "borrador": (
            f"Hola {{NOMBRE}}, soy de {nombre}. "
            "Quería saludarte y preguntarte cómo va todo. "
            "Si necesitas algo de mi parte esta semana, escríbeme · "
            "estoy disponible."
        ),
        "modo": "fallback",
        "provider": "fallback",
        "estado_envio": "pending_user_review",
        "aviso": "Este es un borrador · revisa antes de enviarlo.",
    }


async def _ejecutor_preparar_publicacion_redes(
    accion: dict, perfil: dict | None,
) -> dict[str, Any]:
    contexto = construir_contexto_perfil(perfil)
    user_msg = (
        f"{contexto}\n\n"
        f"Genera la publicación JSON. Recuerda: NO publicas, solo "
        f"preparas borrador para revisión."
    )
    texto, provider = await _llm_completar(
        SYSTEM_PROMPT_PREPARAR_PUBLICACION_REDES, user_msg, max_tokens=500,
    )
    parsed = _parsear_json_seguro(texto)
    if isinstance(parsed, dict):
        return {
            "copy": _trunc(parsed.get("copy", ""), 500),
            "hashtags": [
                _trunc(s, 30) for s in (parsed.get("hashtags") or [])
                if isinstance(s, str)
            ][:7],
            "formato_recomendado": _trunc(
                parsed.get("formato_recomendado", "post"), 30,
            ),
            "call_to_action": _trunc(parsed.get("call_to_action", ""), 80),
            "modo": "llm",
            "provider": provider,
            "estado_publicacion": "pending_user_review",
        }
    # Fallback
    return {
        "copy": (
            "Pequeñas decisiones se acumulan. Esta semana, una pequeña "
            "mejora en tu oferta puede traer resultados grandes."
        ),
        "hashtags": ["pymeenaccion", "negociopropio"],
        "formato_recomendado": "post",
        "call_to_action": "Cuéntame en comentarios qué cambiarías esta semana.",
        "modo": "fallback",
        "provider": "fallback",
        "estado_publicacion": "pending_user_review",
    }


async def _ejecutor_preparar_email_seguimiento(
    accion: dict, perfil: dict | None,
) -> dict[str, Any]:
    contexto = construir_contexto_perfil(perfil)
    user_msg = (
        f"{contexto}\n\n"
        f"Genera asunto + cuerpo del email JSON. Solo borrador · NO se envía."
    )
    texto, provider = await _llm_completar(
        SYSTEM_PROMPT_PREPARAR_EMAIL_SEGUIMIENTO, user_msg, max_tokens=600,
    )
    parsed = _parsear_json_seguro(texto)
    if isinstance(parsed, dict):
        return {
            "asunto": _trunc(parsed.get("asunto", ""), 80),
            "cuerpo": _trunc(parsed.get("cuerpo", ""), 800),
            "modo": "llm",
            "provider": provider,
            "estado_envio": "pending_user_review",
        }
    return {
        "asunto": "Pasando por aquí",
        "cuerpo": (
            "Hola {NOMBRE},\n\n"
            "Te escribo brevemente para saber cómo te va. Si hay algo "
            "puntual en lo que pueda ayudarte esta semana, respóndeme · "
            "intento simplificarte el día.\n\n"
            "Un saludo."
        ),
        "modo": "fallback",
        "provider": "fallback",
        "estado_envio": "pending_user_review",
    }


async def _ejecutor_preparar_campana_whatsapp(
    accion: dict, perfil: dict | None,
) -> dict[str, Any]:
    contexto = construir_contexto_perfil(perfil)
    user_msg = (
        f"{contexto}\n\n"
        f"Genera la campaña JSON · 3 mensajes · NO se envía nada."
    )
    texto, provider = await _llm_completar(
        SYSTEM_PROMPT_PREPARAR_CAMPANA_WHATSAPP, user_msg, max_tokens=900,
    )
    parsed = _parsear_json_seguro(texto)
    if isinstance(parsed, list) and parsed:
        msgs = []
        for raw in parsed[:3]:
            if not isinstance(raw, dict):
                continue
            msgs.append({
                "dia": int(raw.get("dia", 1)) if str(raw.get("dia", "")).isdigit() else 1,
                "titulo": _trunc(raw.get("titulo", ""), 60),
                "mensaje": _trunc(raw.get("mensaje", ""), 500),
            })
        if msgs:
            return {
                "mensajes": msgs,
                "modo": "llm",
                "provider": provider,
                "estado_envio": "pending_user_review",
            }
    return {
        "mensajes": [
            {"dia": 1, "titulo": "Anuncio",
             "mensaje": "Esta semana lanzamos algo que creo te interesa..."},
            {"dia": 3, "titulo": "Recordatorio",
             "mensaje": "Aún quedan cupos · si te interesa, escríbeme."},
            {"dia": 5, "titulo": "Último día",
             "mensaje": "Hoy cierro la lista · si querías entrar, este "
                        "es el momento."},
        ],
        "modo": "fallback",
        "provider": "fallback",
        "estado_envio": "pending_user_review",
    }


async def _ejecutor_borrador_copy_oferta(
    accion: dict, perfil: dict | None,
) -> dict[str, Any]:
    contexto = construir_contexto_perfil(perfil)
    user_msg = f"{contexto}\n\nGenera el copy JSON con titulo + largo + variantes A/B."
    texto, provider = await _llm_completar(
        SYSTEM_PROMPT_BORRADOR_COPY_OFERTA, user_msg, max_tokens=600,
    )
    parsed = _parsear_json_seguro(texto)
    if isinstance(parsed, dict):
        return {
            "titulo_corto": _trunc(parsed.get("titulo_corto", ""), 50),
            "copy_largo": _trunc(parsed.get("copy_largo", ""), 600),
            "variantes": [
                _trunc(v, 200) for v in (parsed.get("variantes") or [])
                if isinstance(v, str)
            ][:2],
            "modo": "llm",
            "provider": provider,
        }
    return {
        "titulo_corto": "Tu siguiente paso, sin rodeos",
        "copy_largo": (
            "Si lo que ofreces ya funciona, el siguiente paso es "
            "comunicarlo con claridad. Una promesa clara, un cliente "
            "ideal en mente y una forma simple de probarlo."
        ),
        "variantes": [
            "Una versión simple para empezar.",
            "Lo mismo, sin fricción.",
        ],
        "modo": "fallback",
        "provider": "fallback",
    }


async def _ejecutor_generar_checklist_ventas(
    accion: dict, perfil: dict | None,
) -> dict[str, Any]:
    return await _ejecutor_checklist_ventas(accion, perfil)


# T2.2 · primer ejecutor HIGH real
from agent.automation.executors.send_message import (
    ejecutor_enviar_mensaje_whatsapp as _ejecutor_enviar_mensaje_whatsapp,
)


# Mapping tipo_accion → ejecutor
EJECUTORES_T21A: dict[str, Callable[..., Awaitable[dict]]] = {
    # LOW
    "generar_plan_semanal": _ejecutor_plan_semanal,
    "generar_calendario_contenido": _ejecutor_calendario_contenido,
    "generar_checklist_ventas": _ejecutor_checklist_ventas,
    "analizar_diagnostico": _ejecutor_analizar_diagnostico,
    "generar_idea_oferta": _ejecutor_generar_idea_oferta,
    # MEDIUM (preparan · NO envían)
    "preparar_mensaje_whatsapp": _ejecutor_preparar_mensaje_whatsapp,
    "preparar_campana_whatsapp": _ejecutor_preparar_campana_whatsapp,
    "preparar_publicacion_redes": _ejecutor_preparar_publicacion_redes,
    "preparar_email_seguimiento": _ejecutor_preparar_email_seguimiento,
    "borrador_copy_oferta": _ejecutor_borrador_copy_oferta,
    # HIGH · T2.2 · enviar mensaje real con guardrails de aprobación,
    # idempotencia anti doble envío y reserva/liberación de créditos.
    "enviar_mensaje_whatsapp": _ejecutor_enviar_mensaje_whatsapp,
    # Los demás HIGH (enviar_campana_masiva, publicar_red_social,
    # contactar_lead) siguen sin ejecutor · ejecutar_accion los rechaza
    # liberando la reserva.
}


# ── API pública ─────────────────────────────────────────────────────────────


async def ejecutar_accion(accion: dict[str, Any]) -> dict[str, Any]:
    """Ejecuta una acción del Action Center.

    Reglas (T2.1.A respetadas en T2.1.C/D):
      - Si estado == 'pending' y riesgo == LOW: ejecuta (auto).
      - Si estado == 'approved': ejecuta.
      - Si estado != esos dos: rechaza con error_message claro.
      - Si riesgo == CRITICAL: bloquea SIEMPRE (audit
        action_blocked_critical · reserva liberada si hubo).
      - Si tipo_accion no tiene ejecutor mapeado (HIGH típicamente):
        falla con mensaje · reserva liberada.

    T2.1.D · reservas de créditos:
      1. Reserva créditos antes de ejecutar (idempotente · no doble cobra).
      2. Si saldo insuficiente → marca acción failed · audit
         action_blocked_insufficient_credits · NO ejecuta.
      3. Tras ejecución exitosa → confirma reserva (descuento queda).
      4. Tras ejecución fallida → libera reserva (acredita de vuelta).

    Returns:
        Dict con 'estado_final' · 'result' · 'error' (si aplica).
    """
    accion_id = accion["id"]
    tipo = accion["tipo_accion"]
    estado = accion["estado"]
    riesgo_str = accion["riesgo"]
    riesgo = NivelRiesgo(riesgo_str)
    telefono = accion["telefono"]
    costo = int(accion.get("costo_creditos_estimado", 0) or 0)

    # Estado válido para ejecutar
    estado_ok = (
        (estado == "pending" and riesgo == NivelRiesgo.LOW)
        or estado == "approved"
    )
    if not estado_ok:
        msg = (
            f"Estado '{estado}' no permite ejecutar; riesgo={riesgo_str}. "
            f"MEDIUM/HIGH requieren aprobación."
        )
        await registrar_evento(
            evento="action_failed", telefono=telefono,
            accion_id=accion_id, riesgo=riesgo_str,
            payload={"tipo_accion": tipo, "razon": "estado_invalido"},
        )
        return {"estado_final": "failed", "error": msg}

    # T2.1.D · Reservar créditos ANTES de marcar_running. Si el saldo
    # es insuficiente, el usuario nunca ve la acción en 'running', y
    # nunca se intenta el ejecutor (LLM no se invoca).
    try:
        await reservar_creditos(
            accion_id=accion_id,
            telefono=telefono,
            creditos=costo,
            razon=f"{tipo} (riesgo={riesgo_str})",
        )
    except CreditosInsuficientesError as e:
        # Audit ya emitido dentro de reservar() · solo marcamos failed
        # pasando por running para respetar el lifecycle (pending → running
        # → failed o needs_approval/approved → running → failed).
        await marcar_running(accion_id)
        msg = (
            f"Créditos insuficientes: necesitas {e.requerido} · "
            f"tienes {e.saldo}. Compra créditos extra y reintenta."
        )
        await marcar_fallida(accion_id, error_message=msg)
        return {
            "estado_final": "failed",
            "error": "insufficient_credits",
            "saldo": e.saldo,
            "requerido": e.requerido,
        }

    # Pasamos a 'running'
    await marcar_running(accion_id)

    # Bloqueo crítico · liberamos la reserva (no debería pasar normalmente
    # porque el caller debería filtrar critical antes, pero defensa en
    # profundidad).
    if esta_bloqueado_t21(riesgo):
        await registrar_evento(
            evento="action_blocked_critical",
            telefono=telefono,
            accion_id=accion_id,
            riesgo=riesgo_str,
            payload={"tipo_accion": tipo, "razon": "critical_blocked_t21a"},
        )
        await liberar_creditos(accion_id, razon="critical_blocked_t21a")
        await marcar_fallida(
            accion_id,
            error_message=(
                "Acción CRITICAL bloqueada · requiere confirmación "
                "fuerte (futuro PR)."
            ),
        )
        return {
            "estado_final": "failed",
            "error": "critical_blocked_t21a",
        }

    # Ejecutor mapeado · si es HIGH no mapeado, rechaza · libera reserva
    ejecutor = EJECUTORES_T21A.get(tipo)
    if ejecutor is None:
        msg = (
            f"Tipo de acción '{tipo}' no tiene ejecutor disponible · "
            f"requiere guardrails reforzados (futuro PR)."
        )
        await liberar_creditos(accion_id, razon="ejecutor_no_disponible")
        await marcar_fallida(accion_id, error_message=msg)
        return {"estado_final": "failed", "error": msg}

    # Ejecutar (ya estamos en running)
    try:
        perfil_dict = await _cargar_perfil(telefono)
        result = await ejecutor(accion, perfil_dict)
    except Exception as e:
        msg = f"{type(e).__name__}: error interno durante ejecución"
        logger.exception(f"[EXEC] accion_id={accion_id} tipo={tipo}")
        await liberar_creditos(accion_id, razon="excepcion_ejecutor")
        await marcar_fallida(accion_id, error_message=msg)
        return {"estado_final": "failed", "error": msg}

    # T2.1.D · Confirmar reserva · el descuento queda firme.
    await confirmar_creditos(accion_id)

    # Audit log de la ejecución (sin output crudo · solo metadata segura).
    # Incluye creditos consumidos y tipo_accion para trazabilidad.
    await registrar_evento(
        evento="action_completed",
        telefono=telefono,
        accion_id=accion_id,
        riesgo=riesgo_str,
        payload={
            "tipo_accion": tipo,
            "modo": result.get("modo", "fallback"),
            "provider": result.get("provider", "fallback"),
            "creditos_descontados": costo,
        },
    )

    await marcar_completada(accion_id, result=result)
    return {"estado_final": "completed", "result": result}


async def _cargar_perfil(telefono: str) -> dict[str, Any] | None:
    """Lee perfil_negocio · retorna dict o None si no existe."""
    from agent.memory import async_session
    from agent.business.models import PerfilNegocio
    from sqlalchemy import select

    async with async_session() as session:
        row = (await session.execute(
            select(PerfilNegocio).where(PerfilNegocio.telefono == telefono)
        )).scalar_one_or_none()
    if row is None:
        return None
    return {
        "nombre_negocio": row.nombre_negocio,
        "industria": row.industria,
        "moneda": row.moneda,
        "meta_mensual": row.meta_mensual,
        "oferta_principal": row.oferta_principal,
        "cliente_ideal": row.cliente_ideal,
        "objetivo_mes": row.objetivo_mes,
        "canales_actuales": row.canales_actuales,
        "bloqueo_actual": row.bloqueo_actual,
        "tareas_delegar": row.tareas_delegar,
    }
