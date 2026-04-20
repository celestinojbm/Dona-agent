# tests/test_local.py — Simulador de chat con Dona en terminal
# Dona

"""
Prueba a Dona sin necesitar WhatsApp.
Simula una conversación en la terminal.
"""

import asyncio
import sys
import os

# Forzar UTF-8 en la terminal de Windows para soportar emojis
if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")
if sys.stdin.encoding != "utf-8":
    sys.stdin.reconfigure(encoding="utf-8")

# Agregar el directorio raíz al path para importar los módulos del agente
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent.brain import generar_respuesta
from agent.memory import inicializar_db, guardar_mensaje, obtener_historial, limpiar_historial

TELEFONO_TEST = "test-local-001"


async def main():
    """Loop principal del chat de prueba."""
    await inicializar_db()

    print()
    print("=" * 55)
    print("   Dona — Asistente Personal · Test Local")
    print("=" * 55)
    print()
    print("  Escribe mensajes como si fueras un usuario.")
    print("  Comandos especiales:")
    print("    'limpiar'  — borra el historial de la sesión")
    print("    'salir'    — termina el test")
    print()
    print("-" * 55)
    print()

    while True:
        try:
            mensaje = input("Tú: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n\nTest finalizado.")
            break

        if not mensaje:
            continue

        if mensaje.lower() == "salir":
            print("\nTest finalizado.")
            break

        if mensaje.lower() == "limpiar":
            await limpiar_historial(TELEFONO_TEST)
            print("[Historial borrado]\n")
            continue

        # Obtener historial ANTES de guardar (brain.py agrega el mensaje actual)
        historial = await obtener_historial(TELEFONO_TEST)

        # Generar respuesta con Claude
        print("\nDona: ", end="", flush=True)
        respuesta = await generar_respuesta(mensaje, historial)
        print(respuesta)
        print()

        # Guardar mensaje del usuario y respuesta de Dona
        await guardar_mensaje(TELEFONO_TEST, "user", mensaje)
        await guardar_mensaje(TELEFONO_TEST, "assistant", respuesta)


if __name__ == "__main__":
    asyncio.run(main())
