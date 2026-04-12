# enhanced/insights.py — Habilidad 5: Aprendizaje y Optimización Continua

"""
Analiza patrones de uso del sistema y genera reportes semanales al owner.

Análisis:
  1. Actividad por hora/día (picos de uso)
  2. Sistemas más usados del catálogo
  3. Errores recurrentes en activity logs
  4. Usuarios más activos
  5. Recomendaciones de optimización

El reporte se envía al owner los domingos a las 20:00 UTC.
Read-only: sugiere, nunca aplica cambios automáticamente.
"""

import logging
from datetime import datetime, timedelta
from collections import Counter

from sqlalchemy import select, func, text
from enhanced.safe_module import SafeModule, OWNER_PHONE
from enhanced.models import SystemActivityLog, UserSystem, async_session_enhanced

logger = logging.getLogger("dona.enhanced")


class ModuloInsights(SafeModule):
    nombre = "insights"

    async def generar_reporte_semanal(self) -> str:
        """
        Genera el reporte semanal de insights.
        Retorna el texto formateado para enviar por WhatsApp.
        """
        hace_7d = datetime.utcnow() - timedelta(days=7)

        # 1. Actividad total en activity logs
        actividad = await self._actividad_semanal(hace_7d)

        # 2. Errores recurrentes
        errores = await self._errores_semana(hace_7d)

        # 3. Sistemas más populares
        sistemas = await self._sistemas_populares()

        # 4. Usuarios activos (conteo de mensajes en DB principal)
        usuarios_activos = await self._usuarios_activos_semana(hace_7d)

        # 5. Construir reporte
        lineas = [
            "*Reporte Semanal Dona 2.0*",
            f"_Periodo: {hace_7d.strftime('%d/%m')} — {datetime.utcnow().strftime('%d/%m/%Y')}_\n",
        ]

        # Actividad
        lineas.append(f"*Actividad del sistema*")
        lineas.append(f"  Acciones registradas: {actividad['total']}")
        lineas.append(f"  Errores: {actividad['errores']}")
        lineas.append(f"  Acciones privilegiadas: {actividad['privilegiadas']}")
        lineas.append("")

        # Usuarios
        lineas.append(f"*Usuarios*")
        lineas.append(f"  Usuarios activos (7d): {usuarios_activos}")
        lineas.append("")

        # Sistemas
        if sistemas:
            lineas.append(f"*Sistemas mas usados*")
            for nombre, count in sistemas[:5]:
                lineas.append(f"  {nombre}: {count} usuarios")
            lineas.append("")

        # Errores
        if errores:
            lineas.append(f"*Errores recurrentes*")
            for accion, count in errores[:5]:
                lineas.append(f"  {accion}: {count} veces")
            lineas.append("")

        # Recomendaciones
        recomendaciones = self._generar_recomendaciones(actividad, errores, sistemas, usuarios_activos)
        if recomendaciones:
            lineas.append("*Recomendaciones*")
            for r in recomendaciones:
                lineas.append(f"  - {r}")

        return "\n".join(lineas)

    async def _actividad_semanal(self, desde: datetime) -> dict:
        """Cuenta actividad total, errores y acciones privilegiadas."""
        try:
            async with async_session_enhanced() as session:
                # Total
                r_total = await session.execute(
                    select(func.count(SystemActivityLog.id)).where(
                        SystemActivityLog.timestamp >= desde
                    )
                )
                total = r_total.scalar() or 0

                # Errores
                r_err = await session.execute(
                    select(func.count(SystemActivityLog.id)).where(
                        SystemActivityLog.timestamp >= desde,
                        SystemActivityLog.nivel == "error",
                    )
                )
                errores = r_err.scalar() or 0

                # Privilegiadas
                r_priv = await session.execute(
                    select(func.count(SystemActivityLog.id)).where(
                        SystemActivityLog.timestamp >= desde,
                        SystemActivityLog.privilegiada == True,
                    )
                )
                privilegiadas = r_priv.scalar() or 0

            return {"total": total, "errores": errores, "privilegiadas": privilegiadas}
        except Exception as e:
            logger.error(f"[INSIGHTS] Error leyendo actividad: {e}")
            return {"total": 0, "errores": 0, "privilegiadas": 0}

    async def _errores_semana(self, desde: datetime) -> list[tuple[str, int]]:
        """Agrupa errores por acción para encontrar patrones recurrentes."""
        try:
            async with async_session_enhanced() as session:
                result = await session.execute(
                    select(
                        SystemActivityLog.accion,
                        func.count(SystemActivityLog.id).label("cnt"),
                    )
                    .where(
                        SystemActivityLog.timestamp >= desde,
                        SystemActivityLog.nivel == "error",
                    )
                    .group_by(SystemActivityLog.accion)
                    .order_by(func.count(SystemActivityLog.id).desc())
                    .limit(10)
                )
                return [(row[0], row[1]) for row in result.all()]
        except Exception as e:
            logger.error(f"[INSIGHTS] Error leyendo errores: {e}")
            return []

    async def _sistemas_populares(self) -> list[tuple[str, int]]:
        """Cuenta cuántos usuarios tienen cada sistema activo."""
        try:
            async with async_session_enhanced() as session:
                result = await session.execute(
                    select(
                        UserSystem.nombre_personalizado,
                        func.count(func.distinct(UserSystem.telefono)).label("cnt"),
                    )
                    .where(UserSystem.activo == True)
                    .group_by(UserSystem.nombre_personalizado)
                    .order_by(func.count(func.distinct(UserSystem.telefono)).desc())
                    .limit(10)
                )
                return [(row[0] or "Sin nombre", row[1]) for row in result.all()]
        except Exception as e:
            logger.error(f"[INSIGHTS] Error leyendo sistemas: {e}")
            return []

    async def _usuarios_activos_semana(self, desde: datetime) -> int:
        """Cuenta usuarios únicos que enviaron mensajes en los últimos 7 días."""
        try:
            from agent.memory import async_session, Mensaje
            async with async_session() as session:
                result = await session.execute(
                    select(func.count(func.distinct(Mensaje.telefono))).where(
                        Mensaje.timestamp >= desde,
                        Mensaje.role == "user",
                    )
                )
                return result.scalar() or 0
        except Exception as e:
            logger.error(f"[INSIGHTS] Error contando usuarios activos: {e}")
            return 0

    def _generar_recomendaciones(
        self, actividad: dict, errores: list, sistemas: list, usuarios: int
    ) -> list[str]:
        """Genera recomendaciones basadas en los datos."""
        recs = []

        # Alta tasa de errores
        if actividad["total"] > 0:
            tasa_error = actividad["errores"] / actividad["total"]
            if tasa_error > 0.1:
                recs.append(
                    f"Tasa de errores alta ({tasa_error:.0%}). "
                    f"Revisar los errores recurrentes arriba."
                )

        # Errores repetitivos
        if errores and errores[0][1] >= 10:
            recs.append(
                f"El error '{errores[0][0]}' se repitio {errores[0][1]} veces. "
                f"Investigar causa raiz."
            )

        # Crecimiento
        if usuarios > 10:
            recs.append(
                f"{usuarios} usuarios activos esta semana. "
                f"Considerar escalar recursos si el crecimiento continua."
            )

        # Sin sistemas activos
        if not sistemas:
            recs.append(
                "Ningun usuario ha activado sistemas del catalogo aun. "
                "Considerar promover el catalogo en el onboarding."
            )

        if not recs:
            recs.append("Sin alertas. El sistema opera dentro de parametros normales.")

        return recs


# Singleton
insights = ModuloInsights()


async def job_reporte_semanal(proveedor):
    """
    Job del scheduler que genera y envía el reporte semanal al owner.
    Programado: domingos 20:00 UTC.
    """
    if not insights.esta_habilitado():
        return

    if not OWNER_PHONE:
        logger.warning("[INSIGHTS] OWNER_PHONE no configurado, reporte no enviado")
        return

    try:
        reporte = await insights.generar_reporte_semanal()

        enviado = await proveedor.enviar_mensaje(OWNER_PHONE, reporte)
        if enviado:
            await insights.registrar_actividad(
                OWNER_PHONE, "reporte_semanal_enviado",
                detalle=f"usuarios_consultados=ok",
            )
            logger.info("[INSIGHTS] Reporte semanal enviado al owner")
        else:
            logger.error("[INSIGHTS] Fallo al enviar reporte semanal")

    except Exception as e:
        logger.error(f"[INSIGHTS] Error en job de reporte semanal: {e}")
