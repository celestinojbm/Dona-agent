# enhanced/monitoring.py — Habilidad 4: Monitoreo y Alertas

"""
Monitoreo continuo read-only que envía alertas por WhatsApp al owner.

Checks periódicos (cada 15 minutos):
  1. Latencia de DB (si > 2s → alerta)
  2. Errores recientes en logs de actividad
  3. Estado del scheduler
  4. Memoria del proceso

Reglas:
  - Solo lectura, nunca actúa
  - Solo alerta al OWNER_PHONE
  - Cooldown de 1 hora entre alertas del mismo tipo (evitar spam)
"""

import os
import logging
from datetime import datetime, timedelta
from time import monotonic

from enhanced.safe_module import SafeModule, OWNER_PHONE
from enhanced.models import SystemActivityLog, async_session_enhanced
from sqlalchemy import select, func

logger = logging.getLogger("dona.enhanced")

# Cooldown entre alertas del mismo tipo (segundos)
_ALERTA_COOLDOWN = 3600  # 1 hora

# Registro de últimas alertas enviadas: {tipo: datetime_utc}
_ultimas_alertas: dict[str, datetime] = {}

# Umbrales
UMBRAL_LATENCIA_DB_MS = 2000      # 2 segundos
UMBRAL_ERRORES_15MIN = 5          # 5+ errores en 15 min


class ModuloMonitoreo(SafeModule):
    nombre = "monitoreo"

    async def ejecutar_monitoreo(self) -> list[dict]:
        """
        Ejecuta todos los checks de monitoreo.
        Retorna lista de alertas (puede estar vacía si todo está bien).
        """
        alertas = []

        # 1. Latencia de DB
        alerta_db = await self._check_latencia_db()
        if alerta_db:
            alertas.append(alerta_db)

        # 2. Errores recientes en activity logs
        alerta_errores = await self._check_errores_recientes()
        if alerta_errores:
            alertas.append(alerta_errores)

        # 3. Scheduler
        alerta_sched = self._check_scheduler_vivo()
        if alerta_sched:
            alertas.append(alerta_sched)

        return alertas

    async def enviar_alertas(self, alertas: list[dict], proveedor) -> int:
        """
        Envía alertas pendientes al owner via WhatsApp.
        Respeta cooldown para no spamear.
        Retorna cantidad de alertas enviadas.
        """
        if not OWNER_PHONE:
            return 0
        if not alertas:
            return 0

        enviadas = 0
        ahora = datetime.utcnow()

        for alerta in alertas:
            tipo = alerta["tipo"]

            # Verificar cooldown
            ultima = _ultimas_alertas.get(tipo)
            if ultima and (ahora - ultima).total_seconds() < _ALERTA_COOLDOWN:
                logger.debug(f"[MONITOR] Alerta '{tipo}' en cooldown, omitiendo")
                continue

            mensaje = (
                f"*Alerta de monitoreo*\n\n"
                f"*{alerta['titulo']}*\n"
                f"{alerta['detalle']}\n\n"
                f"_Detectado: {ahora.strftime('%H:%M UTC')}_"
            )

            try:
                # Alerta operativa al owner — no sujeta a límite diario.
                from agent.envio_gate import contexto_envio_automatico
                with contexto_envio_automatico():
                    enviado = await proveedor.enviar_mensaje(OWNER_PHONE, mensaje)
                if enviado:
                    _ultimas_alertas[tipo] = ahora
                    enviadas += 1
                    await self.registrar_actividad(
                        OWNER_PHONE, f"alerta_enviada:{tipo}",
                        detalle=alerta["detalle"][:200],
                        nivel="warning",
                    )
            except Exception as e:
                logger.error(f"[MONITOR] Error enviando alerta '{tipo}': {e}")

        return enviadas

    # ── Checks individuales ──────────────────────────────────────────────────

    async def _check_latencia_db(self) -> dict | None:
        """Mide latencia de la DB. Alerta si > umbral."""
        try:
            from agent.memory import async_session
            from sqlalchemy import text

            inicio = monotonic()
            async with async_session() as session:
                await session.execute(text("SELECT 1"))
            latencia_ms = (monotonic() - inicio) * 1000

            if latencia_ms > UMBRAL_LATENCIA_DB_MS:
                return {
                    "tipo": "latencia_db",
                    "titulo": "Latencia de base de datos alta",
                    "detalle": f"Latencia: {latencia_ms:.0f}ms (umbral: {UMBRAL_LATENCIA_DB_MS}ms)",
                }
            return None
        except Exception as e:
            return {
                "tipo": "db_error",
                "titulo": "Base de datos inaccesible",
                "detalle": f"{type(e).__name__}: {str(e)[:150]}",
            }

    async def _check_errores_recientes(self) -> dict | None:
        """Cuenta errores en activity logs de los últimos 15 minutos."""
        try:
            hace_15min = datetime.utcnow() - timedelta(minutes=15)
            async with async_session_enhanced() as session:
                result = await session.execute(
                    select(func.count(SystemActivityLog.id)).where(
                        SystemActivityLog.nivel == "error",
                        SystemActivityLog.timestamp >= hace_15min,
                    )
                )
                count = result.scalar() or 0

            if count >= UMBRAL_ERRORES_15MIN:
                return {
                    "tipo": "errores_frecuentes",
                    "titulo": "Errores frecuentes detectados",
                    "detalle": f"{count} errores en los ultimos 15 minutos (umbral: {UMBRAL_ERRORES_15MIN})",
                }
            return None
        except Exception as e:
            logger.debug(f"[MONITOR] Error verificando activity logs: {e}")
            return None

    def _check_scheduler_vivo(self) -> dict | None:
        """Verifica que el scheduler sigue corriendo."""
        try:
            from agent.scheduler import scheduler
            if not scheduler or not scheduler.running:
                return {
                    "tipo": "scheduler_muerto",
                    "titulo": "Scheduler no esta corriendo",
                    "detalle": "El scheduler de recordatorios y proactividad se detuvo.",
                }
            return None
        except Exception as e:
            return {
                "tipo": "scheduler_error",
                "titulo": "Error accediendo al scheduler",
                "detalle": str(e)[:150],
            }


# Singleton
monitoreo = ModuloMonitoreo()


async def job_monitoreo(proveedor):
    """
    Job del scheduler que ejecuta el monitoreo periódico.
    Registrado cada 15 minutos en el scheduler.
    """
    if not monitoreo.esta_habilitado():
        return

    try:
        alertas = await monitoreo.ejecutar_monitoreo()
        if alertas:
            enviadas = await monitoreo.enviar_alertas(alertas, proveedor)
            if enviadas:
                logger.info(f"[MONITOR] {enviadas} alerta(s) enviada(s) al owner")
        else:
            logger.debug("[MONITOR] Check completado — sin alertas")
    except Exception as e:
        logger.error(f"[MONITOR] Error en job de monitoreo: {e}")
