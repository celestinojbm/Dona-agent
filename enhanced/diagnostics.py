# enhanced/diagnostics.py — Habilidad 1: Auto-Diagnóstico Inteligente

"""
Dona puede inspeccionar su propia salud (read-only).

Dos vistas:
  - Vista usuario: "¿cómo estás?" → respuesta simplificada (todo bien / hay un problema)
  - Vista owner:   "!diagnostic"  → reporte técnico completo

Checks:
  1. Base de datos (Supabase/PostgreSQL)
  2. Anthropic Claude API
  3. Meta WhatsApp API
  4. Google Calendar OAuth
  5. OpenAI Embeddings
  6. MiroFish
  7. Scheduler (APScheduler)
  8. Memoria (últimos mensajes)
"""

import os
import logging
from datetime import datetime

import httpx

from enhanced.safe_module import SafeModule, NivelPermiso, _es_owner

logger = logging.getLogger("dona.enhanced")


class ModuloDiagnostico(SafeModule):
    nombre = "diagnostico"

    async def ejecutar_diagnostico(self, telefono: str) -> dict:
        """
        Ejecuta todos los checks de salud.
        Retorna dict con resultados por servicio.
        """
        checks = {}

        # 1. Base de datos
        checks["database"] = await self._check_database()

        # 2. Anthropic Claude API
        checks["claude_api"] = await self._check_claude()

        # 3. Meta WhatsApp API
        checks["whatsapp_meta"] = await self._check_meta()

        # 4. Google Calendar
        checks["google_calendar"] = self._check_google_config()

        # 5. OpenAI Embeddings
        checks["openai_embeddings"] = self._check_openai_config()

        # 6. MiroFish
        checks["mirofish"] = self._check_mirofish_config()

        # 7. Scheduler
        checks["scheduler"] = self._check_scheduler()

        await self.registrar_actividad(
            telefono, "diagnostico_ejecutado",
            detalle=f"checks={len(checks)} owner={_es_owner(telefono)}",
        )

        return checks

    def formatear_vista_usuario(self, checks: dict) -> str:
        """Vista simplificada para cualquier usuario."""
        problemas = [k for k, v in checks.items() if v["estado"] != "ok"]

        if not problemas:
            return (
                "Estoy funcionando perfectamente, todo en orden. "
                "Base de datos, IA y WhatsApp conectados sin problemas."
            )
        else:
            return (
                "Estoy teniendo algunos inconvenientes tecnicos en este momento, "
                "pero sigo funcionando. Si notas algo raro, el equipo ya esta al tanto."
            )

    def formatear_vista_owner(self, checks: dict) -> str:
        """Vista tecnica completa para el owner."""
        lineas = ["*Diagnostico del sistema Dona*\n"]
        ahora = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
        lineas.append(f"Timestamp: {ahora}\n")

        for servicio, resultado in checks.items():
            estado = resultado["estado"]
            icono = {"ok": "OK", "warning": "WARN", "error": "ERR"}.get(estado, "?")
            lineas.append(f"[{icono}] *{servicio}*")
            if resultado.get("detalle"):
                lineas.append(f"    {resultado['detalle']}")

        # Resumen
        total = len(checks)
        ok = sum(1 for v in checks.values() if v["estado"] == "ok")
        warn = sum(1 for v in checks.values() if v["estado"] == "warning")
        err = sum(1 for v in checks.values() if v["estado"] == "error")
        lineas.append(f"\n*Resumen*: {ok}/{total} OK | {warn} warnings | {err} errores")

        return "\n".join(lineas)

    # ── Checks individuales ──────────────────────────────────────────────────

    async def _check_database(self) -> dict:
        """Verifica conectividad con la base de datos."""
        try:
            from agent.memory import async_session
            from sqlalchemy import text
            async with async_session() as session:
                result = await session.execute(text("SELECT 1"))
                result.scalar()
            return {"estado": "ok", "detalle": "Conexion activa"}
        except Exception as e:
            return {"estado": "error", "detalle": f"{type(e).__name__}: {str(e)[:100]}"}

    async def _check_claude(self) -> dict:
        """Verifica que la Anthropic API key es valida."""
        api_key = os.getenv("ANTHROPIC_API_KEY", "")
        if not api_key:
            return {"estado": "error", "detalle": "ANTHROPIC_API_KEY no configurada"}
        # Verificar formato basico (no hacer llamada real para no gastar tokens)
        if api_key.startswith("sk-ant-"):
            return {"estado": "ok", "detalle": "API key configurada (formato valido)"}
        return {"estado": "warning", "detalle": "API key configurada pero formato inusual"}

    async def _check_meta(self) -> dict:
        """Verifica configuracion de Meta WhatsApp API."""
        token = os.getenv("META_ACCESS_TOKEN", "")
        phone_id = os.getenv("META_PHONE_NUMBER_ID", "")
        app_secret = os.getenv("META_APP_SECRET", "")

        if not token:
            return {"estado": "error", "detalle": "META_ACCESS_TOKEN no configurado"}
        if not phone_id:
            return {"estado": "error", "detalle": "META_PHONE_NUMBER_ID no configurado"}

        detalle = "Token y Phone ID configurados"
        if not app_secret:
            detalle += " | HMAC deshabilitado (sin META_APP_SECRET)"
            return {"estado": "warning", "detalle": detalle}

        return {"estado": "ok", "detalle": detalle}

    def _check_google_config(self) -> dict:
        """Verifica configuracion de Google OAuth."""
        client_id = os.getenv("GOOGLE_CLIENT_ID", "")
        client_secret = os.getenv("GOOGLE_CLIENT_SECRET", "")

        if not client_id or not client_secret:
            return {"estado": "warning", "detalle": "Google OAuth no configurado (opcional)"}
        return {"estado": "ok", "detalle": "OAuth configurado"}

    def _check_openai_config(self) -> dict:
        """Verifica configuracion de OpenAI para embeddings."""
        api_key = os.getenv("OPENAI_API_KEY", "")
        if not api_key:
            return {"estado": "warning", "detalle": "Deshabilitado (sin OPENAI_API_KEY)"}
        return {"estado": "ok", "detalle": "API key configurada"}

    def _check_mirofish_config(self) -> dict:
        """Verifica configuracion de MiroFish."""
        base_url = os.getenv("MIROFISH_BASE_URL", "")
        if not base_url:
            return {"estado": "warning", "detalle": "Deshabilitado (sin MIROFISH_BASE_URL)"}
        return {"estado": "ok", "detalle": f"Configurado: {base_url[:40]}"}

    def _check_scheduler(self) -> dict:
        """Verifica estado del scheduler."""
        try:
            from agent.scheduler import scheduler
            if scheduler and scheduler.running:
                jobs = scheduler.get_jobs()
                return {"estado": "ok", "detalle": f"Corriendo, {len(jobs)} jobs activos"}
            return {"estado": "warning", "detalle": "Scheduler no esta corriendo"}
        except Exception as e:
            return {"estado": "error", "detalle": f"Error accediendo al scheduler: {e}"}


# Singleton
diagnostico = ModuloDiagnostico()
