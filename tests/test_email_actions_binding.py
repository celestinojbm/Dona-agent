# tests/test_email_actions_binding.py — PR 1 · Binding por token, no por acción

import hashlib

import pytest

from agent.automation.email_actions import (
    MENSAJE_REFERENCIA_INVALIDA,
    formatear_token,
    generar_token,
    hash_token,
    normalizar_token,
)
from tests.helpers_email_pr1 import fila_por_id, preparar, preparar_db_email

TEL_A = "14155550100"
TEL_B = "5215550200"


@pytest.fixture
async def db(tmp_path, monkeypatch):
    return await preparar_db_email(tmp_path, monkeypatch)


class TestToken:
    def test_token_aleatorio_y_con_alfabeto_crockford(self):
        alfabeto = set("0123456789ABCDEFGHJKMNPQRSTVWXYZ")
        tokens = {generar_token() for _ in range(200)}
        assert len(tokens) > 190  # aleatorio de verdad, no secuencial
        for t in tokens:
            assert len(t) == 10
            assert set(t) <= alfabeto

    def test_normalizacion_crockford(self):
        assert normalizar_token("ab2k7 9xm4t") == "AB2K79XM4T"
        assert normalizar_token("AB2K7-9XM4T") == "AB2K79XM4T"
        assert normalizar_token("  AB2K79XM4T  ") == "AB2K79XM4T"
        # Mapa Crockford: O→0, I→1, L→1
        assert normalizar_token("OB2K79XM4T") == "0B2K79XM4T"
        assert normalizar_token("IB2K79XM4T") == "1B2K79XM4T"
        assert normalizar_token("LB2K79XM4T") == "1B2K79XM4T"

    def test_normalizacion_rechaza_longitud_y_alfabeto(self):
        assert normalizar_token("") is None
        assert normalizar_token("ABC") is None
        assert normalizar_token("AB2K79XM4TX") is None  # 11 chars
        assert normalizar_token("AB2K79XM4U") is None  # U fuera del alfabeto
        assert normalizar_token("AB2K79XM4Ñ") is None
        assert normalizar_token(None) is None

    def test_formatear_token(self):
        assert formatear_token("AB2K79XM4T") == "AB2K7 9XM4T"


class TestSoloHashEnDB:
    @pytest.mark.asyncio
    async def test_el_token_en_claro_no_se_persiste(self, db):
        r = await preparar(TEL_A, "wamid-100")
        token = r["token"]
        fila = await fila_por_id(r["action_id"])
        esperado = hashlib.sha256(token.encode()).hexdigest()
        assert fila.confirmation_reference_hash == esperado
        # El token no aparece en NINGUNA columna de texto
        for col in (
            fila.titulo, fila.descripcion, fila.razon_recomendacion,
            fila.payload_json, fila.result_json, fila.error_message,
            fila.preparation_request_key, fila.idempotency_key,
        ):
            assert token not in (col or "")

    def test_hash_token_es_sha256(self):
        assert hash_token("AB2K79XM4T") == hashlib.sha256(b"AB2K79XM4T").hexdigest()


class TestOwnership:
    @pytest.mark.asyncio
    async def test_token_de_otro_owner_es_invalido(self, db):
        from agent.automation.email_actions import confirmar_envio_correo

        r_a = await preparar(TEL_A, "wamid-110")
        res = await confirmar_envio_correo(TEL_B, r_a["token"])
        assert res["estado"] == "invalida"
        assert res["mensaje"] == MENSAJE_REFERENCIA_INVALIDA
        # La acción de A queda intacta
        fila = await fila_por_id(r_a["action_id"])
        assert fila.estado == "needs_approval"
        assert fila.confirmation_reference_hash != ""

    @pytest.mark.asyncio
    async def test_cancelacion_de_otro_owner_es_invalida(self, db):
        from agent.automation.email_actions import cancelar_envio_correo

        r_a = await preparar(TEL_A, "wamid-111")
        res = await cancelar_envio_correo(TEL_B, r_a["token"])
        assert res["estado"] == "invalida"
        fila = await fila_por_id(r_a["action_id"])
        assert fila.estado == "needs_approval"


class TestRespuestaUniforme:
    @pytest.mark.asyncio
    async def test_inexistente_expirado_y_ajeno_son_indistinguibles(self, db):
        from agent.automation.email_actions import confirmar_envio_correo
        from tests.helpers_email_pr1 import forzar_expiracion

        r = await preparar(TEL_A, "wamid-120")
        await forzar_expiracion(r["action_id"])

        res_expirado = await confirmar_envio_correo(TEL_A, r["token"])
        res_inexistente = await confirmar_envio_correo(TEL_A, generar_token())
        res_ajeno = await confirmar_envio_correo(TEL_B, r["token"])
        assert (
            res_expirado["mensaje"]
            == res_inexistente["mensaje"]
            == res_ajeno["mensaje"]
            == MENSAJE_REFERENCIA_INVALIDA
        )

    @pytest.mark.asyncio
    async def test_fuerza_bruta_razonable_respuesta_uniforme(self, db):
        from agent.automation.email_actions import confirmar_envio_correo

        await preparar(TEL_A, "wamid-121")
        for _ in range(25):
            res = await confirmar_envio_correo(TEL_A, generar_token())
            assert res["estado"] == "invalida"
            assert res["mensaje"] == MENSAJE_REFERENCIA_INVALIDA

    @pytest.mark.asyncio
    async def test_action_id_no_sirve_como_credencial(self, db):
        from agent.automation.email_actions import confirmar_envio_correo

        r = await preparar(TEL_A, "wamid-122")
        # Intentos con el ID de la acción (relleno a 10 chars y crudo)
        for intento in (str(r["action_id"]), str(r["action_id"]).zfill(10)):
            res = await confirmar_envio_correo(TEL_A, intento)
            assert res["estado"] == "invalida"
        fila = await fila_por_id(r["action_id"])
        assert fila.estado == "needs_approval"
