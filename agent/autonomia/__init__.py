"""Autonomía por tipo de acción (F1).

Capa determinística sobre el patrón preparar_X/confirmar_X: un evaluador de
política decide si una acción requiere confirmación humana o puede
autoautorizarse según el nivel (L1–L4) configurado por el usuario. El modelo
sólo propone; nunca se concede permisos a sí mismo. `confirmar_X` exige una
autorización PERSISTIDA (humana o de política) verificable: usuario, acción y
argumentos (hash), cotización/versiones, alcance, vencimiento y uso único.

Flag DONA_AUTONOMY_ENABLED=false por defecto → todo exige confirmación humana.
"""
