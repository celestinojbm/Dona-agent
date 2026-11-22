"""Memoria de intenciones mencionadas una sola vez (F28 · subsección aprobada).

Qué hace: detecta en un mensaje del usuario algo que dijo de pasada («tengo que
renovar el dominio en noviembre») y lo devuelve como *propuesta*: un chip
«¿Lo recuerdo?» con la frase de origen. Solo si el usuario acepta el chip se
convierte en una `Intencion` con vencimiento de 30 días.

Qué NO hace (invariantes del roadmap, sección F28):

- **No ejecuta ni autoriza nada.** Una intención no es una autorización: no
  tiene campo de permiso, no importa `agent.autonomia` ni `agent.automation` y
  no puede subir el nivel L1–L4. Actuar sobre ella sigue el flujo de F1
  (preparar → confirmar).
- **No persiste.** No escribe en BD ni en memoria vectorial. Guardar y mostrar
  la intención en la pantalla Memoria de la app es un PR aparte.
- **No guarda datos sensibles.** Salud, credenciales y datos de pago se
  rechazan antes de proponer y otra vez al aceptar. El filtro es una lista
  negra conservadora: lo que no reconoce, pasa. Lo que sí es fail-closed es el
  manejo de errores: si el filtro falla o recibe algo que no es texto, se trata
  como sensible y no se guarda nada.
- **Apagado por agente por defecto.** `agente_habilitado` vale `False` salvo
  que se pase `True` literal: olvidar el argumento al cablear no enciende nada.
- **No envía.** WhatsApp solo avisaría o pediría aprobación (F35); este módulo
  no llama a ningún canal.

No está cableado a `main.py` ni al cerebro. Flag
`DONA_MEMORIA_INTENCIONES_ENABLED` apagado por defecto; se lee en cada llamada,
sin cachear, para que `monkeypatch.setenv` funcione en tests.
"""

from __future__ import annotations

import logging
import os
import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

_ENV_FLAG = "DONA_MEMORIA_INTENCIONES_ENABLED"
# Igual que agent/efectos.py y agent/canales: `1`/`true`/`yes`/`on`, sin
# distinguir mayúsculas (tras strip). Ausente, vacío u otro valor → apagado.
_VERDADEROS = frozenset({"true", "1", "yes", "on"})

DIAS_VIGENCIA = 30
PREGUNTA_CHIP = "¿Lo recuerdo?"
LARGO_MAXIMO_FRASE = 300
LARGO_MAXIMO_TEXTO = 160
# Menos que esto tras el disparador («tengo que ir») no es una intención útil.
_LARGO_MINIMO_TEXTO = 6
_ELIPSIS = "…"

RAZON_FLAG_APAGADO = "flag_apagado"
RAZON_AGENTE_APAGADO = "agente_apagado"
RAZON_SIN_INTENCION = "sin_intencion"
RAZON_DATO_SENSIBLE = "dato_sensible"
RAZON_ERROR = "error_evaluacion"
RAZON_PROPUESTA = "propuesta"

# Disparadores sobre texto normalizado (minúsculas, sin acentos). «necesito» no
# entra: casi siempre es un pedido para ahora («necesito un logo»), no una
# intención a futuro.
_DISPARADOR = re.compile(
    r"\b(?:tengo|tenemos) (?:que|pendiente)\s+"
    r"|\b(?:debo|debemos)\s+"
    r"|\bhay que\s+"
    r"|\b(?:me|nos) toca\s+"
    r"|\bno se me (?:puede |debe )?olvid(?:ar|e)\s+(?:de\s+)?"
)
# «no tengo que…», «ya no debo…»: negación inmediatamente antes del disparador.
_NEGACION_PREVIA = re.compile(r"\b(?:no|nunca|ya no)\s*$")
# Recordatorio explícito: lo resuelve `reminders_nl` de forma determinista.
_RECORDATORIO_EXPLICITO = re.compile(r"\b(?:recuerdame|recordame|recordarme|recordatorio)\b")
# Fin de frase: signo seguido de espacio o del final, o salto de línea. Así el
# «.» de un dominio o el «?» de una query string no parten la frase (si no,
# `usadona.com/login?t=…` dejaría el token fuera del filtro de sensibles).
_FIN_DE_FRASE = re.compile(r"[.!?;]+(?=\s|$)|\n+")
_ESPACIOS = re.compile(r"\s+")

# ── Datos sensibles (texto normalizado). Lista negra: lo que no está, pasa. ──
_SALUD = re.compile(
    r"\b(?:medic[oa]s?|doctor[ae]?s?|dr[ae]?|hospital\w*|clinica\w*|salud|enfermedad\w*"
    r"|medicamento\w*|medicina\w*|pastilla\w*|receta medica|diagnostic\w*|tratamiento\w*"
    r"|terapia\w*|terapeuta\w*|psicolog\w*|psiquiatr\w*|embaraz\w*|vih|cancer|diabet\w*"
    r"|analisis de sangre|laboratorio clinico|dentista\w*|ginecolog\w*|vacuna\w*|cirugia\w*)\b"
)
_CREDENCIALES = re.compile(
    r"\b(?:contrasena\w*|password\w*|passcode|clave\w*|pin|nip|token\w*|otp|2fa"
    r"|codigo de (?:verificacion|seguridad|acceso)|api ?key|usuario y contrasena|credencial\w*)\b"
    # Tokens en query string de un enlace (`?t=…`, `&token=…`).
    r"|[?&][\w.-]+="
)
_PAGO = re.compile(
    r"\b(?:cvv|cvc|numero de (?:tarjeta|cuenta)|cuenta bancaria|routing|iban|swift|clabe"
    r"|ssn|social security|seguro social)\b"
    # 12-19 dígitos seguidos o separados por espacio/guion: forma de tarjeta o cuenta.
    r"|(?<!\d)(?:\d[ -]?){11,18}\d(?!\d)"
)
_SENSIBLES = (_SALUD, _CREDENCIALES, _PAGO)


@dataclass(frozen=True)
class PropuestaIntencion:
    """Chip «¿Lo recuerdo?». No se guarda: si el usuario no lo acepta, se pierde."""

    texto: str
    frase_origen: str
    pregunta: str = PREGUNTA_CHIP


@dataclass(frozen=True)
class DecisionIntencion:
    """Resultado de evaluar un mensaje. `razon` es un código estable."""

    propuesta: PropuestaIntencion | None
    razon: str


@dataclass(frozen=True)
class Intencion:
    """Intención aceptada por el usuario. Vence a los `DIAS_VIGENCIA` días.

    Sin campo de autorización a propósito: nada en este objeto permite ejecutar.
    """

    texto: str
    frase_origen: str
    creada_en: datetime
    vence_en: datetime


def flag_intenciones_activo() -> bool:
    """True solo si DONA_MEMORIA_INTENCIONES_ENABLED es `true`/`1`/`yes`/`on`."""
    return os.getenv(_ENV_FLAG, "").strip().lower() in _VERDADEROS


def _normalizar(texto: str) -> str:
    """Minúsculas y sin acentos, conservando la longitud (índices alineados)."""
    # Carácter a carácter y quedándose con el primero de la descomposición: «é»
    # → «e», «ñ» → «n», «İ» → «i». Así los índices del texto normalizado sirven
    # para cortar el original.
    return "".join(unicodedata.normalize("NFKD", c.lower())[0] for c in texto)


def _recortar(texto: str, maximo: int) -> str:
    if len(texto) <= maximo:
        return texto
    return texto[: maximo - len(_ELIPSIS)].rstrip() + _ELIPSIS


def _una_linea(texto: str) -> str:
    return _ESPACIOS.sub(" ", texto).strip()


def es_sensible(texto: str) -> bool:
    """True si el texto trae salud, credenciales o datos de pago.

    Fail-closed ante error: si `texto` no es `str` o el filtro lanza una
    excepción, devuelve True. Así quien llama descarta la intención en vez de
    guardarla sin haberla revisado.
    """
    if not isinstance(texto, str):
        return True
    try:
        normalizado = _normalizar(texto)
        return any(patron.search(normalizado) for patron in _SENSIBLES)
    except Exception as exc:  # noqa: BLE001 — cualquier fallo cuenta como sensible
        # Solo el tipo de error: el texto puede traer justo el dato sensible.
        logger.warning(
            "intenciones: filtro de sensibles falló (%s); se descarta", type(exc).__name__
        )
        return True


def _frases(texto: str) -> list[tuple[str, bool]]:
    """Parte en frases; marca las que terminan en «?» (preguntas a Dona)."""
    resultado: list[tuple[str, bool]] = []
    inicio = 0
    for fin in _FIN_DE_FRASE.finditer(texto):
        resultado.append((texto[inicio : fin.start()], "?" in fin.group()))
        inicio = fin.end()
    resultado.append((texto[inicio:], False))
    return [(f, pregunta) for f, pregunta in resultado if f.strip()]


def _extraer(frase: str) -> str | None:
    """Devuelve lo que sigue al disparador, o None si la frase no es intención."""
    normalizada = _normalizar(frase)
    if _RECORDATORIO_EXPLICITO.search(normalizada):
        return None
    for coincidencia in _DISPARADOR.finditer(normalizada):
        if _NEGACION_PREVIA.search(normalizada[: coincidencia.start()]):
            continue
        texto = _una_linea(frase[coincidencia.end() :]).rstrip(" ,:")
        if len(texto) >= _LARGO_MINIMO_TEXTO:
            return texto
    return None


def evaluar_mensaje(
    texto: str, *, flag: bool | None = None, agente_habilitado: bool = False
) -> DecisionIntencion:
    """Evalúa un mensaje del usuario y, si procede, propone recordar una intención.

    - `flag=None` lee `DONA_MEMORIA_INTENCIONES_ENABLED`; `True`/`False`
      explícito ignora el entorno. Apagado → nunca propone.
    - `agente_habilitado` es `False` por defecto: la función queda apagada
      para el agente salvo que se pase `True` literal (un valor «truthy» como
      `"false"` o `1` no la enciende).
    - Devuelve la primera intención no sensible del mensaje; las preguntas
      («¿tengo que pagar?») y los recordatorios explícitos no cuentan.
    - Si una frase con intención trae un dato sensible, se rechaza el mensaje
      completo (`dato_sensible`) en vez de buscar otra frase.
    - Cualquier error durante la evaluación devuelve `error_evaluacion` sin
      propuesta: ante error, no se propone ni se guarda nada.
    """
    activo = flag_intenciones_activo() if flag is None else bool(flag)
    if not activo:
        return DecisionIntencion(None, RAZON_FLAG_APAGADO)
    if agente_habilitado is not True:
        return DecisionIntencion(None, RAZON_AGENTE_APAGADO)
    if not isinstance(texto, str) or not texto.strip():
        return DecisionIntencion(None, RAZON_SIN_INTENCION)
    try:
        return _evaluar_texto(texto)
    except Exception as exc:  # noqa: BLE001 — fail-closed: ante error, nada
        logger.warning(
            "intenciones: error al evaluar mensaje (%s); sin propuesta", type(exc).__name__
        )
        return DecisionIntencion(None, RAZON_ERROR)


def _evaluar_texto(texto: str) -> DecisionIntencion:
    for frase, es_pregunta in _frases(texto):
        if es_pregunta:
            continue
        extraido = _extraer(frase)
        if extraido is None:
            continue
        if es_sensible(frase):
            return DecisionIntencion(None, RAZON_DATO_SENSIBLE)
        propuesta = PropuestaIntencion(
            texto=_recortar(extraido, LARGO_MAXIMO_TEXTO),
            frase_origen=_recortar(_una_linea(frase), LARGO_MAXIMO_FRASE),
        )
        return DecisionIntencion(propuesta, RAZON_PROPUESTA)
    return DecisionIntencion(None, RAZON_SIN_INTENCION)


def _exigir_zona_horaria(ahora: datetime) -> None:
    if not isinstance(ahora, datetime) or ahora.tzinfo is None or ahora.utcoffset() is None:
        raise ValueError("`ahora` debe ser un datetime con zona horaria")


def aceptar_propuesta(propuesta: PropuestaIntencion, *, ahora: datetime) -> Intencion:
    """El usuario aceptó el chip: crea la intención con vencimiento de 30 días.

    Revalida que no sea sensible (la propuesta pudo construirse a mano). Si el
    filtro falla, `es_sensible` devuelve True y la intención no se crea.
    """
    if not isinstance(propuesta, PropuestaIntencion):
        raise TypeError("se esperaba una PropuestaIntencion")
    _exigir_zona_horaria(ahora)
    if es_sensible(propuesta.texto) or es_sensible(propuesta.frase_origen):
        raise ValueError("la intención contiene datos sensibles y no se guarda")
    if len(propuesta.texto.strip()) < _LARGO_MINIMO_TEXTO:
        raise ValueError("la intención está vacía")
    return Intencion(
        texto=propuesta.texto,
        frase_origen=propuesta.frase_origen,
        creada_en=ahora,
        vence_en=ahora + timedelta(days=DIAS_VIGENCIA),
    )


def esta_vigente(intencion: Intencion, *, ahora: datetime) -> bool:
    """True mientras no haya llegado `vence_en`. Vencida → no se sugiere más."""
    _exigir_zona_horaria(ahora)
    return ahora < intencion.vence_en


def redactar_sugerencia(intencion: Intencion) -> str:
    """Copy para la app. Deja claro que nada se ejecuta sin confirmación."""
    return (
        f"Me dijiste: «{intencion.frase_origen}». "
        "¿Preparo algo para eso? No hago nada sin tu confirmación."
    )
