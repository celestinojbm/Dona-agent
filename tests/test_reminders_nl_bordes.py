# tests/test_reminders_nl_bordes.py — Bordes y ramas de error del parser NL

"""
Cubre las ramas de validación y error de `agent.reminders_nl.parsear` que no
tocaban los tests principales (`test_reminders_nl.py`):

  - texto vacío
  - minuto fuera de rango (>59)
  - hora en formato 24h (sin am/pm), válida y fuera de rango
  - 12am (medianoche) y 12pm (mediodía) normalizados correctamente
  - hora inválida dentro del patrón de fecha explícita
  - fecha calendario imposible (30 de febrero)
  - rollover al año siguiente que cae en fecha imposible (29 de febrero
    de un año no bisiesto)

Todos los tests fijan el COMPORTAMIENTO ACTUAL: no cambian el parser, solo
lo cubren.
"""

from datetime import datetime

from agent.reminders_nl import parsear


# Ancla determinística: martes 2026-04-14 12:00:00 UTC (mismo criterio que
# el test principal para poder razonar sobre "ya pasó / mañana").
AHORA = datetime(2026, 4, 14, 12, 0, 0)


class TestTextoVacio:
    def test_texto_vacio_devuelve_none(self):
        assert parsear("", ahora_utc=AHORA) is None

    def test_texto_none_devuelve_none(self):
        # El guardclause `if not texto` también atrapa None.
        assert parsear(None, ahora_utc=AHORA) is None


class TestMinutoFueraDeRango:
    def test_minuto_mayor_a_59_no_matchea(self):
        # ":75" es minuto inválido → _normalizar_hora devuelve None.
        assert parsear(
            "recuérdame mañana 9:75am que X",
            ahora_utc=AHORA, offset_tz_minutos=0,
        ) is None


class TestFormato24Horas:
    def test_hora_24h_valida_sin_ampm(self):
        # "a las 14" (sin am/pm) toma la rama de 24h: hora tal cual.
        r = parsear(
            "recuérdame mañana a las 14 que X",
            ahora_utc=AHORA, offset_tz_minutos=0,
        )
        assert r is not None
        fecha, msg = r
        assert msg == "X"
        assert fecha == datetime(2026, 4, 15, 14, 0)

    def test_hora_24h_fuera_de_rango_no_matchea(self):
        # "a las 25" sin am/pm → h>23 → None.
        assert parsear(
            "recuérdame mañana a las 25 que X",
            ahora_utc=AHORA, offset_tz_minutos=0,
        ) is None


class TestDoceHoras:
    def test_12am_es_medianoche(self):
        # "hoy 12am" = 00:00; como ya pasó respecto a AHORA (12:00) salta
        # al día siguiente.
        r = parsear(
            "recuérdame hoy 12am que X",
            ahora_utc=AHORA, offset_tz_minutos=0,
        )
        assert r is not None
        assert r[0] == datetime(2026, 4, 15, 0, 0)

    def test_12pm_es_mediodia(self):
        # "hoy 12pm" = 12:00; igual a AHORA (<=) → salta a mañana.
        r = parsear(
            "recuérdame hoy 12pm que X",
            ahora_utc=AHORA, offset_tz_minutos=0,
        )
        assert r is not None
        assert r[0] == datetime(2026, 4, 15, 12, 0)


class TestFechaExplicitaBordes:
    def test_hora_invalida_en_fecha_no_matchea(self):
        # Patrón "el D de MES a las HH": hora 25 (sin am/pm) → None.
        assert parsear(
            "recuérdame el 20 de mayo a las 25 reunión",
            ahora_utc=AHORA, offset_tz_minutos=0,
        ) is None

    def test_fecha_calendario_imposible_no_matchea(self):
        # 30 de febrero no existe → ValueError interno → None.
        assert parsear(
            "recuérdame el 30 de febrero a las 9am X",
            ahora_utc=AHORA, offset_tz_minutos=0,
        ) is None

    def test_rollover_a_anio_no_bisiesto_no_matchea(self):
        # Ancla en 2028 (bisiesto), después del 29-feb: "29 de febrero" ya
        # pasó este año → intenta el año siguiente (2029, no bisiesto) →
        # 29-feb-2029 no existe → None.
        ahora_2028 = datetime(2028, 6, 1, 12, 0, 0)
        assert parsear(
            "recuérdame el 29 de febrero a las 9am X",
            ahora_utc=ahora_2028, offset_tz_minutos=0,
        ) is None
