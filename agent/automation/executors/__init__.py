# agent/automation/executors/__init__.py — T2.2

"""
Submódulo con ejecutores de acciones HIGH que requieren guardrails
reforzados (aprobación humana, idempotencia anti doble envío, cobro
seguro y mock-ability en tests).

Cada ejecutor HIGH vive en su propio archivo y exporta:
  - una función _ejecutor_X (firma compatible con EJECUTORES_T21A)
  - opcionalmente funciones de orquestación preparar/confirmar
"""
