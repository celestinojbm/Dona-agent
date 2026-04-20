# tests/test_gmail_adjuntos.py — Tests para enviar_correo_con_adjunto

"""
Verifica que el multipart del correo tenga headers correctos, un text/plain,
al menos un attachment base64-encoded, y que el POST vaya al endpoint /messages/send.
"""

import base64
import email
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from agent import gmail


def _mock_resp(status: int, json_data: dict | None = None, text: str = ""):
    r = MagicMock()
    r.status_code = status
    r.json = MagicMock(return_value=json_data or {})
    r.text = text
    return r


def _ctx_with_post(post_responses: list):
    client = MagicMock()
    client.post = AsyncMock(side_effect=list(post_responses))
    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=client)
    ctx.__aexit__ = AsyncMock(return_value=None)
    return ctx, client


@pytest.fixture
def mock_token(monkeypatch):
    async def fake(t): return "fake-token"
    monkeypatch.setattr(gmail, "_token", fake)


@pytest.fixture
def mock_token_none(monkeypatch):
    async def fake(t): return None
    monkeypatch.setattr(gmail, "_token", fake)


class TestEnviarCorreoConAdjunto:
    @pytest.mark.asyncio
    async def test_sin_token_retorna_false(self, mock_token_none):
        ok = await gmail.enviar_correo_con_adjunto(
            "5551", "a@b.com", "Asunto", "Cuerpo",
            adjuntos=[{"nombre": "f.csv", "contenido": b"a,b"}],
        )
        assert ok is False

    @pytest.mark.asyncio
    async def test_sin_adjuntos_delega_a_simple(self, mock_token, monkeypatch):
        llamados = {}

        async def fake_simple(telefono, destinatario, asunto, cuerpo, **kw):
            llamados["ok"] = (telefono, destinatario, asunto, cuerpo)
            return True

        monkeypatch.setattr(gmail, "enviar_correo", fake_simple)
        ok = await gmail.enviar_correo_con_adjunto(
            "5551", "a@b.com", "Hola", "Contenido", adjuntos=[]
        )
        assert ok is True
        assert llamados["ok"] == ("5551", "a@b.com", "Hola", "Contenido")

    @pytest.mark.asyncio
    async def test_envio_exitoso_con_un_adjunto(self, mock_token):
        ctx, client = _ctx_with_post([_mock_resp(200, {"id": "msg1"})])
        with patch("agent.gmail.httpx.AsyncClient", return_value=ctx):
            ok = await gmail.enviar_correo_con_adjunto(
                "5551", "dest@x.com", "Reporte abril", "Adjunto el CSV del mes.",
                adjuntos=[{"nombre": "reporte.csv", "contenido": b"fecha,monto\n2026-04-01,100.00\n"}],
            )
        assert ok is True
        args, kwargs = client.post.call_args
        # Endpoint correcto
        assert "messages/send" in args[0]
        # Authorization header
        assert kwargs["headers"]["Authorization"] == "Bearer fake-token"
        # El body tiene 'raw' base64 urlsafe del MIME
        raw = kwargs["json"]["raw"]
        # Restituir padding y decodificar
        padding = "=" * (-len(raw) % 4)
        mime_bytes = base64.urlsafe_b64decode(raw + padding)
        msg = email.message_from_bytes(mime_bytes)
        assert msg["To"] == "dest@x.com"
        assert msg["Subject"] == "Reporte abril"
        # Debe ser multipart con al menos 2 partes (body + adjunto)
        assert msg.is_multipart()
        partes = list(msg.walk())
        # partes[0] es el root; buscar una parte con Content-Disposition attachment
        tiene_adjunto = any(
            "attachment" in (p.get("Content-Disposition") or "")
            and "reporte.csv" in (p.get("Content-Disposition") or "")
            for p in partes
        )
        assert tiene_adjunto

    @pytest.mark.asyncio
    async def test_mime_type_inferido_por_nombre(self, mock_token):
        ctx, client = _ctx_with_post([_mock_resp(200, {"id": "m"})])
        with patch("agent.gmail.httpx.AsyncClient", return_value=ctx):
            await gmail.enviar_correo_con_adjunto(
                "5551", "a@b.com", "S", "B",
                adjuntos=[{"nombre": "x.pdf", "contenido": b"%PDF-1.4"}],
            )
        raw = client.post.call_args.kwargs["json"]["raw"]
        mime_bytes = base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4))
        # En el body MIME debe aparecer application/pdf inferido desde .pdf
        assert b"application/pdf" in mime_bytes

    @pytest.mark.asyncio
    async def test_multiples_adjuntos(self, mock_token):
        ctx, client = _ctx_with_post([_mock_resp(200, {"id": "m"})])
        with patch("agent.gmail.httpx.AsyncClient", return_value=ctx):
            ok = await gmail.enviar_correo_con_adjunto(
                "5551", "a@b.com", "S", "B",
                adjuntos=[
                    {"nombre": "a.csv", "contenido": b"1,2"},
                    {"nombre": "b.txt", "contenido": b"hola"},
                ],
            )
        assert ok is True
        raw = client.post.call_args.kwargs["json"]["raw"]
        mime_bytes = base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4))
        msg = email.message_from_bytes(mime_bytes)
        nombres = [
            p.get_filename() for p in msg.walk() if p.get_filename()
        ]
        assert "a.csv" in nombres and "b.txt" in nombres

    @pytest.mark.asyncio
    async def test_403_levanta_scope_error(self, mock_token):
        ctx, _ = _ctx_with_post([_mock_resp(403, text="Forbidden")])
        with patch("agent.gmail.httpx.AsyncClient", return_value=ctx):
            with pytest.raises(gmail.GmailScopeError):
                await gmail.enviar_correo_con_adjunto(
                    "5551", "a@b.com", "S", "B",
                    adjuntos=[{"nombre": "f.csv", "contenido": b"x"}],
                )

    @pytest.mark.asyncio
    async def test_500_retorna_false(self, mock_token):
        ctx, _ = _ctx_with_post([_mock_resp(500, text="err")])
        with patch("agent.gmail.httpx.AsyncClient", return_value=ctx):
            ok = await gmail.enviar_correo_con_adjunto(
                "5551", "a@b.com", "S", "B",
                adjuntos=[{"nombre": "f.csv", "contenido": b"x"}],
            )
        assert ok is False
