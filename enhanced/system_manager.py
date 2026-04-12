# enhanced/system_manager.py — Gestor de sistemas de usuario

"""
Habilidad 3: Ciclo de vida de sistemas de usuario.

Responsabilidades:
  - Instanciar un sistema del catálogo para un usuario
  - Listar sistemas activos del usuario
  - Interactuar con un sistema (agregar datos, consultar)
  - Desactivar un sistema (nivel usuario, requiere CONFIRMAR)
"""

import json
import logging
from datetime import datetime
from sqlalchemy import select, update

from enhanced.safe_module import SafeModule, NivelPermiso, AccionConfirmable
from enhanced.models import UserSystem, SystemCatalog, async_session_enhanced
from enhanced.catalog import obtener_sistema_por_id

logger = logging.getLogger("dona.enhanced")


class GestorSistemas(SafeModule):
    nombre = "sistemas"

    async def instanciar_sistema(self, telefono: str, catalog_id: int) -> str:
        """
        Crea una instancia de un sistema del catálogo para el usuario.
        Retorna mensaje de confirmación o error.
        """
        # Verificar que el sistema existe en el catálogo
        sistema = await obtener_sistema_por_id(catalog_id)
        if not sistema:
            return "No encontré ese sistema en el catálogo."

        # Verificar si el usuario ya tiene este sistema activo
        async with async_session_enhanced() as session:
            result = await session.execute(
                select(UserSystem).where(
                    UserSystem.telefono == telefono,
                    UserSystem.catalog_id == catalog_id,
                    UserSystem.activo == True,
                )
            )
            existente = result.scalar()
            if existente:
                return f"Ya tienes *{sistema['nombre']}* activo. Di '*mis sistemas*' para verlo."

            # Crear instancia con la plantilla del catálogo
            nuevo = UserSystem(
                telefono=telefono,
                catalog_id=catalog_id,
                nombre_personalizado=sistema["nombre"],
                datos_json=json.dumps(sistema["plantilla"], ensure_ascii=False),
            )
            session.add(nuevo)
            await session.commit()

        await self.registrar_actividad(
            telefono, f"sistema_instanciado:{sistema['nombre']}",
            detalle=f"catalog_id={catalog_id}",
        )

        instrucciones = sistema["plantilla"].get("instrucciones", "")
        return (
            f"*{sistema['nombre']}* activado\n\n"
            f"{sistema['descripcion']}\n\n"
            f"{instrucciones}"
        )

    async def listar_sistemas_usuario(self, telefono: str) -> str:
        """Lista todos los sistemas activos del usuario."""
        async with async_session_enhanced() as session:
            result = await session.execute(
                select(UserSystem).where(
                    UserSystem.telefono == telefono,
                    UserSystem.activo == True,
                )
            )
            sistemas = result.scalars().all()

        if not sistemas:
            return (
                "No tienes sistemas activos todavía.\n\n"
                "Di '*catálogo*' o '*qué sistemas hay*' para ver los disponibles."
            )

        lineas = ["*Tus sistemas activos:*\n"]
        for s in sistemas:
            nombre = s.nombre_personalizado or f"Sistema #{s.catalog_id}"
            lineas.append(f"  {nombre}")

        lineas.append(f"\nTotal: {len(sistemas)}")
        return "\n".join(lineas)

    async def obtener_datos_sistema(self, telefono: str, catalog_id: int) -> dict | None:
        """Obtiene los datos JSON de un sistema del usuario."""
        async with async_session_enhanced() as session:
            result = await session.execute(
                select(UserSystem).where(
                    UserSystem.telefono == telefono,
                    UserSystem.catalog_id == catalog_id,
                    UserSystem.activo == True,
                )
            )
            sistema = result.scalar()
            if not sistema:
                return None
            return {
                "id": sistema.id,
                "nombre": sistema.nombre_personalizado,
                "datos": json.loads(sistema.datos_json),
                "creado": sistema.creado.isoformat() if sistema.creado else None,
            }

    async def actualizar_datos_sistema(
        self, telefono: str, catalog_id: int, datos: dict
    ) -> bool:
        """Actualiza los datos JSON de un sistema del usuario."""
        async with async_session_enhanced() as session:
            result = await session.execute(
                select(UserSystem).where(
                    UserSystem.telefono == telefono,
                    UserSystem.catalog_id == catalog_id,
                    UserSystem.activo == True,
                )
            )
            sistema = result.scalar()
            if not sistema:
                return False

            sistema.datos_json = json.dumps(datos, ensure_ascii=False)
            sistema.actualizado = datetime.utcnow()
            await session.commit()

        return True

    async def solicitar_desactivacion(self, telefono: str, catalog_id: int) -> str:
        """
        Inicia el flujo de confirmación para desactivar un sistema.
        Nivel: usuario (solo afecta sus propios datos).
        """
        sistema_info = await self.obtener_datos_sistema(telefono, catalog_id)
        if not sistema_info:
            return "No encontré ese sistema en tus sistemas activos."

        nombre = sistema_info["nombre"]

        async def _ejecutar_desactivacion(**kwargs):
            _tel = kwargs["telefono"]
            _cid = kwargs["catalog_id"]
            async with async_session_enhanced() as session:
                await session.execute(
                    update(UserSystem)
                    .where(
                        UserSystem.telefono == _tel,
                        UserSystem.catalog_id == _cid,
                        UserSystem.activo == True,
                    )
                    .values(activo=False)
                )
                await session.commit()
            return {"exito": True, "mensaje": f"*{nombre}* desactivado. Tus datos se conservan por si quieres reactivarlo."}

        accion = AccionConfirmable(
            nombre=f"Desactivar {nombre}",
            descripcion=f"Se desactivará tu sistema *{nombre}*. Tus datos no se borran.",
            nivel=NivelPermiso.USUARIO,
            ejecutar=_ejecutar_desactivacion,
            parametros={"telefono": telefono, "catalog_id": catalog_id},
        )

        return await self.solicitar_confirmacion(telefono, accion)

    def formatear_catalogo(self, catalogo: list[dict]) -> str:
        """Formatea el catálogo completo para mostrarlo al usuario."""
        if not catalogo:
            return "El catálogo está vacío."

        # Agrupar por categoría
        por_categoria: dict[str, list] = {}
        for s in catalogo:
            cat = s["categoria"]
            por_categoria.setdefault(cat, []).append(s)

        iconos = {
            "habitos": "🔄", "finanzas": "💰", "salud": "💪",
            "productividad": "🎯", "aprendizaje": "📚", "social": "👥",
            "hogar": "🏠", "negocio": "💼",
        }

        lineas = ["*Sistemas disponibles:*\n"]
        for cat, sistemas in por_categoria.items():
            icono = iconos.get(cat, "📌")
            lineas.append(f"{icono} *{cat.capitalize()}*")
            for s in sistemas:
                lineas.append(f"  - {s['nombre']}")
            lineas.append("")

        lineas.append(
            'Para activar uno, di algo como:\n'
            '"quiero organizar mis gastos"\n'
            '"activa el tracker de hábitos"\n'
            '"necesito un CRM simple"'
        )
        return "\n".join(lineas)


# Singleton
gestor_sistemas = GestorSistemas()
