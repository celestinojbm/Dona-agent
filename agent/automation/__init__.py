# agent/automation/__init__.py — Dona Automation Core (T2.1.A)

"""
Sistema fundacional de automatización autorizada.

Pipeline:
    diagnóstico → oportunidades → playbooks → acciones →
    permisos → ejecución controlada → audit log → resultados

Todos los efectos externos pasan por este sistema. T2.1.A entrega solo
la base: ejecutores internos (dry-run / generación de texto). Acciones
con efecto externo real (enviar WhatsApp, publicar, gastar dinero) se
clasifican como medium/high/critical y NO se ejecutan automáticamente
en este PR · requieren aprobación explícita y solo entonces el ejecutor
real las procesa (futuros PRs T2.1.C).

Submódulos:
    permissions   — clasificación de riesgo + reglas de auto-ejecución
    opportunities — Opportunity Engine (perfil → oportunidades)
    playbooks     — catálogo de playbooks
    costos        — estimación de créditos por playbook
    audit         — audit log fundacional sin PII
    execution     — interfaz de ejecutores · solo dry-run en T2.1.A
    action_center — CRUD de acciones (crear, listar, aprobar, etc.)
    models        — tablas SQLAlchemy + MIGRACIONES_AUTOMATION
"""
