# agent/business/onboarding_negocio.py — Onboarding de negocio self-service

"""
Flujo guiado por WhatsApp para configurar el perfil de negocio.
Se activa cuando el usuario menciona su negocio por primera vez
y no tiene perfil configurado, o cuando dispara la palabra
"diagnóstico" (T2.0.E.1).

Flujo de 10 pasos:
  0 — nombre del negocio
  1 — tipo/industria
  2 — moneda
  3 — meta de ventas mensual (opcional)

  T2.0.E.1 — diagnóstico extendido (texto libre, todos opcionales):
  4 — oferta principal
  5 — cliente ideal
  6 — objetivo del mes (texto · complementa meta_mensual)
  7 — canales actuales
  8 — mayor bloqueo
  9 — tareas que quiere delegar a Dona

Estado se guarda en perfil_negocio con un campo onboarding_paso.
None = completado, 0-9 = en progreso. Cada paso se aplica de forma
idempotente: re-recibir el mismo paso no duplica datos.

Privacidad (T2.0.E.1):
  - Las respuestas de los pasos 4-9 son texto libre y pueden incluir
    PII de clientes del usuario. NO se loguea el contenido bruto.
    Solo paso, longitud y telefono truncado en el log.
  - El borrado de datos del owner via 'dona borrar mis datos' (CCPA)
    elimina perfil_negocio entero · cubre los nuevos campos.
"""

import logging
from datetime import datetime

from agent.memory import async_session
from agent.business.models import PerfilNegocio
from sqlalchemy import select

logger = logging.getLogger("dona")

# ── Logging seguro · helpers ────────────────────────────────────────────────


def _short_telefono(telefono: str) -> str:
    """Trunca teléfono para logs. Mismo patrón que agent/welcome.py."""
    if not telefono:
        return "***"
    if len(telefono) <= 6:
        return "***"
    return f"{telefono[:2]}****{telefono[-4:]}"


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
Penúltima parte rápida: ¿tienes una meta de ventas mensual? 📊

Escribe el monto (ej: *50000*) o *no* si prefieres omitirlo."""

# T2.0.E.1 — preguntas extendidas del diagnóstico inicial.
# Cada paso permite "saltar" con respuestas como "no", "omitir", "skip".

MENSAJE_OFERTA = """\
Ahora un diagnóstico breve para que pueda ayudarte mejor 🎯

*Paso 1 de 6 · ¿Cuál es tu oferta principal?*

Cuéntame en pocas palabras qué vendes o qué servicio ofreces. Si tienes varios, el más importante.

_(Escribe *omitir* si prefieres saltar este paso)_"""

MENSAJE_CLIENTE_IDEAL = """\
Anotado.

*Paso 2 de 6 · ¿Quién es tu cliente ideal?*

Describe brevemente a la persona o tipo de negocio al que vendes (edad, contexto, qué necesita).

_(Escribe *omitir* para saltar)_"""

MENSAJE_OBJETIVO_MES = """\
Bien.

*Paso 3 de 6 · ¿Cuál es tu objetivo principal este mes?*

Por ejemplo: 'conseguir 10 clientes nuevos', 'lanzar mi tienda online', 'recuperar clientes que dejaron de comprar'.

_(Escribe *omitir* para saltar)_"""

MENSAJE_CANALES = """\
Perfecto.

*Paso 4 de 6 · ¿Por qué canales vendes hoy?*

Por ejemplo: WhatsApp, Instagram, tienda física, referidos, marketplace, página web. Puedes mencionar varios.

_(Escribe *omitir* para saltar)_"""

MENSAJE_BLOQUEO = """\
Ya casi terminamos.

*Paso 5 de 6 · ¿Cuál es tu mayor bloqueo o frustración hoy?*

¿Qué te quita tiempo o te impide crecer? Sé directo.

_(Escribe *omitir* para saltar)_"""

MENSAJE_TAREAS_DELEGAR = """\
Última pregunta.

*Paso 6 de 6 · ¿Qué tareas te gustaría delegar a Dona?*

Por ejemplo: responder mensajes repetidos, hacer cotizaciones, recordar pagos, generar contenido para redes, llevar tus ventas.

_(Escribe *omitir* para saltar)_"""

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

# Respuestas que indican que el usuario quiere saltar la pregunta.
# Aplican a los pasos 4-9 (texto libre) y al paso 3 (meta numérica).
_RECHAZOS = {
    "no", "0", "omitir", "skip", "no tengo", "después", "despues",
    "saltar", "ninguno", "ninguna", "nada", "no sé", "no se",
    "mas tarde", "más tarde", "luego",
}


def _es_rechazo(texto: str) -> bool:
    """True si el usuario quiere saltar el paso · case-insensitive."""
    return texto.strip().lower() in _RECHAZOS


# Palabras que activan el onboarding automáticamente.
# T2.0.E.1 — agregamos "diagnóstico" para que el wa.me del tour
# (T2.0.D step 8) dispare el flow al recibir el texto pre-llenado.
TRIGGER_KEYWORDS = {
    "mi negocio", "mi empresa", "mi tienda", "mi local",
    "tengo un negocio", "tengo una tienda", "tengo un restaurante",
    "registra una venta", "vendí", "vendi",
    "mi pastelería", "mi pasteleria",
    "configurar negocio", "configurar mi negocio",
    # T2.0.E.1
    "diagnóstico", "diagnostico",
    "empezar diagnóstico", "empezar diagnostico",
    "iniciar diagnóstico", "iniciar diagnostico",
    "diagnostico de mi negocio", "diagnóstico de mi negocio",
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
        # onboarding_paso 4-9 = en el diagnóstico extendido
        if perfil.onboarding_paso is None:
            return False
        if perfil.onboarding_paso == 0 and not perfil.nombre_negocio:
            return True
        if 1 <= perfil.onboarding_paso <= 9:
            return True
        return False


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
    logger.info(f"[BIZ-ONBOARD] Iniciado para {_short_telefono(telefono)}")
    return MENSAJE_INICIO


# Cap para texto libre · evita persistir bloques enormes en DB.
# CCPA permite "minimización de datos"; un mensaje normal cabe en 500 chars.
_MAX_TEXTO_LIBRE = 500


def _capar_texto(texto: str) -> str:
    """Trunca texto libre a _MAX_TEXTO_LIBRE chars."""
    return texto.strip()[:_MAX_TEXTO_LIBRE]


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

        # Logging seguro · sólo paso, longitud, telefono truncado.
        # NUNCA loguear el contenido del texto del usuario · puede tener PII.
        logger.info(
            f"[BIZ-ONBOARD] tel={_short_telefono(telefono)} "
            f"paso={paso} resp_len={len(texto_limpio)}"
        )

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
            if not _es_rechazo(texto_limpio):
                # Extraer número del texto
                import re
                numeros = re.findall(r"[\d,]+\.?\d*", texto_limpio.replace(",", ""))
                if numeros:
                    try:
                        meta = float(numeros[0].replace(",", ""))
                    except ValueError:
                        pass

            perfil.meta_mensual = meta
            perfil.onboarding_paso = 4  # T2.0.E.1 — sigue el diagnóstico
            perfil.actualizado = datetime.utcnow()
            await session.commit()
            return MENSAJE_OFERTA

        # ── Paso 4 (T2.0.E.1): Oferta principal ─────────────────────
        elif paso == 4:
            perfil.oferta_principal = (
                "" if _es_rechazo(texto_limpio) else _capar_texto(texto_limpio)
            )
            perfil.onboarding_paso = 5
            perfil.actualizado = datetime.utcnow()
            await session.commit()
            return MENSAJE_CLIENTE_IDEAL

        # ── Paso 5 (T2.0.E.1): Cliente ideal ────────────────────────
        elif paso == 5:
            perfil.cliente_ideal = (
                "" if _es_rechazo(texto_limpio) else _capar_texto(texto_limpio)
            )
            perfil.onboarding_paso = 6
            perfil.actualizado = datetime.utcnow()
            await session.commit()
            return MENSAJE_OBJETIVO_MES

        # ── Paso 6 (T2.0.E.1): Objetivo del mes (texto) ─────────────
        elif paso == 6:
            perfil.objetivo_mes = (
                "" if _es_rechazo(texto_limpio) else _capar_texto(texto_limpio)
            )
            perfil.onboarding_paso = 7
            perfil.actualizado = datetime.utcnow()
            await session.commit()
            return MENSAJE_CANALES

        # ── Paso 7 (T2.0.E.1): Canales actuales ─────────────────────
        elif paso == 7:
            perfil.canales_actuales = (
                "" if _es_rechazo(texto_limpio) else _capar_texto(texto_limpio)
            )
            perfil.onboarding_paso = 8
            perfil.actualizado = datetime.utcnow()
            await session.commit()
            return MENSAJE_BLOQUEO

        # ── Paso 8 (T2.0.E.1): Mayor bloqueo ────────────────────────
        elif paso == 8:
            perfil.bloqueo_actual = (
                "" if _es_rechazo(texto_limpio) else _capar_texto(texto_limpio)
            )
            perfil.onboarding_paso = 9
            perfil.actualizado = datetime.utcnow()
            await session.commit()
            return MENSAJE_TAREAS_DELEGAR

        # ── Paso 9 (T2.0.E.1): Tareas que delegar a Dona · CIERRA ───
        elif paso == 9:
            perfil.tareas_delegar = (
                "" if _es_rechazo(texto_limpio) else _capar_texto(texto_limpio)
            )
            perfil.onboarding_paso = None  # Onboarding completado
            perfil.actualizado = datetime.utcnow()
            await session.commit()

            # Generar mensaje de completado.
            # NO incluimos el texto libre de los pasos 4-9 en el mensaje
            # (UX: ya lo tipeó · evita ruido). Solo el resumen estructurado.
            industria_label = _INDUSTRIA_LABEL.get(perfil.industria, perfil.industria)
            meta_texto = (
                f"Meta mensual: ${perfil.meta_mensual:,.0f}"
                if perfil.meta_mensual > 0 else "Sin meta mensual configurada"
            )
            logger.info(
                f"[BIZ-ONBOARD] Completado tel={_short_telefono(telefono)} "
                f"industria={perfil.industria}"
            )
            return MENSAJE_COMPLETADO.format(
                nombre=perfil.nombre_negocio,
                industria=industria_label,
                moneda=perfil.moneda,
                meta_texto=meta_texto,
            )

    return None
