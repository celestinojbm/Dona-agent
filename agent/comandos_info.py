# agent/comandos_info.py — Comandos "dona ayuda" y "dona estado"

"""
Dos comandos de descubrimiento y auto-diagnóstico:

  - `dona ayuda` → lista (agrupada por dominio) de cosas que Dona sabe hacer,
    con ejemplos copiables. Es el primer lugar al que mandar a un usuario
    confundido. Personalizado según qué integraciones tiene conectadas.

  - `dona estado` → health check interno. Reporta integraciones conectadas,
    jobs del scheduler activos, y un conteo de actividad reciente. Sirve
    para debug y para que el usuario vea que Dona está "viva".

Ambos comandos viven acá (y no en main.py) para que sean testeables sin
levantar FastAPI, y para concentrar la "lógica de presentación" en un solo
archivo cuando agreguemos más comandos de este tipo.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta
from typing import Any

logger = logging.getLogger("agentkit")


# ── Detección ──────────────────────────────────────────────────────────────

_COMANDOS_AYUDA = {
    "dona ayuda", "dona help", "dona que puedes hacer", "dona qué puedes hacer",
    "dona que haces", "dona qué haces", "dona que sabes hacer", "dona qué sabes hacer",
    "dona comandos", "dona manual",
}

_COMANDOS_ESTADO = {
    "dona estado", "dona status", "dona diagnostico", "dona diagnóstico",
    "dona salud", "dona health",
}


def es_comando_ayuda(texto: str) -> bool:
    """True si el texto es una invocación del comando de ayuda."""
    if not texto:
        return False
    return texto.strip().lower() in _COMANDOS_AYUDA


def es_comando_estado(texto: str) -> bool:
    """True si el texto es una invocación del comando de estado."""
    if not texto:
        return False
    return texto.strip().lower() in _COMANDOS_ESTADO


# ── Ayuda ──────────────────────────────────────────────────────────────────

async def generar_texto_ayuda(telefono: str) -> str:
    """
    Retorna el texto del comando de ayuda, personalizado según las integraciones
    conectadas del usuario. Si Google está conectado muestra ejemplos que lo
    aprovechan; si no, sugiere conectar primero.
    """
    google_conectado = False
    try:
        from agent.memory import obtener_google_auth
        auth = await obtener_google_auth(telefono)
        google_conectado = bool(auth)
    except Exception:
        pass

    secciones: list[str] = [
        "🤖 *Dona — Qué puedo hacer*",
        "",
        "*💰 Finanzas*",
        "• \"vendí $200 hoy\" — registro una venta",
        "• \"gasté $30 en insumos\" — registro un gasto",
        "• \"dona resumen del mes\" — reporte financiero",
        "• \"dona exporta octubre\" — CSV de transacciones",
        "• \"dona exporta por correo\" — mismo CSV por email",
        "",
        "*👥 Clientes (CRM)*",
        "• \"registra cliente María con tel 555-1234\"",
        "• \"busca clientes\" — lista tu cartera",
        "• \"dar seguimiento a Juan el lunes\"",
        "",
        "*📦 Productos y pedidos*",
        "• \"registra producto pastel de chocolate $250\"",
        "• \"crea pedido de Ana: 2 pasteles para el viernes\"",
        "• \"actualiza el pedido a entregado\"",
        "",
        "*📝 Notas y recordatorios*",
        "• \"recuérdame pagar la luz el viernes\"",
        "• \"anota: idea de promo para el día del padre\"",
        "• \"busca en mis notas sobre proveedores\"",
        "",
        "*✍️ Contenido*",
        "• \"dame un post para Instagram sobre mi promo\"",
        "• \"cotiza 3 pasteles para un evento\"",
    ]

    if google_conectado:
        secciones.extend([
            "",
            "*🗓️ Calendario (Google)*",
            "• \"qué tengo hoy?\" — tus eventos del día",
            "• \"agéndame reunión con Ana mañana 4pm\"",
            "",
            "*✉️ Correo (Gmail)*",
            "• \"lee mis correos no leídos\"",
            "• \"mándale correo a Juan\" (busca el email en tus contactos)",
            "• \"responde el último de María\"",
            "",
            "*✅ Tareas (Google Tasks)*",
            "• \"agrega tarea llamar al banco\"",
            "• \"qué tengo pendiente?\"",
            "• \"marca como hecha la tarea de X\"",
            "",
            "*📊 Sheets*",
            "• \"registra mi hoja de ventas: [link]\"",
            "• \"agrega fila a mi hoja\" / \"lee mi hoja\"",
        ])
    else:
        secciones.extend([
            "",
            "🔗 *Conectar Google* (para más capacidades)",
            "Escribe *\"dona conectar google\"* para habilitar:",
            "calendario, correo, tareas, sheets, drive y contactos.",
        ])

    secciones.extend([
        "",
        "*💳 Créditos y creaciones*",
        "• \"dona saldo\" — ver tus créditos disponibles",
        "• \"dona recargar\" — comprar más créditos",
        "• \"dona mis assets\" — últimas imágenes/videos generados",
        "",
        "*🛠️ Comandos útiles*",
        "• \"dona estado\" — ver integraciones y jobs",
        "• \"dona pausa\" / \"dona reanuda\" — mensajes proactivos",
        "• \"dona exportar datos\" / \"dona borrar mis datos\" — CCPA",
        "",
        "_Tip: también puedes escribirme normal — no necesitas comandos._",
    ])
    return "\n".join(secciones)


# ── Estado ─────────────────────────────────────────────────────────────────

def _describir_job(job: Any) -> str:
    """Devuelve un string humano describiendo un APScheduler Job."""
    trigger = getattr(job, "trigger", None)
    trigger_str = str(trigger) if trigger else "?"
    nombre = getattr(job, "id", getattr(job, "name", "?"))
    # Acortar trigger_str para que quepa bonito en WhatsApp
    if len(trigger_str) > 50:
        trigger_str = trigger_str[:47] + "..."
    return f"• `{nombre}` — {trigger_str}"


async def _contar_mensajes_recientes(telefono: str, horas: int = 24) -> int:
    """
    Cuenta los mensajes procesados del usuario en las últimas N horas.
    Retorna 0 si la tabla no existe o hay error (best-effort).
    """
    try:
        from agent.memory import async_session, Mensaje
        from sqlalchemy import select, and_, func

        corte = datetime.utcnow() - timedelta(hours=horas)
        async with async_session() as session:
            q = select(func.count(Mensaje.id)).where(
                and_(
                    Mensaje.telefono == telefono,
                    Mensaje.timestamp >= corte,
                )
            )
            result = await session.execute(q)
            return int(result.scalar() or 0)
    except Exception as e:
        logger.debug(f"[ESTADO] No se pudieron contar mensajes: {e}")
        return 0


async def generar_texto_estado(telefono: str) -> str:
    """
    Retorna un texto con el estado interno de Dona para este usuario:
      - integraciones Google conectadas + email
      - jobs del scheduler activos
      - mensajes procesados en las últimas 24 h
      - señales de configuración del entorno (sin revelar secretos)
    """
    lineas: list[str] = ["🩺 *Estado de Dona*", ""]

    # Google (OAuth)
    email_google = ""
    try:
        from agent.memory import obtener_google_auth
        auth = await obtener_google_auth(telefono)
        if auth:
            email_google = auth.get("email", "") or "(sin email)"
    except Exception:
        pass
    if email_google:
        lineas.append(f"🔗 *Google:* conectado ({email_google})")
    else:
        lineas.append("🔗 *Google:* no conectado — `dona conectar google`")

    # Variables de entorno clave (sin exponer valores)
    env_anthropic = bool(os.getenv("ANTHROPIC_API_KEY"))
    env_whatsapp_prov = os.getenv("WHATSAPP_PROVIDER", "whapi")
    env_redis = bool(os.getenv("REDIS_URL"))
    lineas.append(
        f"⚙️ *Runtime:* IA {'✓' if env_anthropic else '✗'} · "
        f"WhatsApp={env_whatsapp_prov} · "
        f"Redis {'✓' if env_redis else '—'}"
    )

    # Scheduler jobs
    try:
        from agent.scheduler import scheduler
        if scheduler.running:
            jobs = scheduler.get_jobs()
            lineas.append("")
            lineas.append(f"⏰ *Scheduler* ({len(jobs)} jobs activos):")
            for job in jobs[:12]:  # limitar a 12 por tamaño de mensaje
                lineas.append(_describir_job(job))
            if len(jobs) > 12:
                lineas.append(f"  …y {len(jobs) - 12} más")
        else:
            lineas.append("")
            lineas.append("⏰ *Scheduler:* detenido")
    except Exception as e:
        logger.debug(f"[ESTADO] Scheduler info no disponible: {e}")

    # Actividad reciente
    mensajes_24h = await _contar_mensajes_recientes(telefono, horas=24)
    lineas.append("")
    lineas.append(f"💬 *Actividad 24h:* {mensajes_24h} mensajes procesados")

    # Saldo de créditos (best-effort — no bloquea si billing no está configurado)
    try:
        from agent.billing import obtener_saldo
        saldo = await obtener_saldo(telefono)
        lineas.append(f"💳 *Créditos:* {saldo} disponibles")
    except Exception as e:
        logger.debug(f"[ESTADO] Billing info no disponible: {e}")

    lineas.append("")
    lineas.append("_Escribe *\"dona ayuda\"* para ver el manual completo._")
    return "\n".join(lineas)
