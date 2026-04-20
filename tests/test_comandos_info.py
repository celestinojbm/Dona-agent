# tests/test_comandos_info.py — Tests para comandos "dona ayuda" y "dona estado"

"""
Cubre detección de los comandos y el render del texto, incluyendo
el branch según Google esté conectado o no.
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from agent.comandos_info import (
    es_comando_ayuda,
    es_comando_estado,
    generar_texto_ayuda,
    generar_texto_estado,
)


class TestDetectores:
    def test_ayuda_variantes(self):
        assert es_comando_ayuda("dona ayuda")
        assert es_comando_ayuda("Dona Ayuda")
        assert es_comando_ayuda("  dona help  ")
        assert es_comando_ayuda("dona qué puedes hacer")
        assert es_comando_ayuda("dona comandos")

    def test_ayuda_rechaza_no_comandos(self):
        assert not es_comando_ayuda("")
        assert not es_comando_ayuda("hola")
        assert not es_comando_ayuda("ayuda")  # sin prefijo dona
        assert not es_comando_ayuda("dona ayudame con esto")

    def test_estado_variantes(self):
        assert es_comando_estado("dona estado")
        assert es_comando_estado("Dona Status")
        assert es_comando_estado("dona diagnóstico")
        assert es_comando_estado("dona health")

    def test_estado_rechaza_no_comandos(self):
        assert not es_comando_estado("")
        assert not es_comando_estado("status")
        assert not es_comando_estado("dona estás ahí?")


class TestGenerarTextoAyuda:
    @pytest.mark.asyncio
    async def test_sin_google_muestra_hint_conectar(self):
        with patch("agent.memory.obtener_google_auth", new=AsyncMock(return_value=None)):
            texto = await generar_texto_ayuda("5551")
        assert "Conectar Google" in texto
        assert "dona conectar google" in texto
        # No debería listar tools Google-exclusivas
        assert "Calendario (Google)" not in texto

    @pytest.mark.asyncio
    async def test_con_google_lista_capacidades_extra(self):
        auth = {"email": "user@example.com", "access_token": "x"}
        with patch("agent.memory.obtener_google_auth", new=AsyncMock(return_value=auth)):
            texto = await generar_texto_ayuda("5551")
        assert "Calendario (Google)" in texto
        assert "Correo (Gmail)" in texto
        assert "Tareas (Google Tasks)" in texto
        assert "Sheets" in texto

    @pytest.mark.asyncio
    async def test_siempre_incluye_finanzas_y_tip(self):
        with patch("agent.memory.obtener_google_auth", new=AsyncMock(return_value=None)):
            texto = await generar_texto_ayuda("5551")
        assert "Finanzas" in texto
        assert "resumen del mes" in texto
        assert "dona estado" in texto  # apunta al otro comando


class TestGenerarTextoEstado:
    @pytest.mark.asyncio
    async def test_sin_google_indica_no_conectado(self):
        with patch("agent.memory.obtener_google_auth", new=AsyncMock(return_value=None)), \
             patch("agent.comandos_info._contar_mensajes_recientes", new=AsyncMock(return_value=0)):
            # Scheduler puede no estar corriendo en tests — best-effort
            texto = await generar_texto_estado("5551")
        assert "Estado de Dona" in texto
        assert "no conectado" in texto
        assert "dona conectar google" in texto

    @pytest.mark.asyncio
    async def test_con_google_muestra_email(self):
        auth = {"email": "bob@example.com", "access_token": "x"}
        with patch("agent.memory.obtener_google_auth", new=AsyncMock(return_value=auth)), \
             patch("agent.comandos_info._contar_mensajes_recientes", new=AsyncMock(return_value=5)):
            texto = await generar_texto_estado("5551")
        assert "bob@example.com" in texto
        assert "5 mensajes" in texto

    @pytest.mark.asyncio
    async def test_runtime_flags(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-xxx")
        monkeypatch.setenv("WHATSAPP_PROVIDER", "meta")
        monkeypatch.delenv("REDIS_URL", raising=False)
        with patch("agent.memory.obtener_google_auth", new=AsyncMock(return_value=None)), \
             patch("agent.comandos_info._contar_mensajes_recientes", new=AsyncMock(return_value=0)):
            texto = await generar_texto_estado("5551")
        assert "WhatsApp=meta" in texto
        assert "IA ✓" in texto

    @pytest.mark.asyncio
    async def test_scheduler_con_jobs(self):
        # Fake scheduler con un par de jobs — inyectamos un módulo fake en sys.modules
        # para evitar dependencia de APScheduler en el entorno de test.
        import sys, types
        fake_job1 = MagicMock()
        fake_job1.id = "recap_semanal"
        fake_job1.trigger = "cron[day_of_week='sun', hour='19']"

        fake_scheduler = MagicMock()
        fake_scheduler.running = True
        fake_scheduler.get_jobs = MagicMock(return_value=[fake_job1])

        fake_mod = types.ModuleType("agent.scheduler")
        fake_mod.scheduler = fake_scheduler
        orig = sys.modules.get("agent.scheduler")
        sys.modules["agent.scheduler"] = fake_mod
        try:
            with patch("agent.memory.obtener_google_auth", new=AsyncMock(return_value=None)), \
                 patch("agent.comandos_info._contar_mensajes_recientes", new=AsyncMock(return_value=0)):
                texto = await generar_texto_estado("5551")
        finally:
            if orig is not None:
                sys.modules["agent.scheduler"] = orig
            else:
                sys.modules.pop("agent.scheduler", None)
        assert "Scheduler" in texto
        assert "recap_semanal" in texto

    @pytest.mark.asyncio
    async def test_scheduler_detenido(self):
        import sys, types
        fake_scheduler = MagicMock()
        fake_scheduler.running = False

        fake_mod = types.ModuleType("agent.scheduler")
        fake_mod.scheduler = fake_scheduler
        orig = sys.modules.get("agent.scheduler")
        sys.modules["agent.scheduler"] = fake_mod
        try:
            with patch("agent.memory.obtener_google_auth", new=AsyncMock(return_value=None)), \
                 patch("agent.comandos_info._contar_mensajes_recientes", new=AsyncMock(return_value=0)):
                texto = await generar_texto_estado("5551")
        finally:
            if orig is not None:
                sys.modules["agent.scheduler"] = orig
            else:
                sys.modules.pop("agent.scheduler", None)
        assert "detenido" in texto
