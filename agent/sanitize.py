# agent/sanitize.py — Sanitización de datos externos (anti prompt injection)

"""
Saneo de texto proveniente de fuentes externas (Calendar, Sheets, Gmail,
Google Tasks, memoria) antes de inyectarlo como resultado de herramienta al
contexto del LLM.

Extraído de `agent/brain.py` (Fase 2 · Bloque 1) SIN cambios de comportamiento:
mismos patrones, mismo anti-breakout, mismo wrapper con nonce, mismo truncado.
Vive fuera de `brain` para que los handlers de tools —que no deben depender de
`brain`— puedan reutilizarlo. `brain` lo re-importa con alias
`_sanitizar_datos_externos` para no tocar sus call sites existentes.
"""

import logging
import re
import secrets

logger = logging.getLogger("dona")

# Patrones que indican intento de inyección de instrucciones en datos externos.
_PATRONES_INYECCION = re.compile(
    r"(?i)"
    r"(?:ignora|ignore|olvida|forget|override|overwrite)\s+"
    r"(?:todas?\s+las?\s+)?(?:instrucciones?|instructions?|reglas?|rules?|prompt)"
    r"|(?:eres\s+ahora|you\s+are\s+now|act\s+as|actúa\s+como|nuevo\s+rol)"
    r"|(?:system\s*prompt|system\s*message|<\s*system)"
    r"|(?:envía?\s+(?:un\s+)?mensaje\s+a|send\s+(?:a\s+)?message\s+to)"
    r"|(?:revela|reveal|muestra|show)\s+(?:tu\s+)?(?:prompt|instrucciones|api\s*key|token)"
)

# Cualquier forma del delimitador `external_data` que aparezca DENTRO del
# contenido externo es un intento de fuga del sandbox: el atacante quiere
# cerrar el bloque (`</external_data>`) o abrir uno falso para que su texto
# parezca instrucción de confianza "fuera" de los datos. Cubre variantes de
# espaciado, mayúsculas, atributos y cierres colgantes sin `>`.
_RE_DELIMITADOR_FUGA = re.compile(r"(?i)<\s*/?\s*external_data\b[^>\n]*>?")


def sanitizar_datos_externos(texto: str, max_chars: int = 4000) -> str:
    """
    Sanitiza texto proveniente de fuentes externas (Calendar, Sheets, Gmail, memoria)
    antes de inyectarlo como resultado de herramienta en el contexto de Claude.

    - Trunca a max_chars para evitar saturación de contexto
    - Marca intentos de inyección detectados como [contenido filtrado]
    - Neutraliza cualquier delimitador `external_data` inyectado (anti-breakout)
    - Envuelve en un delimitador con NONCE aleatorio por invocación, de modo que
      el cierre sea impredecible y no forjable desde el contenido (Fable5 · 5.5)
    """
    if not texto:
        return texto
    texto = texto[:max_chars]
    # Si se detecta un patrón de inyección, marcar la línea afectada
    lineas = texto.split("\n")
    lineas_limpias = []
    for linea in lineas:
        if _PATRONES_INYECCION.search(linea):
            logger.warning(f"[SECURITY] Posible prompt injection detectado y filtrado: {linea[:120]}")
            lineas_limpias.append("[contenido filtrado por seguridad]")
        else:
            lineas_limpias.append(linea)
    contenido = "\n".join(lineas_limpias)
    # Anti-breakout: remover delimitadores `external_data` inyectados en el
    # contenido. Sin esto, un `</external_data>` en un título de evento o cuerpo
    # de correo cierra el sandbox y el texto siguiente se lee como instrucción.
    if _RE_DELIMITADOR_FUGA.search(contenido):
        logger.warning("[SECURITY] Intento de fuga del delimitador external_data neutralizado")
        contenido = _RE_DELIMITADOR_FUGA.sub("[delimitador removido]", contenido)
    # Nonce por invocación: el delimitador de cierre lleva un token aleatorio
    # que el atacante no puede predecir, por lo que no puede forjar un cierre
    # válido aunque conozca el formato del wrapper.
    nonce = secrets.token_hex(8)
    return f'<external_data nonce="{nonce}">\n{contenido}\n</external_data nonce="{nonce}">'
