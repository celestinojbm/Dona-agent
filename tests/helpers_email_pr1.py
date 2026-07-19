# tests/helpers_email_pr1.py — Utilidades compartidas de la suite PR 1 email

"""
Fixture-factory y helpers comunes para los tests del Action Center de
correo persistente. Sigue el patrón del repo: env vars + importlib.reload
de los módulos que cachean estado en import-time, SQLite en tmp_path.
"""

import importlib

from sqlalchemy import select


async def preparar_db_email(tmp_path, monkeypatch, nombre_db="email_pr1.db"):
    """Prepara una DB SQLite limpia con ENCRYPTION_KEY válida y devuelve el
    módulo agent.memory recargado."""
    from cryptography.fernet import Fernet

    db_path = tmp_path / nombre_db
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{db_path}")
    monkeypatch.setenv("ENCRYPTION_KEY", Fernet.generate_key().decode())
    monkeypatch.setenv("ENVIRONMENT", "test")
    monkeypatch.delenv("EMAIL_CRYPTO_PERMITIR_PLAINTEXT", raising=False)

    import agent.automation.models as _am
    import agent.business.models as _bm
    import agent.memory
    importlib.reload(agent.memory)
    importlib.reload(_bm)
    importlib.reload(_am)
    await agent.memory.inicializar_db()
    return agent.memory


async def preparar(telefono, key, *, cuerpo="Hola, este es el cuerpo.", destinatario="cliente@ejemplo.com", asunto="Asunto de prueba", thread_id="", reply_message_id=""):
    """Atajo del dominio para preparar un borrador en tests."""
    from agent.automation.email_actions import preparar_envio_correo

    return await preparar_envio_correo(
        telefono,
        destinatario=destinatario,
        asunto=asunto,
        cuerpo=cuerpo,
        thread_id=thread_id,
        reply_message_id=reply_message_id,
        preparation_request_key=key,
    )


async def filas_email(telefono=None):
    """Todas las filas de acciones tipo enviar_correo_gmail (opcionalmente
    filtradas por owner)."""
    from agent.automation.models import AccionAutomatizacion
    from agent.memory import async_session

    async with async_session() as session:
        q = select(AccionAutomatizacion).where(
            AccionAutomatizacion.tipo_accion == "enviar_correo_gmail"
        )
        if telefono is not None:
            q = q.where(AccionAutomatizacion.telefono == telefono)
        res = await session.execute(q)
        return list(res.scalars().all())


async def fila_por_id(accion_id):
    from agent.automation.models import AccionAutomatizacion
    from agent.memory import async_session

    async with async_session() as session:
        res = await session.execute(
            select(AccionAutomatizacion).where(AccionAutomatizacion.id == accion_id)
        )
        return res.scalar_one_or_none()


async def forzar_expiracion(accion_id):
    """Mueve expires_at al pasado (simula TTL vencido sin dormir)."""
    from datetime import datetime, timedelta

    from sqlalchemy import update

    from agent.automation.models import AccionAutomatizacion
    from agent.memory import async_session

    async with async_session() as session:
        await session.execute(
            update(AccionAutomatizacion)
            .where(AccionAutomatizacion.id == accion_id)
            .values(expires_at=datetime.utcnow() - timedelta(minutes=1))
        )
        await session.commit()


async def filas_audit():
    """Todas las filas del audit log de automatización."""
    from agent.automation.models import AuditLogAutomatizacion
    from agent.memory import async_session

    async with async_session() as session:
        res = await session.execute(select(AuditLogAutomatizacion))
        return list(res.scalars().all())
