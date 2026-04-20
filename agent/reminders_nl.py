# agent/reminders_nl.py — Parser de recordatorios en lenguaje natural (español)

"""
Convierte frases tipo "recuérdame mañana 9am que llame a Juan" en
`(fecha_hora_utc, mensaje)` listo para `guardar_recordatorio`.

Alcance intencional:
  - SOLO patrones comunes. No intenta reemplazar un parser NL completo.
  - Todas las fechas se resuelven asumiendo la timezone del usuario
    (offset en minutos) que el caller debe proveer.

Patrones soportados:
  - "recuérdame en N (minutos|horas|días) <msg>"
  - "recuérdame (hoy|mañana|pasado mañana) <a las HH[am|pm]> <msg>"
  - "recuérdame el <D> de <mes> <a las HH[am|pm]> <msg>"

Devuelve None si no puede parsear con confianza — el caller debe caer
al flujo de LLM normal.
"""

import re
from datetime import datetime, timedelta, timezone


_MESES = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6,
    "julio": 7, "agosto": 8, "septiembre": 9, "setiembre": 9,
    "octubre": 10, "noviembre": 11, "diciembre": 12,
}

# "recuérdame" / "recuerdame" / "recordame" / "dona recuérdame"
_PREFIJO = re.compile(
    r"^\s*(?:dona\s+)?(?:recuerdame|recuérdame|recordame)\s+",
    re.IGNORECASE,
)

# "en 5 minutos" / "en 2 horas" / "en 3 días"
_RE_EN = re.compile(
    r"^en\s+(\d{1,3})\s+(minutos?|horas?|dias?|días?)\s+(?:que\s+)?(.+)$",
    re.IGNORECASE,
)

# "mañana 9am que ...", "hoy a las 6pm que ..."
_RE_DIA_HORA = re.compile(
    r"^(hoy|mañana|manana|pasado\s+mañana|pasado\s+manana)"
    r"(?:\s+a\s+las)?\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?"
    r"\s*(?:que\s+)?(.+)$",
    re.IGNORECASE,
)

# "el 15 de marzo a las 10am que ..."
_RE_FECHA = re.compile(
    r"^el\s+(\d{1,2})\s+de\s+([a-zñáéíóú]+)"
    r"(?:\s+a\s+las)?\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?"
    r"\s*(?:que\s+)?(.+)$",
    re.IGNORECASE,
)


def _normalizar_hora(h: int, minuto: int, ampm: str | None) -> tuple[int, int] | None:
    if minuto < 0 or minuto > 59:
        return None
    if ampm:
        ampm = ampm.lower()
        if h < 1 or h > 12:
            return None
        if ampm == "pm" and h != 12:
            h += 12
        elif ampm == "am" and h == 12:
            h = 0
    else:
        if h < 0 or h > 23:
            return None
    return h, minuto


def parsear(texto: str, ahora_utc: datetime | None = None, offset_tz_minutos: int = 0) -> tuple[datetime, str] | None:
    """
    Intenta parsear `texto` como un recordatorio. Devuelve (fecha_utc, mensaje)
    o None si no hay match.

    Args:
        texto: el mensaje del usuario.
        ahora_utc: momento de referencia en UTC (default: now).
        offset_tz_minutos: offset de la timezone del usuario respecto a UTC.
            Ej: -300 = EST (UTC-5). Se usa para que "mañana 9am" signifique
            9am en hora del usuario, no UTC.
    """
    if not texto:
        return None
    ahora_utc = ahora_utc or datetime.now(tz=timezone.utc).replace(tzinfo=None)

    match_prefijo = _PREFIJO.match(texto)
    if not match_prefijo:
        return None
    resto = texto[match_prefijo.end():].strip()

    # 1) "en N unidades"
    m = _RE_EN.match(resto)
    if m:
        n = int(m.group(1))
        unidad = m.group(2).lower()
        mensaje = m.group(3).strip()
        if not mensaje:
            return None
        if "min" in unidad:
            delta = timedelta(minutes=n)
        elif "hor" in unidad:
            delta = timedelta(hours=n)
        else:  # días
            delta = timedelta(days=n)
        return ahora_utc + delta, mensaje

    # Para patrones que involucran hora del día, necesitamos calcular en la
    # timezone del usuario y luego convertir a UTC.
    ahora_local = ahora_utc + timedelta(minutes=offset_tz_minutos)

    # 2) "hoy/mañana/pasado mañana [a las] HH[:MM] [am|pm]"
    m = _RE_DIA_HORA.match(resto)
    if m:
        palabra_dia = m.group(1).lower().replace("manana", "mañana")
        hora = int(m.group(2))
        minuto = int(m.group(3)) if m.group(3) else 0
        ampm = m.group(4)
        mensaje = m.group(5).strip()
        if not mensaje:
            return None
        hm = _normalizar_hora(hora, minuto, ampm)
        if not hm:
            return None
        h, mi = hm

        base = ahora_local.replace(hour=h, minute=mi, second=0, microsecond=0)
        if palabra_dia.startswith("hoy"):
            fecha_local = base
            # Si la hora ya pasó hoy, asumimos mañana
            if fecha_local <= ahora_local:
                fecha_local += timedelta(days=1)
        elif "pasado" in palabra_dia:
            fecha_local = base + timedelta(days=2)
        else:  # mañana
            fecha_local = base + timedelta(days=1)

        fecha_utc = fecha_local - timedelta(minutes=offset_tz_minutos)
        return fecha_utc, mensaje

    # 3) "el D de MES [a las] HH[:MM] [am|pm]"
    m = _RE_FECHA.match(resto)
    if m:
        dia = int(m.group(1))
        nombre_mes = m.group(2).lower()
        hora = int(m.group(3))
        minuto = int(m.group(4)) if m.group(4) else 0
        ampm = m.group(5)
        mensaje = m.group(6).strip()
        if not mensaje or nombre_mes not in _MESES:
            return None
        hm = _normalizar_hora(hora, minuto, ampm)
        if not hm:
            return None
        h, mi = hm
        mes_n = _MESES[nombre_mes]
        año = ahora_local.year
        try:
            fecha_local = datetime(año, mes_n, dia, h, mi)
        except ValueError:
            return None
        # Si ya pasó, asumimos el año que viene
        if fecha_local <= ahora_local:
            try:
                fecha_local = datetime(año + 1, mes_n, dia, h, mi)
            except ValueError:
                return None
        fecha_utc = fecha_local - timedelta(minutes=offset_tz_minutos)
        return fecha_utc, mensaje

    return None
