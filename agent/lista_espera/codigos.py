"""Códigos de invitación con entropía mínima (issue #334).

Problema que resuelve: antes bastaba con 8 caracteres cualesquiera, así que
``DONA2026`` era un código "válido". Con el límite global de canje (~4800
intentos al día) un código así cae en horas; uno aleatorio de 80 bits no cae
nunca.

Formato: Crockford base32 (0-9 y A-Z sin I, L, O, U), 16 símbolos aleatorios
= 80 bits, mostrados en grupos de 4: ``7KQ2-M9XW-4HTB-RZ8D``. Al comparar se
ignoran guiones, espacios y mayúsculas, y se aceptan O→0 e I/L→1 (lo que un
humano confunde al copiar).

Qué se garantiza y qué no:
  - Un código configurado en DONA_CODIGOS_INVITACION que no cumple el formato
    o que tiene un patrón humano evidente (pocos símbolos distintos, rachas,
    secuencias, bloques repetidos) NO vale nunca: fail-closed, con un error en
    el log que dice su posición (nunca el código).
  - Un string de 16 símbolos "con pinta aleatoria" elegido a mano pasaría el
    filtro. La entropía real solo la garantiza generar los códigos con:

        python -m agent.lista_espera.codigos 5
"""

from __future__ import annotations

import functools
import logging
import secrets
import sys

logger = logging.getLogger("dona")

ALFABETO = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
BITS_POR_SIMBOLO = 5  # log2(32)
LARGO_CODIGO = 16
ENTROPIA_MINIMA_BITS = LARGO_CODIGO * BITS_POR_SIMBOLO  # 80
_LARGO_MAXIMO = 32
_MIN_SIMBOLOS_DISTINTOS = 8
_MAX_RACHA = 3  # 4 iguales o 4 consecutivos del alfabeto seguidos → débil

_EQUIVALENCIAS = str.maketrans({"O": "0", "I": "1", "L": "1"})
_SEPARADORES = str.maketrans("", "", "- \t")
_POSICION = {c: i for i, c in enumerate(ALFABETO)}


def normalizar(codigo: str) -> str:
    """Mayúsculas, sin separadores y con O→0, I/L→1. No valida."""
    return (codigo or "").upper().translate(_SEPARADORES).translate(_EQUIVALENCIAS)


def motivo_debil(codigo_normalizado: str) -> str | None:
    """None si el código cumple el mínimo; si no, el motivo (sin el código)."""
    c = codigo_normalizado
    if not LARGO_CODIGO <= len(c) <= _LARGO_MAXIMO:
        return f"largo {len(c)} fuera de {LARGO_CODIGO}-{_LARGO_MAXIMO} símbolos"
    if any(s not in _POSICION for s in c):
        return "símbolos fuera del alfabeto Crockford base32"
    if len(set(c)) < _MIN_SIMBOLOS_DISTINTOS:
        return f"menos de {_MIN_SIMBOLOS_DISTINTOS} símbolos distintos"
    pos = [_POSICION[s] for s in c]
    for paso in (0, 1, -1):  # misma letra, secuencia ascendente, descendente
        racha = 1
        for a, b in zip(pos, pos[1:], strict=False):
            racha = racha + 1 if b - a == paso else 1
            if racha > _MAX_RACHA:
                return "racha o secuencia de 4 símbolos"
    for periodo in range(1, len(c) // 2 + 1):
        if all(c[i] == c[i + periodo] for i in range(len(c) - periodo)):
            return "bloque repetido"
    return None


def generar() -> str:
    """Código nuevo de 80 bits (``secrets``), agrupado de 4 en 4."""
    while True:
        c = "".join(secrets.choice(ALFABETO) for _ in range(LARGO_CODIGO))
        # Un aleatorio cae en el filtro de patrones ~1 vez de cada 1000: se
        # descarta y se genera otro (pierde una fracción de bit, no importa).
        if motivo_debil(c) is None:
            return "-".join(c[i : i + 4] for i in range(0, LARGO_CODIGO, 4))


@functools.lru_cache(maxsize=4)
def cargar(crudo: str) -> tuple[str, ...]:
    """Códigos válidos de DONA_CODIGOS_INVITACION, ya normalizados.

    Los débiles se descartan con un error en el log. Cacheado por el valor
    crudo de la variable: el log sale una vez por configuración, no por canje.
    """
    validos: list[str] = []
    for posicion, entrada in enumerate(crudo.split(","), start=1):
        if not entrada.strip():
            continue
        c = normalizar(entrada)
        motivo = motivo_debil(c)
        if motivo:
            logger.error(
                f"[LISTA-ESPERA] DONA_CODIGOS_INVITACION: el código #{posicion} se "
                f"ignora ({motivo}). Genera códigos con "
                "`python -m agent.lista_espera.codigos`."
            )
            continue
        validos.append(c)
    return tuple(validos)


if __name__ == "__main__":  # pragma: no cover - utilidad de consola
    cantidad = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    print(",".join(generar() for _ in range(cantidad)))
