# tests/test_email_brain_migracion.py — PR 1 · Migración de los 3 caminos legacy

"""
Los tres caminos (preparar_borrador_correo, responder_correo,
confirmar_envio_correo) delegan al dominio persistente: cero dict en
memoria, cero Gmail en confirmación, UX equivalente (preview + espera de
confirmación). Cero red real: Claude y Gmail van mockeados.
"""

import re

import pytest

import agent.brain as brain
from tests.helpers_email_pr1 import filas_email, preparar_db_email

TEL = "14155550100"


class _Bloque:
    def __init__(self, name, input_, id_="tu_1"):
        self.type = "tool_use"
        self.name = name
        self.input = input_
        self.id = id_


class _Texto:
    def __init__(self, text):
        self.type = "text"
        self.text = text


class _Respuesta:
    def __init__(self, content, stop_reason="tool_use"):
        self.content = content
        self.stop_reason = stop_reason


@pytest.fixture
async def db(tmp_path, monkeypatch):
    return await preparar_db_email(tmp_path, monkeypatch)


@pytest.fixture
def llm_y_gmail_mock(monkeypatch):
    """Mockea la 2ª llamada a Claude (captura el tool_result), el redactor
    de cuerpos y TODO Gmail de escritura. Cero red real."""
    import agent.gmail as _gmail
    import agent.llm as _llm

    capturas = {}

    async def _fake_invocar(api_kwargs, telefono):
        capturas["kwargs"] = api_kwargs
        return _Respuesta([_Texto("ok")], stop_reason="end_turn")

    async def _fake_completar(prompt, max_tokens=500, telefono=""):
        return "Cuerpo redactado por el LLM (mock)."

    async def _gmail_prohibido(*args, **kwargs):
        raise AssertionError("PR 1 jamás llama al envío de Gmail")

    async def _fake_leer_correo(telefono, message_id):
        return {
            "from": "remitente@ejemplo.com",
            "subject": "Consulta",
            "cuerpo": "Texto del correo original",
            "date": "2026-07-17",
            "thread_id": "thread-123",
            "message_id_header": "<msg-123@ejemplo.com>",
        }

    monkeypatch.setattr(brain, "_invocar_claude_gateado", _fake_invocar)
    monkeypatch.setattr(_llm, "completar_texto", _fake_completar)
    monkeypatch.setattr(_gmail, "enviar_correo", _gmail_prohibido)
    monkeypatch.setattr(_gmail, "leer_correo", _fake_leer_correo)
    return capturas


def _tool_result(capturas) -> str:
    mensajes = capturas["kwargs"]["messages"]
    return mensajes[-1]["content"][0]["content"]


def _extraer_codigo(texto: str) -> str:
    m = re.search(r"Código de confirmación: ([0-9A-Z]{5} [0-9A-Z]{5})", texto)
    assert m, f"preview sin código: {texto[:200]}"
    return m.group(1)


class TestDictEliminado:
    def test_borradores_pendientes_ya_no_existe(self):
        assert not hasattr(brain, "_borradores_pendientes")

    def test_seleccionar_tools_no_depende_del_dict(self):
        import inspect

        src = inspect.getsource(brain.seleccionar_tools)
        assert "_borradores_pendientes" not in src

    def test_confirmar_requiere_confirmation_reference(self):
        tool = next(t for t in brain.TOOLS if t["name"] == "confirmar_envio_correo")
        assert "confirmation_reference" in tool["input_schema"]["properties"]
        assert tool["input_schema"]["required"] == ["confirmation_reference"]


class TestPrepararBorrador:
    @pytest.mark.asyncio
    async def test_preview_persistido_con_codigo(self, db, llm_y_gmail_mock):
        resp = _Respuesta([_Bloque("preparar_borrador_correo", {
            "destinatario": "cliente@ejemplo.com",
            "asunto": "Propuesta",
            "instrucciones": "que confirme la reunión",
        })])
        out = await brain._manejar_tool_use(
            resp, [{"role": "user", "content": "manda un correo"}],
            "sys", TEL, None, preparation_request_key="wamid-b1",
        )
        assert out == "ok"
        tool_result = _tool_result(llm_y_gmail_mock)
        assert "NO* SE HA ENVIADO" in tool_result or "NO SE HA ENVIADO" in tool_result
        assert "cliente@ejemplo.com" in tool_result
        codigo = _extraer_codigo(tool_result)
        # La acción quedó persistida y el código confirma (hold del PR 1)
        filas = await filas_email(TEL)
        assert len(filas) == 1
        assert filas[0].estado == "needs_approval"
        from agent.automation.email_actions import confirmar_envio_correo
        res = await confirmar_envio_correo(TEL, codigo)
        assert res["estado"] == "pendiente_habilitacion"

    @pytest.mark.asyncio
    async def test_alias_legacy_redactar_y_enviar(self, db, llm_y_gmail_mock):
        resp = _Respuesta([_Bloque("redactar_y_enviar_correo", {
            "destinatario": "cliente@ejemplo.com",
            "asunto": "Propuesta",
            "instrucciones": "seguimiento",
        })])
        await brain._manejar_tool_use(
            resp, [], "sys", TEL, None, preparation_request_key="wamid-b2",
        )
        assert len(await filas_email(TEL)) == 1


class TestResponderCorreo:
    @pytest.mark.asyncio
    async def test_conserva_thread_y_reply(self, db, llm_y_gmail_mock):
        resp = _Respuesta([_Bloque("responder_correo", {
            "message_id": "msg-1",
            "instrucciones": "dile que sí",
        })])
        await brain._manejar_tool_use(
            resp, [], "sys", TEL, None, preparation_request_key="wamid-b3",
        )
        tool_result = _tool_result(llm_y_gmail_mock)
        assert "remitente@ejemplo.com" in tool_result
        filas = await filas_email(TEL)
        assert len(filas) == 1
        from agent.automation import email_crypto
        payload = email_crypto.descifrar_payload_email(filas[0].payload_json)
        assert payload["thread_id"] == "thread-123"
        assert payload["reply_message_id"] == "<msg-123@ejemplo.com>"
        assert payload["asunto"] == "Re: Consulta"


class TestConfirmarEnvioTool:
    @pytest.mark.asyncio
    async def test_delegacion_al_dominio_sin_gmail(self, db, llm_y_gmail_mock):
        from tests.helpers_email_pr1 import preparar

        r = await preparar(TEL, "wamid-b4")
        resp = _Respuesta([_Bloque("confirmar_envio_correo", {
            "confirmation_reference": r["token"],
        })])
        await brain._manejar_tool_use(
            resp, [], "sys", TEL, None, preparation_request_key="wamid-b4",
        )
        tool_result = _tool_result(llm_y_gmail_mock)
        assert "todavía no está habilitado" in tool_result
        assert "PROHIBIDO decir que el correo se envió" in tool_result
        filas = await filas_email(TEL)
        assert filas[0].estado == "needs_approval"

    @pytest.mark.asyncio
    async def test_sin_referencia_pide_el_codigo(self, db, llm_y_gmail_mock):
        resp = _Respuesta([_Bloque("confirmar_envio_correo", {})])
        await brain._manejar_tool_use(
            resp, [], "sys", TEL, None, preparation_request_key="wamid-b5",
        )
        tool_result = _tool_result(llm_y_gmail_mock)
        assert "Falta el código" in tool_result

    @pytest.mark.asyncio
    async def test_referencia_invalida_respuesta_uniforme(self, db, llm_y_gmail_mock):
        from agent.automation.email_actions import MENSAJE_REFERENCIA_INVALIDA

        resp = _Respuesta([_Bloque("confirmar_envio_correo", {
            "confirmation_reference": "AB2K79XM4T",
        })])
        await brain._manejar_tool_use(
            resp, [], "sys", TEL, None, preparation_request_key="wamid-b6",
        )
        assert MENSAJE_REFERENCIA_INVALIDA in _tool_result(llm_y_gmail_mock)


class TestSeleccionDeTools:
    @pytest.mark.asyncio
    async def test_tiene_accion_confirmable(self, db):
        from agent.automation.email_actions import tiene_accion_confirmable
        from tests.helpers_email_pr1 import preparar

        assert await tiene_accion_confirmable(TEL) is False
        await preparar(TEL, "wamid-b7")
        assert await tiene_accion_confirmable(TEL) is True
        assert await tiene_accion_confirmable("5215559999") is False


class TestRegresionReadOnly:
    def test_buscar_correos_sigue_en_registry_read_only(self):
        from agent import tools_registry

        assert "buscar_correos" in tools_registry.REGISTRY
        assert tools_registry.es_read_only("buscar_correos")

    def test_tools_gmail_read_only_siguen_definidas(self):
        nombres = {t["name"] for t in brain.TOOLS}
        for esperada in ("leer_correos", "leer_correo_completo", "buscar_correos",
                        "preparar_borrador_correo", "confirmar_envio_correo",
                        "responder_correo"):
            assert esperada in nombres
