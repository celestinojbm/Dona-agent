# agent/creativos/bg_remove.py — Quitar fondo (Photoroom)

"""
Integración con Photoroom SDK para eliminar el fondo de una imagen.

Diseño (sigue el patrón de `imagen.py`):
  - `remove_background()` es la capa pura: recibe bytes de la imagen,
    retorna `(bytes, meta)`. Mockeable con httpx en tests.
  - `preparar_bg_remove_*` / `confirmar_bg_remove` implementan el flujo
    de 2 pasos (naming LITERAL: preparar → confirmar) para no gatillar
    alucinación de éxito en el LLM.
  - Hay DOS formas de preparar:
      a) `preparar_bg_remove_desde_bytes(telefono, source_bytes, mime)` —
         usado cuando el usuario manda una foto con caption "quita el fondo".
         Sube el source a R2 primero y guarda la URL (porque `queue.py`
         serializa params con json.dumps y no tolera bytes).
      b) `preparar_bg_remove_desde_ultimo_asset(telefono)` — usado cuando
         el usuario dice "quita el fondo a la última imagen". Busca el
         último asset de tipo image y reutiliza su URL.
  - Si `PHOTOROOM_API_KEY` no está seteada, `remove_background` retorna
    el mismo PNG de entrada sin tocar (dev/tests).
"""

from __future__ import annotations

import os
import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta

logger = logging.getLogger("dona")


# ── Config ──────────────────────────────────────────────────────────────────

PHOTOROOM_ENDPOINT = os.getenv(
    "PHOTOROOM_ENDPOINT",
    "https://sdk.photoroom.com/v1/segment",
)
REQUEST_TIMEOUT_S = float(os.getenv("PHOTOROOM_TIMEOUT", "60"))
MAX_RETRIES = int(os.getenv("PHOTOROOM_RETRIES", "2"))

PENDIENTE_TTL_MIN = int(os.getenv("BG_REMOVE_PENDIENTE_TTL_MIN", "15"))


class PhotoroomError(Exception):
    """Error genérico del provider (timeout, 4xx/5xx, respuesta vacía)."""


# ── Low-level: llamada HTTP ─────────────────────────────────────────────────

async def remove_background(
    image_bytes: bytes,
    mime_type: str = "image/png",
    api_key: str | None = None,
) -> tuple[bytes, dict]:
    """
    Envía la imagen a Photoroom y retorna `(png_bytes_sin_fondo, meta)`.

    `meta` incluye `modelo`, `mime_type` (siempre image/png — Photoroom
    devuelve transparente) y `bytes_size`.

    Lanza `PhotoroomError` si falla tras reintentos.

    Si no hay `PHOTOROOM_API_KEY` configurada, retorna la imagen original
    sin transformar — útil en dev/tests.
    """
    if not image_bytes:
        raise ValueError("image_bytes vacío")

    key = api_key if api_key is not None else os.getenv("PHOTOROOM_API_KEY", "")

    if not key:
        logger.warning("[BG_REMOVE] PHOTOROOM_API_KEY no configurada — devolviendo imagen original")
        return image_bytes, {
            "modelo": "placeholder",
            "mime_type": mime_type or "image/png",
            "bytes_size": len(image_bytes),
            "placeholder": True,
        }

    import httpx  # import diferido para mockear en tests

    headers = {
        "x-api-key": key,
        "Accept": "image/png, application/json",
    }
    files = {
        "image_file": ("input.png", image_bytes, mime_type or "image/png"),
    }

    ultimo_error: Exception | None = None
    for intento in range(MAX_RETRIES + 1):
        try:
            async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT_S) as client:
                resp = await client.post(PHOTOROOM_ENDPOINT, headers=headers, files=files)

            if resp.status_code >= 500:
                raise PhotoroomError(f"Photoroom 5xx: {resp.status_code} {resp.text[:200]}")
            if resp.status_code >= 400:
                # 4xx típicamente: key inválida, cuota, formato no soportado
                raise PhotoroomError(f"Photoroom {resp.status_code}: {resp.text[:200]}")

            content = resp.content
            if not content or len(content) < 100:
                raise PhotoroomError(f"Respuesta Photoroom vacía o inválida ({len(content)} bytes)")

            resp_mime = resp.headers.get("content-type", "image/png").split(";")[0].strip()

            return content, {
                "modelo": "photoroom-sdk-segment",
                "mime_type": resp_mime or "image/png",
                "bytes_size": len(content),
                "placeholder": False,
            }

        except PhotoroomError as e:
            ultimo_error = e
            if "4" in str(e)[:14] and "5" not in str(e)[:14]:
                break
            if intento < MAX_RETRIES:
                backoff = 2 ** intento
                logger.warning(f"[BG_REMOVE] intento {intento+1} falló ({e}); reintentando en {backoff}s")
                await asyncio.sleep(backoff)
        except Exception as e:
            ultimo_error = PhotoroomError(f"{type(e).__name__}: {e}")
            if intento < MAX_RETRIES:
                await asyncio.sleep(2 ** intento)

    raise ultimo_error or PhotoroomError("fallo desconocido")


# ── Pendientes en memoria (preparar → confirmar) ────────────────────────────

@dataclass
class BgRemovePendiente:
    telefono: str
    source_url: str
    source_mime: str
    source_asset_id: int | None  # None si es un upload fresco no registrado aún
    costo_creditos: int
    creado: datetime = field(default_factory=datetime.utcnow)

    def expirado(self) -> bool:
        return datetime.utcnow() - self.creado > timedelta(minutes=PENDIENTE_TTL_MIN)


_PENDIENTES: dict[str, BgRemovePendiente] = {}


def obtener_pendiente(telefono: str) -> BgRemovePendiente | None:
    p = _PENDIENTES.get(telefono)
    if p is None:
        return None
    if p.expirado():
        _PENDIENTES.pop(telefono, None)
        return None
    return p


# ── API 2 pasos ─────────────────────────────────────────────────────────────

async def preparar_bg_remove_desde_bytes(
    telefono: str,
    source_bytes: bytes,
    source_mime: str = "image/jpeg",
) -> dict:
    """
    Sube la imagen fuente a R2 (o FS fallback), la registra como asset
    del usuario (tipo "image_source") y guarda el pendiente con la URL.

    Se usa cuando el usuario envía una foto con caption "quita el fondo".

    Retorna dict con datos para preview al usuario (costo, saldo, alcanza).
    NO cobra, NO procesa.
    """
    from agent.billing import COSTO_BG_REMOVE, obtener_saldo
    from agent import storage
    from agent.creativos.pendientes import cancelar_otros_pendientes

    if not source_bytes:
        raise ValueError("source_bytes vacío")

    # Un solo pendiente activo por teléfono — si había otro, lo reemplazamos.
    reemplazo = cancelar_otros_pendientes(telefono, excepto="bg_remove")

    # Subir y registrar el source — así el usuario puede re-usarlo luego
    # ("quita el fondo a la última imagen" funciona incluso después de un
    # restart del worker).
    guardado, asset_id = await storage.subir_y_registrar(
        telefono=telefono,
        tipo="image_source",
        contenido=source_bytes,
        mime_type=source_mime or "image/jpeg",
        nombre_sugerido="source.jpg",
        prompt="(subida por el usuario)",
        modelo="whatsapp-upload",
        meta={"fuente": "whatsapp_inbound"},
    )

    costo = COSTO_BG_REMOVE
    saldo = await obtener_saldo(telefono)

    pendiente = BgRemovePendiente(
        telefono=telefono,
        source_url=guardado.url_publica,
        source_mime=guardado.mime_type or source_mime or "image/jpeg",
        source_asset_id=asset_id,
        costo_creditos=costo,
    )
    _PENDIENTES[telefono] = pendiente

    logger.info(
        f"[BG_REMOVE] preparar desde bytes → {telefono} asset_id={asset_id} "
        f"backend={guardado.backend} costo={costo}"
    )

    return {
        "source_url": guardado.url_publica,
        "source_backend": guardado.backend,
        "source_asset_id": asset_id,
        "costo_creditos": costo,
        "saldo_actual": saldo,
        "alcanza": saldo >= costo,
        "ttl_min": PENDIENTE_TTL_MIN,
        "reemplazo": reemplazo,
    }


async def preparar_bg_remove_desde_ultimo_asset(telefono: str) -> dict:
    """
    Busca el último asset tipo "image" o "image_source" del usuario y prepara
    bg_remove sobre él.

    Retorna:
      - {"estado": "sin_imagen"} si el usuario no tiene ninguna imagen previa
      - {"estado": "source_no_servible"} si la imagen existe pero está en fs://
        (no servible externamente — Photoroom necesita URL https o bytes, y no
        queremos duplicar la descarga-y-subida acá)
      - {"estado": "ok", ...} con el preview normal
    """
    from agent.billing import COSTO_BG_REMOVE, obtener_saldo
    from agent import storage
    from agent.creativos.pendientes import cancelar_otros_pendientes

    assets = await storage.listar_assets_usuario(telefono, limite=10, tipo=None)
    source = None
    for a in assets:
        if a.get("tipo") in ("image", "image_source") and a.get("url_publica"):
            source = a
            break

    if not source:
        logger.info(f"[BG_REMOVE] sin_imagen → {telefono}")
        return {"estado": "sin_imagen"}

    url = source["url_publica"]
    if url.startswith("file://") or url.startswith("fs://"):
        # Imagen en backend local: no la puede consumir Photoroom
        logger.warning(f"[BG_REMOVE] source_no_servible → {telefono} url={url[:80]}")
        return {"estado": "source_no_servible"}

    # Un solo pendiente activo por teléfono — si había otro, lo reemplazamos.
    reemplazo = cancelar_otros_pendientes(telefono, excepto="bg_remove")

    costo = COSTO_BG_REMOVE
    saldo = await obtener_saldo(telefono)

    pendiente = BgRemovePendiente(
        telefono=telefono,
        source_url=url,
        source_mime=source.get("mime_type") or "image/jpeg",
        source_asset_id=source.get("id"),
        costo_creditos=costo,
    )
    _PENDIENTES[telefono] = pendiente

    logger.info(
        f"[BG_REMOVE] preparar desde ultimo_asset → {telefono} "
        f"asset_id={source.get('id')} costo={costo}"
    )

    return {
        "estado": "ok",
        "source_url": url,
        "source_asset_id": source.get("id"),
        "costo_creditos": costo,
        "saldo_actual": saldo,
        "alcanza": saldo >= costo,
        "ttl_min": PENDIENTE_TTL_MIN,
        "reemplazo": reemplazo,
    }


async def confirmar_bg_remove(telefono: str) -> dict:
    """
    Cobra créditos y encola job `bg_remove`.
    Retorna `{"estado": "ok"|"sin_pendiente"|"saldo_insuficiente", ...}`.
    """
    pendiente = obtener_pendiente(telefono)
    if pendiente is None:
        return {"estado": "sin_pendiente"}

    from agent.billing import cobrar_o_rechazar
    from agent.jobs import encolar

    ok, err = await cobrar_o_rechazar(
        telefono,
        pendiente.costo_creditos,
        "bg_remove",
    )
    if not ok:
        return {"estado": "saldo_insuficiente", "mensaje": err}

    job_id = await encolar(
        "bg_remove",
        telefono,
        {
            "source_url": pendiente.source_url,
            "source_mime": pendiente.source_mime,
            "source_asset_id": pendiente.source_asset_id,
            "costo_creditos": pendiente.costo_creditos,
        },
    )
    _PENDIENTES.pop(telefono, None)
    return {"estado": "ok", "job_id": job_id}


def cancelar_bg_remove(telefono: str) -> bool:
    """Descarta el pendiente sin cobrar. Retorna True si había uno."""
    return _PENDIENTES.pop(telefono, None) is not None
