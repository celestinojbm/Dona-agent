# tests/test_email_actions_confirmacion_pr1.py — PR 1 · Confirmación fail-closed

"""
REGLA ABSOLUTA DEL PR 1: ENVIAR <token> válido mantiene needs_approval,
mantiene el token, no crea reserva ni attempt, no aprueba, no reclama,
no llama executor ni Gmail — bajo CUALQUIER valor de EMAIL_SEND_ENABLED.
"""

import importlib
import inspect

import pytest
from sqlalchemy import select

from tests.helpers_email_pr1 import (
    fila_por_id,
    filas_email,
    forzar_expiracion,
    preparar,
    preparar_db_email,
)

TEL = "14155550100"


@pytest.fixture
async def db(tmp_path, monkeypatch):
    return await preparar_db_email(tmp_path, monkeypatch)


@pytest.fixture
def guardias_no_envio(monkeypatch):
    """Falla el test si CUALQUIER vía de materialización se toca."""
    import agent.gmail as _gmail
    from agent.automation import execution as _execution

    async def _prohibido(*args, **kwargs):
        raise AssertionError("PR 1 no debe llamar Gmail ni el pipeline de ejecución")

    monkeypatch.setattr(_gmail, "enviar_correo", _prohibido)
    monkeypatch.setattr(_gmail, "enviar_correo_con_adjunto", _prohibido, raising=False)
    monkeypatch.setattr(_execution, "ejecutar_accion", _prohibido)
    return True


async def _reservas_credito():
    from agent.automation.models import ReservaCreditoAutomation
    from agent.memory import async_session

    async with async_session() as session:
        res = await session.execute(select(ReservaCreditoAutomation))
        return list(res.scalars().all())


class TestConfirmacionSiempreFailClosed:
    @pytest.mark.parametrize("flag", [None, "false", "true", "TRUE", "1"])
    @pytest.mark.asyncio
    async def test_flag_no_habilita_nada(self, db, monkeypatch, guardias_no_envio, flag):
        from agent.automation.email_actions import confirmar_envio_correo

        if flag is None:
            monkeypatch.delenv("EMAIL_SEND_ENABLED", raising=False)
        else:
            monkeypatch.setenv("EMAIL_SEND_ENABLED", flag)

        r = await preparar(TEL, f"wamid-flag-{flag}")
        res = await confirmar_envio_correo(TEL, r["token"])

        assert res["estado"] == "pendiente_habilitacion"
        assert "todavía no está habilitado" in res["mensaje"]
        assert "ENVIAR" in res["mensaje"]

        fila = await fila_por_id(r["action_id"])
        assert fila.estado == "needs_approval"
        assert fila.confirmation_reference_hash != ""  # token sigue vigente
        assert fila.approved_at is None
        assert await _reservas_credito() == []

    @pytest.mark.asyncio
    async def test_repeticion_inocua_y_token_no_consumido(self, db, guardias_no_envio):
        from agent.automation.email_actions import confirmar_envio_correo

        r = await preparar(TEL, "wamid-200")
        hash_inicial = (await fila_por_id(r["action_id"])).confirmation_reference_hash
        for _ in range(3):
            res = await confirmar_envio_correo(TEL, r["token"])
            assert res["estado"] == "pendiente_habilitacion"
        fila = await fila_por_id(r["action_id"])
        assert fila.estado == "needs_approval"
        assert fila.confirmation_reference_hash == hash_inicial

    @pytest.mark.asyncio
    async def test_cero_estados_de_materializacion(self, db, guardias_no_envio):
        from agent.automation.email_actions import confirmar_envio_correo

        r = await preparar(TEL, "wamid-201")
        await confirmar_envio_correo(TEL, r["token"])
        estados = {f.estado for f in await filas_email()}
        assert "approved" not in estados
        assert "running" not in estados
        assert "completed" not in estados

    @pytest.mark.asyncio
    async def test_mensaje_incluye_el_token_para_reconfirmar(self, db):
        from agent.automation.email_actions import (
            confirmar_envio_correo,
            formatear_token,
        )

        r = await preparar(TEL, "wamid-202")
        res = await confirmar_envio_correo(TEL, r["token"])
        assert formatear_token(r["token"]) in res["mensaje"]


class TestDominioSinRamasDeEnvio:
    def test_email_actions_no_importa_gmail_ni_executors(self):
        """Verificación estática de la regla absoluta: el módulo de dominio
        no contiene NINGUNA vía de materialización."""
        import agent.automation.email_actions as mod

        src = inspect.getsource(mod)
        # Ni siquiera puede leer EMAIL_SEND_ENABLED: no importa os.
        assert "import os" not in src
        assert "os.getenv" not in src
        # Cero Gmail, cero pipeline de ejecución, cero reservas.
        assert "agent.gmail" not in src
        assert "import gmail" not in src
        assert "enviar_correo(" not in src
        assert "ejecutar_accion(" not in src
        assert "from agent.automation.execution" not in src
        assert "from agent.automation.executors" not in src
        assert "EJECUTORES_T21A" not in src
        assert "ReservaCredito" not in src
        assert "reservar_creditos" not in src

    def test_tipo_no_registrado_en_ejecutores(self):
        from agent.automation.execution import EJECUTORES_T21A

        assert "enviar_correo_gmail" not in EJECUTORES_T21A


class TestReinicioYTTL:
    @pytest.mark.asyncio
    async def test_reinicio_conserva_borrador_y_token(self, db, guardias_no_envio):
        """El token sobrevive a un reinicio del proceso: el estado vive en la
        DB, no en memoria (a diferencia del dict eliminado)."""
        r = await preparar(TEL, "wamid-210")
        # Simular reinicio: recargar el módulo del dominio (sin estado propio)
        import agent.automation.email_actions as mod
        importlib.reload(mod)
        res = await mod.confirmar_envio_correo(TEL, r["token"])
        assert res["estado"] == "pendiente_habilitacion"
        assert res["action_id"] == r["action_id"]

    @pytest.mark.asyncio
    async def test_expiracion_cancela_y_purga(self, db):
        from agent.automation.email_actions import (
            MENSAJE_REFERENCIA_INVALIDA,
            confirmar_envio_correo,
        )

        r = await preparar(TEL, "wamid-211")
        await forzar_expiracion(r["action_id"])
        res = await confirmar_envio_correo(TEL, r["token"])
        assert res["mensaje"] == MENSAJE_REFERENCIA_INVALIDA
        fila = await fila_por_id(r["action_id"])
        assert fila.estado == "cancelled"
        assert fila.payload_json == '{"purged": true}'
        assert fila.confirmation_reference_hash == ""
        assert "expired" in fila.result_json

    @pytest.mark.asyncio
    async def test_cancelacion_consume_hash_y_purga(self, db):
        from agent.automation.email_actions import (
            cancelar_envio_correo,
            confirmar_envio_correo,
        )

        r = await preparar(TEL, "wamid-212")
        res = await cancelar_envio_correo(TEL, r["token"])
        assert res["estado"] == "cancelada"
        fila = await fila_por_id(r["action_id"])
        assert fila.estado == "cancelled"
        assert fila.confirmation_reference_hash == ""
        assert fila.payload_json == '{"purged": true}'
        # El token ya no confirma nada
        res2 = await confirmar_envio_correo(TEL, r["token"])
        assert res2["estado"] == "invalida"

    @pytest.mark.asyncio
    async def test_payload_corrupto_cancela_y_purga(self, db):
        from sqlalchemy import update

        from agent.automation.email_actions import confirmar_envio_correo
        from agent.automation.models import AccionAutomatizacion
        from agent.memory import async_session

        r = await preparar(TEL, "wamid-213")
        async with async_session() as session:
            await session.execute(
                update(AccionAutomatizacion)
                .where(AccionAutomatizacion.id == r["action_id"])
                .values(payload_json='{"v": 1, "alg": "fernet", "ct": "basura"}')
            )
            await session.commit()
        res = await confirmar_envio_correo(TEL, r["token"])
        assert res["estado"] == "corrupta"
        fila = await fila_por_id(r["action_id"])
        assert fila.estado == "cancelled"
        assert fila.payload_json == '{"purged": true}'
