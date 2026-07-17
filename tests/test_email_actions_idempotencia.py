# tests/test_email_actions_idempotencia.py — PR 1 · Idempotencia persistente

import asyncio

import pytest
from sqlalchemy.exc import IntegrityError

from tests.helpers_email_pr1 import (
    fila_por_id,
    filas_email,
    preparar,
    preparar_db_email,
)

TEL = "14155550100"


@pytest.fixture
async def db(tmp_path, monkeypatch):
    return await preparar_db_email(tmp_path, monkeypatch)


class TestMismaKeyMismoFingerprint:
    @pytest.mark.asyncio
    async def test_devuelve_la_misma_accion(self, db):
        r1 = await preparar(TEL, "wamid-001")
        r2 = await preparar(TEL, "wamid-001")
        assert r1["estado"] == "ok"
        assert r2["estado"] == "rerender"
        assert r1["action_id"] == r2["action_id"]
        assert len(await filas_email(TEL)) == 1

    @pytest.mark.asyncio
    async def test_rerender_rota_token_e_invalida_el_anterior(self, db):
        from agent.automation.email_actions import confirmar_envio_correo

        r1 = await preparar(TEL, "wamid-002")
        r2 = await preparar(TEL, "wamid-002")
        assert r1["token"] != r2["token"]
        # Token viejo → respuesta uniforme de inválido
        res_viejo = await confirmar_envio_correo(TEL, r1["token"])
        assert res_viejo["estado"] == "invalida"
        # Token nuevo → confirmación válida (hold del PR 1)
        res_nuevo = await confirmar_envio_correo(TEL, r2["token"])
        assert res_nuevo["estado"] == "pendiente_habilitacion"
        assert res_nuevo["action_id"] == r1["action_id"]

    @pytest.mark.asyncio
    async def test_rerender_conserva_preview(self, db):
        r1 = await preparar(TEL, "wamid-003", cuerpo="Cuerpo persistente X")
        r2 = await preparar(TEL, "wamid-003", cuerpo="Cuerpo persistente X")
        assert r2["payload"]["cuerpo"] == "Cuerpo persistente X"
        assert r2["payload"]["destinatario"] == r1["payload"]["destinatario"]


class TestMismaKeyFingerprintDistinto:
    @pytest.mark.asyncio
    async def test_conflicto_cerrado(self, db):
        r1 = await preparar(TEL, "wamid-010", cuerpo="contenido A")
        r2 = await preparar(TEL, "wamid-010", cuerpo="contenido B")
        assert r1["estado"] == "ok"
        assert r2["estado"] == "conflicto"
        assert "nueva solicitud" in r2["mensaje"].lower()
        # No reemplaza ni crea otra acción
        filas = await filas_email(TEL)
        assert len(filas) == 1
        assert filas[0].estado == "needs_approval"

    @pytest.mark.asyncio
    async def test_conflicto_no_invalida_token_original(self, db):
        from agent.automation.email_actions import confirmar_envio_correo

        r1 = await preparar(TEL, "wamid-011", cuerpo="contenido A")
        await preparar(TEL, "wamid-011", cuerpo="contenido B")
        res = await confirmar_envio_correo(TEL, r1["token"])
        assert res["estado"] == "pendiente_habilitacion"

    @pytest.mark.asyncio
    async def test_conflicto_queda_en_audit(self, db):
        from tests.helpers_email_pr1 import filas_audit

        await preparar(TEL, "wamid-012", cuerpo="contenido A")
        await preparar(TEL, "wamid-012", cuerpo="contenido B")
        eventos = {f.evento for f in await filas_audit()}
        assert "email_prep_key_conflict" in eventos


class TestAccionTerminal:
    @pytest.mark.asyncio
    async def test_terminal_no_genera_segunda_accion(self, db):
        from agent.automation.email_actions import cancelar_envio_correo

        r1 = await preparar(TEL, "wamid-020")
        res_cancel = await cancelar_envio_correo(TEL, r1["token"])
        assert res_cancel["estado"] == "cancelada"
        # Retry del mismo request (misma key + mismo fingerprint)
        r2 = await preparar(TEL, "wamid-020")
        assert r2["estado"] == "terminal"
        assert r2["estado_accion"] == "cancelled"
        assert len(await filas_email(TEL)) == 1

    @pytest.mark.asyncio
    async def test_terminal_no_recrea_contenido_purgado(self, db):
        from agent.automation.email_actions import cancelar_envio_correo

        r1 = await preparar(TEL, "wamid-021", cuerpo="SECRETO_PURGADO_XYZ")
        await cancelar_envio_correo(TEL, r1["token"])
        r2 = await preparar(TEL, "wamid-021", cuerpo="SECRETO_PURGADO_XYZ")
        assert "SECRETO_PURGADO_XYZ" not in r2["mensaje"]
        assert "payload" not in r2
        fila = await fila_por_id(r1["action_id"])
        assert fila.payload_json == '{"purged": true}'


class TestIndiceUnicoConfirmable:
    @pytest.mark.asyncio
    async def test_indice_parcial_efectivo_en_sqlite(self, db):
        """Dos filas needs_approval del mismo owner violan el índice parcial
        aunque se inserten directo (sin pasar por el dominio)."""
        from datetime import datetime

        from agent.automation.models import AccionAutomatizacion
        from agent.memory import async_session

        async def _insertar():
            async with async_session() as session:
                session.add(
                    AccionAutomatizacion(
                        telefono=TEL,
                        tipo_accion="enviar_correo_gmail",
                        titulo="x",
                        estado="needs_approval",
                        riesgo="high",
                        payload_json='{"purged": true}',
                        preparation_request_key="",
                        created_at=datetime.utcnow(),
                        updated_at=datetime.utcnow(),
                    )
                )
                await session.commit()

        await _insertar()
        with pytest.raises(IntegrityError):
            await _insertar()

    @pytest.mark.asyncio
    async def test_indice_no_afecta_otros_tipos(self, db):
        """Filas de otros tipos de acción NO quedan atrapadas por el índice
        parcial (dos needs_approval del mismo owner conviven)."""
        from datetime import datetime

        from agent.automation.models import AccionAutomatizacion
        from agent.memory import async_session

        async with async_session() as session:
            for _ in range(2):
                session.add(
                    AccionAutomatizacion(
                        telefono=TEL,
                        tipo_accion="preparar_mensaje_whatsapp",
                        titulo="x",
                        estado="needs_approval",
                        riesgo="medium",
                        created_at=datetime.utcnow(),
                        updated_at=datetime.utcnow(),
                    )
                )
            await session.commit()

    @pytest.mark.asyncio
    async def test_preparaciones_concurrentes_una_sola_confirmable(self, db):
        res = await asyncio.gather(
            preparar(TEL, "wamid-030", cuerpo="contenido A"),
            preparar(TEL, "wamid-031", cuerpo="contenido B"),
            return_exceptions=True,
        )
        assert not any(isinstance(r, Exception) for r in res)
        confirmables = [
            f for f in await filas_email(TEL) if f.estado == "needs_approval"
        ]
        assert len(confirmables) == 1


class TestReemplazo:
    @pytest.mark.asyncio
    async def test_key_nueva_reemplaza_y_purga_la_anterior(self, db):
        r1 = await preparar(TEL, "wamid-040", cuerpo="contenido viejo")
        r2 = await preparar(TEL, "wamid-041", cuerpo="contenido nuevo")
        assert r2["estado"] == "ok"
        assert r2["es_reemplazo"] is True
        vieja = await fila_por_id(r1["action_id"])
        assert vieja.estado == "cancelled"
        assert vieja.payload_json == '{"purged": true}'
        assert vieja.confirmation_reference_hash == ""
        assert "superseded" in vieja.result_json
        nueva = await fila_por_id(r2["action_id"])
        assert nueva.estado == "needs_approval"

    @pytest.mark.asyncio
    async def test_token_de_la_reemplazada_queda_invalido(self, db):
        from agent.automation.email_actions import confirmar_envio_correo

        r1 = await preparar(TEL, "wamid-042", cuerpo="contenido viejo")
        r2 = await preparar(TEL, "wamid-043", cuerpo="contenido nuevo")
        res_viejo = await confirmar_envio_correo(TEL, r1["token"])
        assert res_viejo["estado"] == "invalida"
        res_nuevo = await confirmar_envio_correo(TEL, r2["token"])
        assert res_nuevo["estado"] == "pendiente_habilitacion"
        assert res_nuevo["action_id"] == r2["action_id"]
