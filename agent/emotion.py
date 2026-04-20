# agent/emotion.py — Inteligencia emocional de Dona
# Dona

"""
Detecta el estado emocional del usuario en cada mensaje y adapta el tono de Dona.

Estados detectados:
  stress       — Estrés / sobrecarga
  frustration  — Frustración con personas o situaciones
  exhaustion   — Agotamiento físico o mental
  celebration  — Logro o celebración
  anxiety      — Ansiedad o incertidumbre
  crisis       — Señales de crisis emocional seria (manejo especial)
  neutral      — Estado productivo / sin carga emocional notable

La detección usa Claude Haiku (rápido y barato). Si falla, retorna "neutral"
para no bloquear la respuesta principal.
"""

import os
import json
import logging
from anthropic import AsyncAnthropic
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger("agentkit")

_claude = AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

# Palabras que indican posible crisis — manejo especial independientemente del LLM
_PALABRAS_CRISIS = {
    "no quiero seguir", "no tiene sentido", "para qué seguir",
    "quiero desaparecer", "no puedo más con la vida", "me quiero morir",
    "ya no aguanto", "no vale la pena vivir",
}

MENSAJE_CRISIS = (
    "Gracias por contarme esto. Lo que sientes es válido y merece atención real. 💙\n\n"
    "Por favor habla con alguien de confianza ahora — un amigo, familiar, o un profesional. "
    "En México puedes llamar a SAPTEL: 55 5259-8121 (24 horas). "
    "No tienes que pasar por esto solo/sola."
)


# ─── DETECCIÓN ───────────────────────────────────────────────────────────────

async def detectar_emocion(mensaje: str, contexto_usuario: str = "") -> dict:
    """
    Detecta el estado emocional del usuario.

    Retorna dict con:
        state: str            — stress|frustration|exhaustion|celebration|anxiety|crisis|neutral
        intensity: int        — 1 (leve), 2 (moderado), 3 (intenso)
        needs_validation: bool — True si Dona debe validar antes de resolver
        contexto: str         — explicación breve
    """
    # Check rápido de crisis (sin llamar al LLM)
    if _es_crisis(mensaje):
        return {
            "state": "crisis",
            "intensity": 3,
            "needs_validation": True,
            "contexto": "Señales de crisis emocional detectadas"
        }

    try:
        ctx = f"\nContexto del usuario: {contexto_usuario[:200]}" if contexto_usuario else ""
        prompt = (
            f"Analiza el estado emocional de este mensaje de WhatsApp en español.{ctx}\n\n"
            f'Mensaje: "{mensaje}"\n\n'
            f"Responde SOLO con este JSON exacto (sin texto adicional):\n"
            f'{{"state":"<stress|frustration|exhaustion|celebration|anxiety|neutral>",'
            f'"intensity":<1|2|3>,"needs_validation":<true|false>,'
            f'"contexto":"<frase corta>"}}\n\n'
            f"Reglas:\n"
            f"- intensity: 1=leve, 2=moderado, 3=intenso\n"
            f"- needs_validation: true cuando necesita ser escuchado antes de recibir soluciones\n"
            f"- Ante la duda, usa neutral\n"
            f"- No sobreinterpretes mensajes cortos o ambiguos"
        )

        from agent.llm import completar_texto
        texto = await completar_texto(prompt, max_tokens=80)
        if not texto:
            raise ValueError("LLM no respondió")
        # Extraer solo el JSON si hay texto extra alrededor
        inicio = texto.find("{")
        fin = texto.rfind("}") + 1
        if inicio >= 0 and fin > inicio:
            texto = texto[inicio:fin]

        resultado = json.loads(texto)
        # Validar campos mínimos
        if "state" not in resultado:
            raise ValueError("state faltante")
        return resultado

    except Exception as e:
        logger.debug(f"Emotion detector fallback a neutral: {e}")
        return {"state": "neutral", "intensity": 1, "needs_validation": False, "contexto": ""}


def _es_crisis(mensaje: str) -> bool:
    """Detección rápida de crisis por palabras clave — sin LLM."""
    msg_lower = mensaje.lower()
    return any(kw in msg_lower for kw in _PALABRAS_CRISIS)


# ─── INSTRUCCIONES DE TONO ───────────────────────────────────────────────────

def obtener_instrucciones_tono(emotion: dict, nombre: str) -> str:
    """
    Genera las instrucciones de tono para Claude basadas en el estado emocional.
    Se inyectan en el system prompt de cada respuesta.
    """
    state = emotion.get("state", "neutral")
    intensity = emotion.get("intensity", 1)
    needs_validation = emotion.get("needs_validation", False)

    instrucciones = {
        "stress": (
            f"{nombre} está estresado/a (intensidad {intensity}/3). "
            "PRIMERO valida su sentimiento con una frase de empatía genuina — NO empieces con soluciones ni listas. "
            "Luego ayuda a priorizar UNA sola cosa, no todo a la vez. "
            "Tono: calmado, contenedor, sin urgencia adicional. Máximo 2 párrafos cortos."
        ),
        "frustration": (
            f"{nombre} está frustrado/a (intensidad {intensity}/3). "
            "Reconoce la frustración en una frase corta y luego ofrece UNA acción concreta. "
            "No minimices el problema. No digas 'entiendo' vacíamente — muestra que lo entiendes. "
            "Tono: empático pero orientado a la acción."
        ),
        "exhaustion": (
            f"{nombre} está agotado/a (intensidad {intensity}/3). "
            "No agregues más tareas ni responsabilidades. "
            "Si parece tarde o lleva muchas horas, sugiere descanso con suavidad. "
            "Si insiste en trabajar, ayúdalo/a brevemente y sin presión. "
            "Tono: suave, cuidadoso, sin exigencias."
        ),
        "celebration": (
            f"{nombre} está celebrando un logro. "
            "Celebra genuinamente y con entusiasmo — no seas genérico/a. "
            "Menciona el logro específico. Luego pregunta por el siguiente paso o deja disfrutar el momento. "
            "Tono: alegre, cálido, energético."
        ),
        "anxiety": (
            f"{nombre} está ansioso/a o inseguro/a (intensidad {intensity}/3). "
            "PRIMERO contén la ansiedad — valida que es normal sentirse así. "
            "Luego estructura opciones claras y concretas. La claridad reduce la ansiedad. "
            "Tono: tranquilizador, estructurado, sin dramatizar."
        ),
        "crisis": (
            "ALERTA: el usuario puede estar en una crisis emocional seria. "
            "Responde SOLO con el mensaje de crisis — no intentes resolver ninguna tarea. "
            "Tono: profundamente empático, sin minimizar, sugiere ayuda profesional."
        ),
        "neutral": (
            f"{nombre} está en modo productivo. "
            "Responde de forma eficiente y directa. Sin drama emocional innecesario. "
            "Tono: profesional, claro, orientado a la acción."
        ),
    }

    base = instrucciones.get(state, instrucciones["neutral"])

    if needs_validation and state not in ("neutral", "celebration", "crisis"):
        base += (
            "\n\nIMPORTANTE: El usuario necesita ser escuchado ANTES de recibir soluciones. "
            "Empieza siempre validando su experiencia en la primera frase."
        )

    return base


# ─── CONTEXTO EMOCIONAL RECIENTE ─────────────────────────────────────────────

def obtener_contexto_emocional_str(estado_actual: str, intensidad: int, actualizado) -> str:
    """
    Retorna una línea de contexto emocional para el system prompt.
    Solo si el estado es reciente (últimas 2 horas) y no es neutral.
    """
    from datetime import datetime, timedelta

    if estado_actual == "neutral" or not actualizado:
        return ""

    hace_dos_horas = datetime.utcnow() - timedelta(hours=2)
    if actualizado < hace_dos_horas:
        return ""

    return f"[Estado emocional reciente del usuario: {estado_actual} (intensidad {intensidad}/3)]"
