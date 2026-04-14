# enhanced/safe_module.py — Clase base para todas las habilidades de Dona 2.0

"""
SafeModule: base segura para habilidades avanzadas.

Tres niveles de permisos:
  - "usuario"        → el usuario puede confirmar (afecta solo sus datos)
  - "owner"          → solo OWNER_PHONE puede confirmar (mantenimiento del sistema)
  - "owner_critical" → OWNER_PHONE + doble confirmación (CONFIRMAR + DONA-ADMIN)

Todas las acciones quedan registradas en system_activity_logs.
Cada módulo puede deshabilitarse con feature flags.
"""

import os
import logging
from datetime import datetime
from enum import Enum
from dataclasses import dataclass, field
from typing import Any, Callable, Awaitable

logger = logging.getLogger("dona.enhanced")

OWNER_PHONE = os.getenv("OWNER_PHONE", "")

# Timeout para confirmaciones pendientes (segundos)
CONFIRMACION_TIMEOUT = 300  # 5 minutos


class NivelPermiso(str, Enum):
    USUARIO = "usuario"
    OWNER = "owner"
    OWNER_CRITICAL = "owner_critical"


@dataclass
class AccionConfirmable:
    """Una acción que requiere confirmación antes de ejecutarse."""
    nombre: str
    descripcion: str
    nivel: NivelPermiso
    ejecutar: Callable[..., Awaitable[dict[str, Any]]]
    parametros: dict[str, Any] = field(default_factory=dict)


@dataclass
class ConfirmacionPendiente:
    """Estado de una confirmación en progreso."""
    accion: AccionConfirmable
    telefono: str
    creada: datetime = field(default_factory=lambda: datetime.utcnow())
    primera_confirmacion: bool = False  # True si ya recibió CONFIRMAR (para owner_critical)


# Confirmaciones pendientes por número de teléfono
_confirmaciones: dict[str, ConfirmacionPendiente] = {}


def _normalizar_telefono(telefono: str) -> str:
    """Normaliza un número de teléfono a solo dígitos para comparación."""
    return "".join(c for c in telefono if c.isdigit())


def _es_owner(telefono: str) -> bool:
    """Verifica si el número corresponde al owner. Comparación exacta por dígitos."""
    if not OWNER_PHONE:
        logger.warning("[SAFE] OWNER_PHONE no configurado — acciones owner deshabilitadas")
        return False
    return _normalizar_telefono(telefono) == _normalizar_telefono(OWNER_PHONE)


def _confirmacion_expirada(conf: ConfirmacionPendiente) -> bool:
    """Verifica si una confirmación pendiente ha expirado."""
    ahora = datetime.utcnow()
    return (ahora - conf.creada).total_seconds() > CONFIRMACION_TIMEOUT


class SafeModule:
    """
    Clase base para habilidades de Dona 2.0.

    Provee:
      - Feature flags (activar/desactivar por módulo)
      - Audit logging automático
      - Flujo de confirmación con niveles de permiso
      - Protección contra ejecución no autorizada
    """

    nombre: str = "modulo_base"
    habilitado: bool = True

    def __init__(self):
        flag = os.getenv(f"DONA_FEATURE_{self.nombre.upper()}", "true")
        self.habilitado = flag.lower() in ("true", "1", "yes", "si")

    def esta_habilitado(self) -> bool:
        return self.habilitado

    # ── Audit logging ────────────────────────────────────────────────────────

    async def registrar_actividad(
        self,
        telefono: str,
        accion: str,
        detalle: str = "",
        nivel: str = "info",
        privilegiada: bool = False,
    ):
        """Registra una acción en system_activity_logs."""
        try:
            from enhanced.models import SystemActivityLog, async_session_enhanced
            async with async_session_enhanced() as session:
                log = SystemActivityLog(
                    telefono=telefono,
                    modulo=self.nombre,
                    accion=accion,
                    detalle=detalle[:2000] if detalle else "",
                    nivel=nivel,
                    privilegiada=privilegiada,
                    timestamp=datetime.utcnow(),
                )
                session.add(log)
                await session.commit()
        except Exception as e:
            logger.error(f"[SAFE] Error registrando actividad: {e}")

    # ── Flujo de confirmación ────────────────────────────────────────────────

    def puede_ejecutar(self, telefono: str, nivel: NivelPermiso) -> tuple[bool, str]:
        """
        Verifica si el teléfono tiene permiso para ejecutar una acción de este nivel.
        Retorna (puede, motivo).
        """
        if not self.habilitado:
            return False, f"El módulo {self.nombre} está deshabilitado."

        if nivel == NivelPermiso.USUARIO:
            return True, ""

        if nivel in (NivelPermiso.OWNER, NivelPermiso.OWNER_CRITICAL):
            if not _es_owner(telefono):
                return False, "Esta acción requiere autorización del administrador."

        return True, ""

    async def solicitar_confirmacion(
        self, telefono: str, accion: AccionConfirmable
    ) -> str:
        """
        Inicia el flujo de confirmación para una acción.
        Retorna el mensaje a enviar al usuario pidiendo confirmación.
        """
        puede, motivo = self.puede_ejecutar(telefono, accion.nivel)
        if not puede:
            return motivo

        _confirmaciones[telefono] = ConfirmacionPendiente(
            accion=accion,
            telefono=telefono,
        )

        await self.registrar_actividad(
            telefono, f"confirmacion_solicitada:{accion.nombre}",
            detalle=accion.descripcion,
            nivel="info",
            privilegiada=accion.nivel != NivelPermiso.USUARIO,
        )

        nivel_info = ""
        if accion.nivel == NivelPermiso.OWNER_CRITICAL:
            nivel_info = "\n\n*Esta es una acción crítica.* Requiere doble confirmación:\n1. Escribe *CONFIRMAR*\n2. Luego escribe *DONA-ADMIN*"
        else:
            nivel_info = "\n\nEscribe *CONFIRMAR* para ejecutar o cualquier otra cosa para cancelar."

        return (
            f"*Acción pendiente: {accion.nombre}*\n"
            f"{accion.descripcion}"
            f"{nivel_info}\n\n"
            f"_Expira en 5 minutos._"
        )

    async def procesar_confirmacion(self, telefono: str, texto: str) -> tuple[bool, str]:
        """
        Procesa un mensaje de confirmación.
        Retorna (procesado, mensaje_respuesta).
        procesado=True si el texto era una confirmación/cancelación (consumió el mensaje).
        procesado=False si no había confirmación pendiente.
        """
        conf = _confirmaciones.get(telefono)
        if not conf:
            return False, ""

        # Verificar expiración
        if _confirmacion_expirada(conf):
            del _confirmaciones[telefono]
            await self.registrar_actividad(
                telefono, f"confirmacion_expirada:{conf.accion.nombre}",
                nivel="warning",
            )
            return True, "La confirmación expiró. Si necesitas ejecutar la acción, solicítala de nuevo."

        texto_limpio = texto.strip().upper()

        # Flujo owner_critical: necesita CONFIRMAR y luego DONA-ADMIN
        if conf.accion.nivel == NivelPermiso.OWNER_CRITICAL:
            if not conf.primera_confirmacion:
                if texto_limpio == "CONFIRMAR":
                    conf.primera_confirmacion = True
                    return True, "Primera confirmación recibida. Ahora escribe *DONA-ADMIN* para ejecutar."
                else:
                    del _confirmaciones[telefono]
                    await self.registrar_actividad(
                        telefono, f"confirmacion_cancelada:{conf.accion.nombre}",
                        nivel="info",
                    )
                    return True, "Acción cancelada."
            else:
                if texto_limpio == "DONA-ADMIN":
                    # Ejecutar la acción crítica
                    return await self._ejecutar_accion(telefono, conf)
                else:
                    del _confirmaciones[telefono]
                    await self.registrar_actividad(
                        telefono, f"confirmacion_cancelada:{conf.accion.nombre}",
                        detalle="Segunda confirmación incorrecta",
                        nivel="warning",
                    )
                    return True, "Código incorrecto. Acción cancelada por seguridad."

        # Flujo normal (usuario/owner): solo CONFIRMAR
        if texto_limpio == "CONFIRMAR":
            return await self._ejecutar_accion(telefono, conf)
        else:
            del _confirmaciones[telefono]
            await self.registrar_actividad(
                telefono, f"confirmacion_cancelada:{conf.accion.nombre}",
                nivel="info",
            )
            return True, "Acción cancelada."

    async def _ejecutar_accion(
        self, telefono: str, conf: ConfirmacionPendiente
    ) -> tuple[bool, str]:
        """Ejecuta una acción confirmada y registra el resultado."""
        accion = conf.accion
        del _confirmaciones[telefono]

        try:
            resultado = await accion.ejecutar(**accion.parametros)
            exito = resultado.get("exito", True)
            mensaje = resultado.get("mensaje", "Acción ejecutada.")

            await self.registrar_actividad(
                telefono, f"accion_ejecutada:{accion.nombre}",
                detalle=mensaje[:500],
                nivel="info" if exito else "error",
                privilegiada=accion.nivel != NivelPermiso.USUARIO,
            )

            return True, mensaje

        except Exception as e:
            logger.error(f"[SAFE] Error ejecutando {accion.nombre}: {e}")
            await self.registrar_actividad(
                telefono, f"accion_fallida:{accion.nombre}",
                detalle=str(e)[:500],
                nivel="error",
                privilegiada=accion.nivel != NivelPermiso.USUARIO,
            )
            return True, f"Error al ejecutar la acción: {type(e).__name__}"


def tiene_confirmacion_pendiente(telefono: str) -> bool:
    """Verifica si hay una confirmación pendiente para este número."""
    conf = _confirmaciones.get(telefono)
    if not conf:
        return False
    if _confirmacion_expirada(conf):
        del _confirmaciones[telefono]
        return False
    return True
