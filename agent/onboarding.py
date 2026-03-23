# agent/onboarding.py — Flujo de onboarding conversacional de Dona
# Generado por AgentKit

"""
Onboarding de 3 fases distribuidas en 3 días.
Cada respuesta alimenta MiroFish para construir el grafo de conocimiento del usuario.

Fases:
  Fase 1 — Fundación: proyectos, rutina, metas
  Fase 2 — Relaciones y trabajo: personas clave, métodos, zonas de genio
  Fase 3 — Visión y personalización: frustraciones, estilo, visión a 12 meses
"""

import asyncio
import logging
from datetime import datetime, timezone

logger = logging.getLogger("agentkit")

# ─── MENSAJES ────────────────────────────────────────────────────────────────

MENSAJE_BIENVENIDA = """\
¡Hola! 👋 Soy *Dona*, tu asistente de IA personal en WhatsApp.

Para ser realmente útil para ti — no solo un recordatorio genérico — necesito conocerte bien.

Voy a hacerte algunas preguntas en los próximos días. Cada cosa que compartas me hace más inteligente para ayudarte.

¿Empezamos ahora? Responde *sí* cuando estés listo ✨"""

MENSAJE_PEDIR_NOMBRE = """\
Genial! Antes de empezar — ¿cómo te llamas? 😊"""

MENSAJE_PEDIR_CIUDAD = """\
Perfecto {nombre}! Una última cosa antes de empezar:

¿En qué ciudad y país vives? Esto me permite avisarte del clima cuando tengas reuniones presenciales 🌍

(Escribe algo como "Ciudad de México, México" o "Bogotá, Colombia". Si prefieres omitirlo, escribe *omitir*)"""

_PALABRAS_OMITIR = {"omitir", "no", "skip", "saltar", "después", "despues", "no quiero"}

# Mensajes de cada paso: (fase, paso) → texto
MENSAJES = {
    # ── Fase 1: Fundación ─────────────────────────────────────────────────────
    (1, 0): """\
Perfecto {nombre}. Primera pregunta:

¿En qué proyectos estás trabajando ahora mismo? Pueden ser de trabajo, personales o ambos.

No necesitas ser formal — cuéntame como le contarías a un amigo 🙌""",

    (1, 1): """\
Genial, ya tengo contexto de tus proyectos 📝

Ahora cuéntame: ¿cómo es tu día típico? ¿A qué hora empiezas, cuándo tienes más energía, cuándo te cuesta más concentrarte?""",

    (1, 2): """\
Interesante. Última pregunta de hoy:

¿Cuáles son tus metas más importantes en los próximos 3, 6 y 12 meses? Pueden ser de trabajo, dinero, salud, relaciones — lo que sea importante para ti.""",

    # ── Fase 2: Relaciones y trabajo ──────────────────────────────────────────
    (2, 0): """\
Buenos días {nombre} ☀️

Ayer me contaste sobre tus proyectos y metas. Hoy quiero conocer a las personas importantes en tu mundo.

¿Quiénes son las 3-5 personas más importantes en tu trabajo? (clientes, socios, equipo, jefe — quien sea clave para ti)""",

    (2, 1): """\
Gracias. Ya tengo contexto de tu red de trabajo.

¿Cómo prefieres trabajar? ¿Eres más de listas o de fluir? ¿Prefieres bloques de tiempo o ir tarea por tarea? ¿Qué herramientas usas (Notion, Google Calendar, papel...)?""",

    (2, 2): """\
Casi terminamos la fase 2. Una pregunta importante:

¿En qué actividades entras en "modo flow" — donde el tiempo vuela y produces tu mejor trabajo?

Y al contrario: ¿qué tareas te drenan la energía o pospones constantemente?""",

    # ── Fase 3: Visión y personalización ──────────────────────────────────────
    (3, 0): """\
Buenos días {nombre} 🌟

Última ronda de preguntas. Hoy quiero entender tu visión y cómo puedo ser la mejor versión de mí misma para ti.

¿Qué te ha frustrado de otros asistentes, apps de productividad o herramientas que hayas probado antes?""",

    (3, 1): """\
Entendido. Eso me ayuda a saber qué NO hacer.

¿Cómo prefieres que me comunique contigo?
- ¿Mensajes cortos y directos o explicaciones detalladas?
- ¿Que te recuerde las cosas o que espere a que me preguntes?
- ¿Que use emojis o que sea más formal?""",

    (3, 2): """\
Última pregunta:

Si en 12 meses tu vida fuera exactamente como la quieres — ¿cómo se vería? ¿Qué habrías logrado? ¿Cómo te sentirías?

Esto me ayuda a conectar lo urgente del día a día con lo que realmente importa para ti.""",
}

MENSAJE_CIERRE_FASE_1 = """\
Perfecto {nombre}, ya tengo una imagen clara de tu mundo 🧠

Mañana te hago unas preguntas sobre las personas importantes en tu trabajo y vida. Eso me permitirá ayudarte mucho mejor.

Por ahora, dime: ¿hay algo urgente en lo que pueda ayudarte hoy?"""

MENSAJE_CIERRE_FASE_2 = """\
Excelente {nombre}. Ahora entiendo cómo trabajas y con quién 💪

Mañana última ronda — te pregunto sobre tu visión y cómo quieres que me comunique contigo.

¿Hay algo en lo que pueda ayudarte hoy?"""

MENSAJE_CIERRE_ONBOARDING = """\
{nombre}, eso es todo 🎉

Ya tengo todo lo que necesito para ser tu mejor asistente. A partir de ahora:

✅ Recuerdo quién es quién en tu vida
✅ Entiendo tus proyectos y prioridades
✅ Sé cómo y cuándo ayudarte mejor
✅ Puedo anticiparme a lo que necesitas

Estoy lista. ¿Por dónde empezamos? 🚀"""

# Etiquetas para el contexto acumulado que se envía a MiroFish
_ETIQUETAS = {
    (1, 0): "PROYECTOS ACTUALES",
    (1, 1): "RUTINA DIARIA",
    (1, 2): "METAS 3-6-12 MESES",
    (2, 0): "PERSONAS CLAVE EN EL TRABAJO",
    (2, 1): "METODOS Y HERRAMIENTAS DE TRABAJO",
    (2, 2): "ZONAS DE GENIO Y TAREAS QUE EVITA",
    (3, 0): "FRUSTRACIONES CON HERRAMIENTAS ANTERIORES",
    (3, 1): "ESTILO DE COMUNICACION PREFERIDO",
    (3, 2): "VISION DE VIDA A 12 MESES",
}

# Palabras que el usuario puede decir para confirmar el inicio
_CONFIRMACIONES = {"sí", "si", "yes", "ok", "dale", "listo", "empezamos", "empezar", "vamos", "claro", "adelante"}


# ─── LÓGICA PRINCIPAL ────────────────────────────────────────────────────────

async def es_onboarding_activo(telefono: str) -> bool:
    """Retorna True si el usuario está en medio del onboarding (fases 1-3, paso activo)."""
    from agent.memory import obtener_onboarding
    estado = await obtener_onboarding(telefono)
    if not estado:
        return True   # Usuario nuevo — el onboarding debe iniciarse
    fase = estado["fase"]
    paso = estado["paso"]
    # Activo si: esperando "sí" (fase=0), o en una fase con paso activo (0-2, no 99 ni 4)
    return fase in (0, 1, 2, 3) and paso != 99 and fase != 4


async def procesar_mensaje_onboarding(telefono: str, texto: str) -> str | None:
    """
    Maneja el mensaje del usuario durante el onboarding.

    Retorna:
        str: Respuesta de Dona para este paso del onboarding.
        None: Si el onboarding ya terminó (fase=4) o está en pausa (paso=99).
              En ese caso, el mensaje debe procesarse por el flujo normal de Dona.
    """
    from agent.memory import obtener_onboarding, guardar_onboarding

    estado = await obtener_onboarding(telefono)

    # ── Usuario completamente nuevo (sin registro) ────────────────────────────
    if not estado:
        await guardar_onboarding(telefono, fase=0, paso=0, nombre="", contexto="")
        return MENSAJE_BIENVENIDA

    fase = estado["fase"]
    paso = estado["paso"]
    nombre = estado.get("nombre") or ""

    # ── Onboarding completado ─────────────────────────────────────────────────
    if fase == 4:
        return None  # Flujo normal

    # ── En pausa entre fases (esperando activación del scheduler) ────────────
    if paso == 99:
        return None  # Flujo normal mientras espera el día siguiente

    # ── Fase 0: bienvenida — esperando respuesta ─────────────────────────────
    # Aceptamos cualquier mensaje como confirmación implícita — si el usuario
    # responde, está listo. Solo el "no" explícito detiene el flujo.
    if fase == 0 and paso == 0:
        _RECHAZOS = {"no", "no quiero", "ahora no", "luego", "después", "despues", "ahorita no"}
        if texto.strip().lower() in _RECHAZOS:
            return "Entendido 😊 Escríbeme cuando quieras empezar."
        await guardar_onboarding(telefono, fase=0, paso=1)
        return MENSAJE_PEDIR_NOMBRE

    # ── Fase 0, paso 1: capturar nombre ──────────────────────────────────────
    if fase == 0 and paso == 1:
        nombre_capturado = _extraer_nombre(texto)
        await guardar_onboarding(telefono, fase=0, paso=2, nombre=nombre_capturado)
        return MENSAJE_PEDIR_CIUDAD.format(nombre=nombre_capturado)

    # ── Fase 0, paso 2: capturar ciudad ──────────────────────────────────────
    if fase == 0 and paso == 2:
        nombre = estado.get("nombre") or ""
        if texto.strip().lower() not in _PALABRAS_OMITIR:
            ciudad, pais = _extraer_ciudad_pais(texto)
            from agent.memory import guardar_ubicacion
            await guardar_ubicacion(telefono, ciudad=ciudad, pais=pais)
            confirmacion = f"¡Perfecto! Registré *{ciudad}* 📍\n\n"
        else:
            confirmacion = "¡Listo! Omitiremos la ubicación por ahora.\n\n"
        await guardar_onboarding(telefono, fase=1, paso=0)
        return confirmacion + MENSAJES[(1, 0)].format(nombre=nombre)

    # ── Fases 1-3: detectar preguntas fuera del flujo antes de avanzar ─────────
    if fase in (1, 2, 3):
        if _es_pregunta_fuera_de_flujo(texto):
            # Claude responde la pregunta, el estado de onboarding no avanza
            return None
        return await _avanzar_fase(telefono, estado, texto)

    return None


async def _avanzar_fase(telefono: str, estado: dict, respuesta_usuario: str) -> str:
    """
    Acumula la respuesta del usuario, la envía a MiroFish en background,
    y retorna el siguiente mensaje del flujo.
    """
    from agent.memory import guardar_onboarding, guardar_mirofish_estado, obtener_mirofish_estado

    fase = estado["fase"]
    paso = estado["paso"]
    nombre = estado.get("nombre") or ""
    contexto_actual = estado.get("contexto") or ""

    # Etiquetar y acumular el contexto
    etiqueta = _ETIQUETAS.get((fase, paso), f"FASE {fase} PASO {paso}")
    nuevo_contexto = f"{contexto_actual}\n\n[{etiqueta}]\n{respuesta_usuario}".strip()

    siguiente_paso = paso + 1

    # ── Fin de fase (3 preguntas por fase: pasos 0, 1, 2) ────────────────────
    if siguiente_paso >= 3:
        # Guardar con paso=99 → pausa hasta el scheduler del día siguiente
        await guardar_onboarding(telefono, paso=99, contexto=nuevo_contexto)

        # Construir grafo MiroFish con todo el contexto acumulado (background)
        asyncio.create_task(_construir_grafo_onboarding(telefono, nuevo_contexto))

        if fase == 1:
            return MENSAJE_CIERRE_FASE_1.format(nombre=nombre)
        elif fase == 2:
            return MENSAJE_CIERRE_FASE_2.format(nombre=nombre)
        else:  # fase 3
            # Onboarding completo
            await guardar_onboarding(
                telefono,
                fase=4,
                paso=0,
                contexto=nuevo_contexto,
                completado_en=datetime.utcnow(),
            )
            asyncio.create_task(_construir_grafo_onboarding(telefono, nuevo_contexto))
            return MENSAJE_CIERRE_ONBOARDING.format(nombre=nombre)

    # ── Siguiente pregunta dentro de la misma fase ────────────────────────────
    await guardar_onboarding(telefono, paso=siguiente_paso, contexto=nuevo_contexto)

    # Construir grafo parcial en background (actualización progresiva)
    asyncio.create_task(_construir_grafo_onboarding(telefono, nuevo_contexto))

    siguiente_mensaje = MENSAJES.get((fase, siguiente_paso), "")
    return siguiente_mensaje.format(nombre=nombre)


async def iniciar_siguiente_fase(telefono: str, proveedor) -> bool:
    """
    Activa la siguiente fase del onboarding.
    Llamada por el scheduler cuando han pasado 18+ horas desde el cierre de la fase anterior.
    Retorna True si se activó la fase, False si no aplica.
    """
    from agent.memory import obtener_onboarding, guardar_onboarding

    estado = await obtener_onboarding(telefono)
    if not estado or estado["paso"] != 99:
        return False

    fase_actual = estado["fase"]
    nombre = estado.get("nombre") or ""

    if fase_actual == 1:
        siguiente_fase = 2
    elif fase_actual == 2:
        siguiente_fase = 3
    else:
        return False

    await guardar_onboarding(telefono, fase=siguiente_fase, paso=0)

    mensaje_inicio = MENSAJES[(siguiente_fase, 0)].format(nombre=nombre)
    await proveedor.enviar_mensaje(telefono, mensaje_inicio)
    logger.info(f"Onboarding: fase {siguiente_fase} iniciada para {telefono}")
    return True


# ─── HELPERS ─────────────────────────────────────────────────────────────────

_PREFIJOS_UBICACION = (
    "vivo en el ", "vivo en la ", "vivo en ",
    "soy de el ", "soy de la ", "soy del ", "soy de ",
    "estoy en el ", "estoy en la ", "estoy en ",
    "me encuentro en ", "resido en el ", "resido en la ", "resido en ",
    "mi ciudad es ", "mi ciudad natal es ",
)


def _extraer_ciudad_pais(texto: str) -> tuple[str, str]:
    """
    Extrae ciudad y país de un texto libre.
    Ej: "Ciudad de México, México"  → ("Ciudad de México", "México")
    Ej: "Bogotá"                    → ("Bogotá", "")
    Ej: "Vivo en Altamonte springs" → ("Altamonte Springs", "")
    """
    texto = texto.strip()
    texto_lower = texto.lower()
    for prefijo in _PREFIJOS_UBICACION:
        if texto_lower.startswith(prefijo):
            texto = texto[len(prefijo):]  # quitar prefijo, conservar capitalización original
            break
    if "," in texto:
        partes = texto.split(",", 1)
        return partes[0].strip().title(), partes[1].strip().title()
    return texto.strip().title(), ""


def _es_pregunta_fuera_de_flujo(texto: str) -> bool:
    """
    Detecta si el mensaje es una pregunta que no corresponde al onboarding.
    En ese caso el mensaje se pasa a Claude sin avanzar el estado.
    Ejemplos que devuelven True:
      "¿Sabes dónde vivo?"
      "Qué hora es?"
      "¿Puedes ayudarme con algo ahora?"
    """
    t = texto.strip()
    return t.startswith("¿") or t.endswith("?")


def _extraer_nombre(texto: str) -> str:
    """
    Extrae el nombre del texto del usuario.
    Toma la primera palabra con mayúscula, o el texto completo si es corto.
    """
    texto = texto.strip()
    if len(texto) <= 20:
        return texto.strip().title()
    # Tomar primera palabra
    primera = texto.split()[0]
    return primera.strip(".,!?¡¿").title()


async def _construir_grafo_onboarding(telefono: str, contexto: str):
    """
    Construye o actualiza el grafo MiroFish con el contexto acumulado del onboarding.
    Silencioso — no interrumpe la experiencia del usuario.
    """
    import agent.mirofish_client as mf
    from agent.memory import guardar_mirofish_estado

    if not mf._disponible():
        return

    try:
        logger.info(f"MiroFish: construyendo grafo de onboarding para {telefono} ({len(contexto)} chars)")
        project_id, graph_id = await mf.construir_grafo_completo(
            texto=contexto,
            telefono=telefono,
            requerimiento=(
                "Analiza las relaciones, proyectos, metas, personas clave, "
                "métodos de trabajo y visión de vida del usuario"
            ),
        )
        if project_id:
            await guardar_mirofish_estado(telefono, project_id=project_id, graph_id=graph_id)
            logger.info(f"MiroFish onboarding: grafo actualizado para {telefono}")
    except Exception as e:
        logger.error(f"MiroFish _construir_grafo_onboarding error ({telefono}): {e}")
