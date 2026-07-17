# tests/test_email_actions_concurrencia.py — PR 1 · Carreras del flujo email

"""
Invariantes bajo concurrencia: nunca dos confirmables, nunca se confirma
una acción distinta a la del token, y las mutaciones condicionales
(owner/tipo/estado/hash/TTL en el WHERE) hacen que el perdedor de la
carrera reciba la respuesta uniforme, no un estado inconsistente.
"""

import asyncio

import pytest

from tests.helpers_email_pr1 import (
    fila_por_id,
    filas_email,
    forzar_expiracion,
    preparar,
    preparar_db_email,
)

TEL = "14155550100"
TEL_OTRO = "5215550200"


@pytest.fixture
async def db(tmp_path, monkeypatch):
    return await preparar_db_email(tmp_path, monkeypatch)


class TestPreparacionVsPreparacion:
    @pytest.mark.asyncio
    async def test_misma_key_concurrente_una_sola_accion(self, db):
        res = await asyncio.gather(
            preparar(TEL, "wamid-300"),
            preparar(TEL, "wamid-300"),
            return_exceptions=True,
        )
        assert not any(isinstance(r, Exception) for r in res)
        filas = await filas_email(TEL)
        assert len(filas) == 1
        estados = sorted(r["estado"] for r in res)
        assert estados in (["ok", "rerender"], ["conflicto_concurrencia", "ok"])

    @pytest.mark.asyncio
    async def test_keys_distintas_concurrentes_una_confirmable(self, db):
        res = await asyncio.gather(
            preparar(TEL, "wamid-301", cuerpo="contenido A"),
            preparar(TEL, "wamid-302", cuerpo="contenido B"),
            return_exceptions=True,
        )
        assert not any(isinstance(r, Exception) for r in res)
        confirmables = [
            f for f in await filas_email(TEL) if f.estado == "needs_approval"
        ]
        assert len(confirmables) == 1


class TestConfirmacionVsMutaciones:
    @pytest.mark.asyncio
    async def test_confirmacion_vs_reemplazo(self, db):
        from agent.automation.email_actions import confirmar_envio_correo

        r1 = await preparar(TEL, "wamid-310", cuerpo="contenido viejo")
        res_conf, res_prep = await asyncio.gather(
            confirmar_envio_correo(TEL, r1["token"]),
            preparar(TEL, "wamid-311", cuerpo="contenido nuevo"),
        )
        # La confirmación solo puede: (a) haber corrido antes del reemplazo
        # (hold sobre LA acción del token) o (b) después (uniforme inválida).
        assert res_conf["estado"] in ("pendiente_habilitacion", "invalida")
        if res_conf["estado"] == "pendiente_habilitacion":
            assert res_conf["action_id"] == r1["action_id"]
        # El reemplazo dejó exactamente una confirmable (la nueva)
        confirmables = [
            f for f in await filas_email(TEL) if f.estado == "needs_approval"
        ]
        assert len(confirmables) == 1
        assert confirmables[0].id == res_prep["action_id"]

    @pytest.mark.asyncio
    async def test_confirmacion_vs_expiracion(self, db):
        from agent.automation.email_actions import (
            MENSAJE_REFERENCIA_INVALIDA,
            confirmar_envio_correo,
        )

        r = await preparar(TEL, "wamid-312")
        await forzar_expiracion(r["action_id"])
        res = await asyncio.gather(
            confirmar_envio_correo(TEL, r["token"]),
            confirmar_envio_correo(TEL, r["token"]),
        )
        for res_i in res:
            assert res_i["estado"] == "invalida"
            assert res_i["mensaje"] == MENSAJE_REFERENCIA_INVALIDA
        fila = await fila_por_id(r["action_id"])
        assert fila.estado == "cancelled"
        assert fila.payload_json == '{"purged": true}'

    @pytest.mark.asyncio
    async def test_cancelacion_vs_confirmacion(self, db):
        from agent.automation.email_actions import (
            cancelar_envio_correo,
            confirmar_envio_correo,
        )

        r = await preparar(TEL, "wamid-313")
        res_cancel, res_conf = await asyncio.gather(
            cancelar_envio_correo(TEL, r["token"]),
            confirmar_envio_correo(TEL, r["token"]),
        )
        # La cancelación gana siempre que su UPDATE condicional encuentre la
        # fila; la confirmación nunca "revive" nada (no muta estado en PR 1).
        assert res_cancel["estado"] in ("cancelada", "invalida")
        assert res_conf["estado"] in ("pendiente_habilitacion", "invalida")
        fila = await fila_por_id(r["action_id"])
        if res_cancel["estado"] == "cancelada":
            assert fila.estado == "cancelled"
            assert fila.payload_json == '{"purged": true}'
        else:
            assert fila.estado == "needs_approval"

    @pytest.mark.asyncio
    async def test_ninguna_confirma_una_accion_diferente(self, db):
        from agent.automation.email_actions import confirmar_envio_correo

        r_mio = await preparar(TEL, "wamid-314", cuerpo="contenido mío")
        r_otro = await preparar(TEL_OTRO, "wamid-315", cuerpo="contenido de otro")
        res_cruzado_1, res_cruzado_2 = await asyncio.gather(
            confirmar_envio_correo(TEL, r_otro["token"]),
            confirmar_envio_correo(TEL_OTRO, r_mio["token"]),
        )
        assert res_cruzado_1["estado"] == "invalida"
        assert res_cruzado_2["estado"] == "invalida"
        # Cada owner solo confirma la suya
        res_ok = await confirmar_envio_correo(TEL, r_mio["token"])
        assert res_ok["estado"] == "pendiente_habilitacion"
        assert res_ok["action_id"] == r_mio["action_id"]
