# agent/entorno.py — Helper único de entorno (Fase 0 · fail-closed por defecto)

"""
Punto único de verdad para decidir si el proceso corre en un entorno
permisivo (dev/test) o estricto (producción o desconocido).

Antes de Fase 0, cada módulo comparaba ``ENVIRONMENT == "production"`` para
activar sus controles de seguridad. Eso es fail-open: un typo ("prod",
"Production "), la variable ausente o un valor nuevo (staging) desactivaban
EN SILENCIO la verificación de firmas de Stripe/Meta/Whapi, el cifrado de
tokens, los secrets de inbound y el state de OAuth (hallazgo C8 del audit
de readiness 2026-06-09).

La lógica se invierte aquí: SOLO ``development`` y ``test`` explícitos
habilitan los paths permisivos. Cualquier otro valor —incluido vacío o
typo— se trata como producción (fail-closed).

``ENVIRONMENT`` se lee en cada llamada (no se cachea) para facilitar tests
con ``monkeypatch.setenv`` — mismo patrón que el resto del repo.
"""

import os

# Únicos valores que habilitan paths permisivos (warning en vez de rechazo).
ENTORNOS_PERMISIVOS = ("development", "test")


def entorno_actual() -> str:
    """``ENVIRONMENT`` normalizado (trim + lower). Vacío si no está configurada."""
    return os.getenv("ENVIRONMENT", "").strip().lower()


def es_entorno_permisivo() -> bool:
    """True SOLO si ``ENVIRONMENT`` es explícitamente development o test."""
    return entorno_actual() in ENTORNOS_PERMISIVOS


def es_entorno_estricto() -> bool:
    """True si el entorno exige controles de producción (fail-closed).

    Producción, valor desconocido, typo o variable ausente → estricto.
    """
    return not es_entorno_permisivo()
