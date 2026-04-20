# agent/business/onboarding_negocio.py — Onboarding de negocio self-service

"""
Flujo guiado por WhatsApp para configurar el perfil de negocio.
Se activa cuando el usuario menciona su negocio por primera vez
y no tiene perfil configurado.

Flujo de 4 pasos:
  0 — Preguntar nombre del negocio
  1 — Preguntar tipo/industria
  2 — Preguntar moneda
  3 — Preguntar meta de ventas mensual (opcional)

Estado se guarda en perfil_negocio con un campo onboarding_paso.
"""

import logging
from datetime import datetime

from agent.memory import async_session
from agent.business.models import PerfilNegocio
from sqlalchemy import select

logger = logging.getLogger("agentkit")

# ── Mensajes del flujo ──────────────────────────────────────────────────────

MENSAJE_INICIO = """\
Soy Dona 🤖, un asistente de IA que te ayuda a organizar tu negocio.

Veo que tienes un negocio. Para ayudarte mejor, necesito conocer algunos datos.

*¿Cómo se llama tu negocio?* 🏪

_(Responde STOP en cualquier momento para desactivar mensajes proactivos)_"""

MENSAJE_INDUSTRIA = """\
Perfecto, *{nombre}*.

¿A qué se dedica? Elige una opción o escríbelo:
1. 🍰 Comida / Restaurante
2. 💇 Servicios personales
3. 🛍️ Tienda / Retail
4. 💻 Freelance / Consultoría
5. 🏗️ Otro"""

MENSAJE_MONEDA = """\
Entendido. ¿En qué moneda manejas tu negocio?
1. 🇲🇽 MXN (Pesos mexicanos)
2. 🇺🇸 USD (Dólares)
3. 🇨🇴 COP (Pesos colombianos)
4. 🇦🇷 ARS (Pesos argentinos)
5. 🇪🇺 EUR (Euros)

(Escribe el código o el número)"""

MENSAJE_META = """\
Último paso: ¿tienes una meta de ventas mensual? 📊

Escribe el monto (ej: *50000*) o *no* si prefieres omitirlo."""

MENSAJE_COMPLETADO = """\
¡Tu negocio está configurado! 🎉

*{nombre}* ({industria})
Moneda: {moneda}
{meta_texto}

Ya puedes:
• Registrar ventas y gastos
• Gestionar clientes y pedidos
• Crear cotizaciones
• Generar contenido para redes

Escríbeme lo que necesites 🚀"""

# Mapeo de respuestas a industrias
_INDUSTRIAS = {
    "1": "comida", "comida": "comida", "restaurante": "comida", "pastelería": "comida",
    "pasteleria": "comida", "cocina": "comida", "panadería": "comida", "panaderia": "comida",
    "2": "servicios", "servicios": "servicios", "barbería": "servicios", "barberia": "servicios",
    "peluquería": "servicios", "peluqueria": "servicios", "salón": "servicios", "salon": "servicios",
    "3": "retail", "tienda": "retail", "retail": "retail", "venta": "retail", "ventas": "retail",
    "4": "freelance", "freelance": "freelance", "consultoría": "freelance", "consultoria": "freelance",
    "diseño": "freelance", "diseno": "freelance", "programación": "freelance",
    "5": "otro", "otro": "otro",
}

_INDUSTRIA_LABEL = {
    "comida": "Comida / Restaurante",
    "servicios": "Servicios personales",
    "retail": "Tienda / Retail",
    "freelance": "Freelance / Consultoría",
    "otro": "Otro",
    "general": "General",
}

_MONEDAS = {
    "1": "MXN", "mxn": "MXN", "pesos": "MXN", "pesos mexicanos": "MXN",
    "2": "USD", "usd": "USD", "dólares": "USD", "dolares": "USD", "dollars": "USD",
    "3": "COP", "cop": "COP", "pesos colombianos": "COP",
    "4": "ARS", "ars": "ARS", "pesos argentinos": "ARS",
    "5": "EUR", "eur": "EUR", "euros": "EUR",
}

# Palabras que activan el onboarding automáticamente
TRIGGER_KEYWORDS = {
    "mi negocio", "mi empresa", "mi tienda", "mi local",
    "tengo un negocio", "tengo una tienda", "tengo un restaurante",
    "registra una venta", "vendí", "vendi",
    "mi pastelería", "mi pasteleria",
    "configurar negocio", "configurar mi negocio",
}


async def necesita_onboarding_negocio(telefono: str, texto: str) -> bool:
    """
    Retorna True si el usuario menciona su negocio pero no tiene perfil.
    """
    texto_lower = texto.lower()

    # Verificar si el texto contiene triggers
    tiene_trigger = any(kw in texto_lower for kw in TRIGGER_KEYWORDS)
    if not tiene_trigger:
        return False

    # Verificar si ya tiene perfil
    async with async_session() as session:
        result = await session.execute(
            select(PerfilNegocio).where(PerfilNegocio.telefono == telefono)
        )
        perfil = result.scalar_one_or_none()
        # Si ya tiene perfil con nombre, no necesita onboarding
        if perfil and perfil.nombre_negocio:
            return False
        # Si tiene perfil sin nombre (en medio del onboarding), sí necesita
        return True


async def esta_en_onboarding_negocio(telefono: str) -> bool:
    """Retorna True si el usuario está en medio del onboarding de negocio."""
    async with async_session() as session:
        result = await session.execute(
            select(PerfilNegocio).where(PerfilNegocio.telefono == telefono)
        )
        perfil = result.scalar_one_or_none()
        if not perfil:
            return False
        # onboarding_paso > 0 y nombre vacío = en medio del flujo
        # onboarding_paso 0 con nombre vacío = justo iniciado
        return not perfil.nombre_negocio and perfil.onboarding_paso is not None


async def iniciar_onboarding_negocio(telefono: str) -> str:
    """Inicia el flujo de onboarding creando un perfil vacío."""
    async with async_session() as session:
        result = await session.execute(
            select(PerfilNegocio).where(PerfilNegocio.telefono == telefono)
        )
        perfil = result.scalar_one_or_none()
        if not perfil:
            perfil = PerfilNegocio(
                telefono=telefono,
                nombre_negocio="",
                onboarding_paso=0,
                creado=datetime.utcnow(),
                actualizado=datetime.utcnow(),
            )
            session.add(perfil)
        else:
            perfil.onboarding_paso = 0
        await session.commit()
    logger.info(f"[BIZ-ONBOARD] Iniciado para {telefono}")
    return MENSAJE_INICIO


async def procesar_paso_onboarding(telefono: str, texto: str) -> str | None:
    """
    Procesa la respuesta del usuario en el onboarding de negocio.
    Retorna el siguiente mensaje del flujo, o None si ya terminó.
    """
    async with async_session() as session:
        result = await session.execute(
            select(PerfilNegocio).where(PerfilNegocio.telefono == telefono)
        )
        perfil = result.scalar_one_or_none()
        if not perfil or perfil.onboarding_paso is None:
            return None

        paso = perfil.onboarding_paso
        texto_limpio = texto.strip()

        # ── Paso 0: Nombre del negocio ──────────────────────────────
        if paso == 0:
            nombre = texto_limpio[:200]
            perfil.nombre_negocio = nombre
            perfil.onboarding_paso = 1
            perfil.actualizado = datetime.utcnow()
            await session.commit()
            return MENSAJE_INDUSTRIA.format(nombre=nombre)

        # ── Paso 1: Industria ───────────────────────────────────────
        elif paso == 1:
            industria = _INDUSTRIAS.get(texto_limpio.lower(), "otro")
            perfil.industria = industria
            perfil.onboarding_paso = 2
            perfil.actualizado = datetime.utcnow()
            await session.commit()
            return MENSAJE_MONEDA

        # ── Paso 2: Moneda ──────────────────────────────────────────
        elif paso == 2:
            moneda = _MONEDAS.get(texto_limpio.lower(), "MXN")
            perfil.moneda = moneda
            perfil.onboarding_paso = 3
            perfil.actualizado = datetime.utcnow()
            await session.commit()
            return MENSAJE_META

        # ── Paso 3: Meta mensual ────────────────────────────────────
        elif paso == 3:
            meta = 0.0
            _rechazos = {"no", "0", "omitir", "skip", "no tengo", "después", "despues"}
            if texto_limpio.lower() not in _rechazos:
                # Extraer número del texto
                import re
                numeros = re.findall(r"[\d,]+\.?\d*", texto_limpio.replace(",", ""))
                if numeros:
                    try:
                        meta = float(numeros[0].replace(",", ""))
                    except ValueError:
                        pass

            perfil.meta_mensual = meta
            perfil.onboarding_paso = None  # Onboarding completado
            perfil.actualizado = datetime.utcnow()
            await session.commit()

            # Generar mensaje de completado
            industria_label = _INDUSTRIA_LABEL.get(perfil.industria, perfil.industria)
            meta_texto = f"Meta mensual: ${meta:,.0f}" if meta > 0 else "Sin meta mensual configurada"
            logger.info(f"[BIZ-ONBOARD] Completado para {telefono}: {perfil.nombre_negocio}")
            return MENSAJE_COMPLETADO.format(
                nombre=perfil.nombre_negocio,
                industria=industria_label,
                moneda=perfil.moneda,
                meta_texto=meta_texto,
            )

    return None
