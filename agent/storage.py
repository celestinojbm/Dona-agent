# agent/storage.py — Storage de assets creativos (R2 + fallback filesystem)

"""
Capa de almacenamiento de assets (imágenes, videos, audios, webs, docs).

Backend primario: Cloudflare R2 (S3-compatible, sin egress fees).
Backend fallback: filesystem local en `./assets/` — permite desarrollar sin
credenciales y degrada con gracia si R2 está caído o mal configurado.

El llamador NO debe preocuparse por el backend: usa `subir_asset()` y recibe
un `AssetGuardado` con `url_publica` (para WhatsApp) y `key_storage` (para
borrar/reupload después).

Todo asset queda registrado en DB via `registrar_asset()` para auditoría
y billing. Las dos operaciones están separadas a propósito — tests pueden
mockear una sin la otra.
"""

from __future__ import annotations

import os
import json
import uuid
import hashlib
import logging
import mimetypes
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger("dona")


# ── Config ──────────────────────────────────────────────────────────────────

R2_ACCOUNT_ID = os.getenv("R2_ACCOUNT_ID", "")
R2_ACCESS_KEY_ID = os.getenv("R2_ACCESS_KEY_ID", "")
R2_SECRET_ACCESS_KEY = os.getenv("R2_SECRET_ACCESS_KEY", "")
R2_BUCKET = os.getenv("R2_BUCKET", "dona-assets")
R2_PUBLIC_URL = os.getenv("R2_PUBLIC_URL", "").rstrip("/")  # ej: https://assets.dona.app

_FS_ROOT = Path(os.getenv("ASSETS_LOCAL_DIR", "./assets")).resolve()


def _r2_disponible() -> bool:
    """True si hay credenciales completas de R2."""
    return all([R2_ACCOUNT_ID, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, R2_BUCKET])


# ── Tipos ──────────────────────────────────────────────────────────────────

@dataclass
class AssetGuardado:
    """Resultado de `subir_asset`. Lo que el llamador necesita para usar o borrar."""
    url_publica: str
    key_storage: str
    backend: str          # "r2" | "fs"
    mime_type: str
    bytes_size: int


# ── Key scheme ──────────────────────────────────────────────────────────────

def _hash_telefono(telefono: str) -> str:
    """
    Hash corto del teléfono — evita que la key del objeto filtre el número.
    No es secreto (usamos hash sin salt); sólo ofusca a quien mire URLs.
    """
    return hashlib.sha1(telefono.encode("utf-8")).hexdigest()[:12]


def _inferir_extension(mime_type: str, nombre: str = "") -> str:
    """Extensión sin punto. Prioriza el nombre del archivo, cae al MIME."""
    if nombre and "." in nombre:
        ext = nombre.rsplit(".", 1)[-1].lower()
        if 1 <= len(ext) <= 5:
            return ext
    if mime_type:
        guess = mimetypes.guess_extension(mime_type) or ""
        if guess:
            return guess.lstrip(".")
    return "bin"


def construir_key(telefono: str, tipo: str, mime_type: str = "", nombre: str = "") -> str:
    """
    Genera la key de storage: `{hash}/{tipo}/{uuid}.{ext}`.

    `tipo` se sanitiza a [a-z0-9_-] para evitar inyecciones en el path.
    """
    tipo_safe = "".join(c for c in tipo.lower() if c.isalnum() or c in "-_")[:30] or "misc"
    ext = _inferir_extension(mime_type, nombre)
    uid = uuid.uuid4().hex[:16]
    return f"{_hash_telefono(telefono)}/{tipo_safe}/{uid}.{ext}"


# ── Backend: Cloudflare R2 ─────────────────────────────────────────────────

async def _subir_r2(key: str, contenido: bytes, mime_type: str) -> str:
    """
    Sube bytes a R2. Retorna URL pública si `R2_PUBLIC_URL` está seteado,
    sino una URL firmada de corta duración.
    """
    # Import diferido para que el módulo cargue sin aioboto3 instalado
    import aioboto3  # type: ignore

    endpoint = f"https://{R2_ACCOUNT_ID}.r2.cloudflarestorage.com"
    session = aioboto3.Session()
    async with session.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=R2_ACCESS_KEY_ID,
        aws_secret_access_key=R2_SECRET_ACCESS_KEY,
        region_name="auto",
    ) as s3:
        await s3.put_object(
            Bucket=R2_BUCKET,
            Key=key,
            Body=contenido,
            ContentType=mime_type or "application/octet-stream",
        )
        if R2_PUBLIC_URL:
            return f"{R2_PUBLIC_URL}/{key}"
        # Fallback: URL firmada 7 días
        url = await s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": R2_BUCKET, "Key": key},
            ExpiresIn=7 * 24 * 3600,
        )
        return url


async def _borrar_r2(key: str) -> bool:
    try:
        import aioboto3  # type: ignore
        endpoint = f"https://{R2_ACCOUNT_ID}.r2.cloudflarestorage.com"
        session = aioboto3.Session()
        async with session.client(
            "s3",
            endpoint_url=endpoint,
            aws_access_key_id=R2_ACCESS_KEY_ID,
            aws_secret_access_key=R2_SECRET_ACCESS_KEY,
            region_name="auto",
        ) as s3:
            await s3.delete_object(Bucket=R2_BUCKET, Key=key)
        return True
    except Exception as e:
        logger.warning(f"[STORAGE] Error borrando R2 key={key}: {e}")
        return False


# ── Backend: filesystem ─────────────────────────────────────────────────────

def _subir_fs(key: str, contenido: bytes) -> str:
    """Escribe a disco bajo _FS_ROOT y retorna path relativo servible."""
    destino = _FS_ROOT / key
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_bytes(contenido)
    # URL local para dev — no servible externamente, pero el registro queda útil
    return f"file://{destino.as_posix()}"


def _borrar_fs(key: str) -> bool:
    try:
        destino = _FS_ROOT / key
        if destino.exists():
            destino.unlink()
        return True
    except Exception as e:
        logger.warning(f"[STORAGE] Error borrando fs key={key}: {e}")
        return False


# ── API pública ─────────────────────────────────────────────────────────────

async def subir_asset(
    telefono: str,
    tipo: str,
    contenido: bytes,
    mime_type: str = "",
    nombre_sugerido: str = "",
) -> AssetGuardado:
    """
    Sube bytes al backend configurado y retorna `AssetGuardado`.

    NO registra en DB — para eso llama `registrar_asset()` después (o usá
    `subir_y_registrar()` para el camino común).
    """
    if not contenido:
        raise ValueError("contenido vacío")
    if not mime_type and nombre_sugerido:
        mime_type = mimetypes.guess_type(nombre_sugerido)[0] or ""

    key = construir_key(telefono, tipo, mime_type, nombre_sugerido)

    if _r2_disponible():
        try:
            url = await _subir_r2(key, contenido, mime_type)
            return AssetGuardado(
                url_publica=url, key_storage=key, backend="r2",
                mime_type=mime_type, bytes_size=len(contenido),
            )
        except Exception as e:
            logger.error(f"[STORAGE] R2 falló ({e}) — usando filesystem fallback")

    url = _subir_fs(key, contenido)
    return AssetGuardado(
        url_publica=url, key_storage=key, backend="fs",
        mime_type=mime_type, bytes_size=len(contenido),
    )


async def registrar_asset(
    telefono: str,
    tipo: str,
    guardado: AssetGuardado,
    prompt: str = "",
    modelo: str = "",
    costo_usd: float = 0.0,
    costo_creditos: int = 0,
    meta: dict[str, Any] | None = None,
) -> int:
    """
    Inserta el registro en DB. Retorna el ID del asset.
    """
    from agent.memory import async_session, AssetGenerado

    async with async_session() as session:
        row = AssetGenerado(
            telefono=telefono,
            tipo=tipo,
            url_publica=guardado.url_publica,
            key_storage=guardado.key_storage,
            backend=guardado.backend,
            prompt=(prompt or "")[:4000],
            modelo=modelo[:80],
            costo_usd=f"{costo_usd:.6f}" if costo_usd else "0",
            costo_creditos=int(costo_creditos),
            mime_type=guardado.mime_type[:80],
            bytes_size=int(guardado.bytes_size),
            meta_json=json.dumps(meta or {}, ensure_ascii=False)[:16000],
            creado=datetime.utcnow(),
        )
        session.add(row)
        await session.commit()
        await session.refresh(row)
        return row.id


async def subir_y_registrar(
    telefono: str,
    tipo: str,
    contenido: bytes,
    mime_type: str = "",
    nombre_sugerido: str = "",
    prompt: str = "",
    modelo: str = "",
    costo_usd: float = 0.0,
    costo_creditos: int = 0,
    meta: dict[str, Any] | None = None,
) -> tuple[AssetGuardado, int]:
    """Atajo: sube + registra en un solo call. Retorna (guardado, asset_id)."""
    guardado = await subir_asset(telefono, tipo, contenido, mime_type, nombre_sugerido)
    asset_id = await registrar_asset(
        telefono=telefono, tipo=tipo, guardado=guardado,
        prompt=prompt, modelo=modelo,
        costo_usd=costo_usd, costo_creditos=costo_creditos, meta=meta,
    )
    return guardado, asset_id


async def obtener_asset(asset_id: int) -> dict | None:
    """Recupera un asset por ID. Retorna dict con campos relevantes o None."""
    from agent.memory import async_session, AssetGenerado
    from sqlalchemy import select

    async with async_session() as session:
        row = (await session.execute(select(AssetGenerado).where(AssetGenerado.id == asset_id))).scalar_one_or_none()
        if not row:
            return None
        return _asset_a_dict(row)


async def listar_assets_usuario(telefono: str, limite: int = 10, tipo: str | None = None) -> list[dict]:
    """Últimos N assets del usuario, opcionalmente filtrados por tipo."""
    from agent.memory import async_session, AssetGenerado
    from sqlalchemy import select

    async with async_session() as session:
        q = select(AssetGenerado).where(AssetGenerado.telefono == telefono)
        if tipo:
            q = q.where(AssetGenerado.tipo == tipo)
        q = q.order_by(AssetGenerado.creado.desc()).limit(limite)
        rows = (await session.execute(q)).scalars().all()
        return [_asset_a_dict(r) for r in rows]


async def eliminar_asset(asset_id: int, telefono: str) -> bool:
    """
    Borra el asset del backend y lo marca en DB. El telefono se verifica
    para que un user no pueda borrar assets de otro (defensa en profundidad).
    """
    from agent.memory import async_session, AssetGenerado
    from sqlalchemy import select, delete

    async with async_session() as session:
        row = (await session.execute(
            select(AssetGenerado).where(
                AssetGenerado.id == asset_id,
                AssetGenerado.telefono == telefono,
            )
        )).scalar_one_or_none()
        if not row:
            return False
        # Borrar del backend (best-effort, no falla el delete si storage ya no tiene el objeto)
        if row.backend == "r2":
            await _borrar_r2(row.key_storage)
        else:
            _borrar_fs(row.key_storage)
        await session.execute(delete(AssetGenerado).where(AssetGenerado.id == asset_id))
        await session.commit()
        return True


def _asset_a_dict(row) -> dict:
    try:
        meta = json.loads(row.meta_json or "{}")
    except Exception:
        meta = {}
    return {
        "id": row.id,
        "telefono": row.telefono,
        "tipo": row.tipo,
        "url": row.url_publica,
        "key": row.key_storage,
        "backend": row.backend,
        "prompt": row.prompt,
        "modelo": row.modelo,
        "costo_usd": row.costo_usd,
        "costo_creditos": row.costo_creditos,
        "mime_type": row.mime_type,
        "bytes": row.bytes_size,
        "meta": meta,
        "creado": row.creado.isoformat() if row.creado else None,
    }
