"""Selector y combinación de modelos (F23).

Permite elegir modelo (Claude, GPT, Gemini, …) por chat y por agente, cambiar de
modelo a mitad de conversación sin perder contexto (el historial es
model-agnostic), un modo Auto que elige por tarea y coste, combinar modelos
(uno planifica / otro ejecuta, o comparar dos lado a lado) y sugerencias (chips
de respuestas, siguientes acciones y modelo recomendado).

Principios:
- Capa de proveedores con interfaz común; las claves viven SÓLO en variables de
  entorno del backend (nunca en código ni en el front).
- Precios por modelo configurables (tabla base + override por env).
- Sin llamadas reales de pago: las pruebas usan un proveedor simulado. El flag
  DONA_MULTI_MODEL_ENABLED está apagado por defecto.

Dona es app-first; esto vive en la app (WhatsApp es secundario).
"""
