# tests/test_reminders_nl.py — Tests del parser NL de recordatorios

"""
Verifica el parser de lenguaje natural de `agent.reminders_nl.parsear`.
"""

from datetime import datetime, timedelta
import pytest
from agent.reminders_nl import parsear


# Anclar "ahora" para que los tests sean determinísticos.
# Martes 2026-04-14 12:00:00 UTC = 08:00 EDT (UTC-4) aprox.
AHORA = datetime(2026, 4, 14, 12, 0, 0)


class TestRelativo:
    def test_en_minutos(self):
        r = parsear("recuérdame en 30 minutos que llame a Juan", ahora_utc=AHORA)
        assert r is not None
        fecha, msg = r
        assert msg == "llame a Juan"
        assert fecha == AHORA + timedelta(minutes=30)

    def test_en_horas(self):
        r = parsear("recuerdame en 2 horas tomar agua", ahora_utc=AHORA)
        assert r is not None
        assert r[0] == AHORA + timedelta(hours=2)
        assert r[1] == "tomar agua"

    def test_en_dias(self):
        r = parsear("recuérdame en 3 días revisar inventario", ahora_utc=AHORA)
        assert r is not None
        assert r[0] == AHORA + timedelta(days=3)

    def test_recordame_variante(self):
        r = parsear("recordame en 1 hora llamar al cliente", ahora_utc=AHORA)
        assert r is not None


class TestDiaHora:
    def test_manana_9am(self):
        # offset_tz=-300 (UTC-5). AHORA=12:00 UTC → 07:00 local.
        # "mañana 9am" → día siguiente 9am local = 14:00 UTC.
        r = parsear("recuérdame mañana 9am que compre leche",
                    ahora_utc=AHORA, offset_tz_minutos=-300)
        assert r is not None
        fecha, msg = r
        assert msg == "compre leche"
        # Day: April 15 2026, hour local 9 + offset 5 = 14 UTC
        assert fecha == datetime(2026, 4, 15, 14, 0)

    def test_hoy_pm_futuro(self):
        # offset 0 (UTC). AHORA=12:00. "hoy a las 6pm" = 18:00 UTC.
        r = parsear("recuérdame hoy a las 6pm que envíe factura",
                    ahora_utc=AHORA, offset_tz_minutos=0)
        assert r is not None
        fecha, _ = r
        assert fecha == datetime(2026, 4, 14, 18, 0)

    def test_hoy_ya_paso_pasa_a_manana(self):
        # AHORA=12:00 UTC. "hoy 8am" ya pasó → debe ser mañana.
        r = parsear("recuérdame hoy 8am que llame", ahora_utc=AHORA, offset_tz_minutos=0)
        assert r is not None
        fecha, _ = r
        assert fecha == datetime(2026, 4, 15, 8, 0)

    def test_pasado_manana(self):
        r = parsear("recuérdame pasado mañana a las 10am que revise",
                    ahora_utc=AHORA, offset_tz_minutos=0)
        assert r is not None
        fecha, _ = r
        assert fecha == datetime(2026, 4, 16, 10, 0)


class TestFechaExplicita:
    def test_fecha_futura_este_año(self):
        # AHORA=abril 14 → "el 20 de mayo 10am" este año
        r = parsear("recuérdame el 20 de mayo a las 10am reunión",
                    ahora_utc=AHORA, offset_tz_minutos=0)
        assert r is not None
        fecha, msg = r
        assert fecha == datetime(2026, 5, 20, 10, 0)
        assert msg == "reunión"

    def test_fecha_pasada_brinca_a_proximo_año(self):
        # AHORA=abril 14 → "el 1 de enero" ya pasó → próximo año
        r = parsear("recuérdame el 1 de enero a las 9am año nuevo",
                    ahora_utc=AHORA, offset_tz_minutos=0)
        assert r is not None
        assert r[0] == datetime(2027, 1, 1, 9, 0)


class TestNoMatch:
    def test_sin_prefijo_recuerdame(self):
        assert parsear("mañana tengo cita", ahora_utc=AHORA) is None

    def test_prefijo_sin_tiempo(self):
        assert parsear("recuérdame cosas", ahora_utc=AHORA) is None

    def test_hora_invalida(self):
        assert parsear("recuérdame mañana 25am hacer algo", ahora_utc=AHORA) is None

    def test_mes_invalido(self):
        assert parsear("recuérdame el 5 de patata a las 9am algo", ahora_utc=AHORA) is None
