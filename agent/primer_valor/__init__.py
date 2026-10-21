"""Primer resultado en 5 minutos (F12).

Lleva el onboarding por fases (ya existente, `usuario_onboarding`) a terminar en
un resultado tangible: un borrador de seguimiento (camino por defecto, sin
proveedor facturable) o una imagen. Siembra créditos de bienvenida una sola vez
(idempotente), mide el time-to-first-value (TTFV) y no expone /admin.

"5 minutos" es una META a medir con usuarios reales, no un hecho validado aquí.

Flag DONA_FIRST_VALUE_ONBOARDING_ENABLED=false por defecto.
"""
