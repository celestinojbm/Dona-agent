# agent/creativos/video_avatar.py — Video con avatar (HeyGen)

"""
Integración con HeyGen para generar videos con un presentador AI que lee un
guion. Caso de uso típico: UGC/marketing rápido para el negocio del usuario.

Diseño (mismo patrón que video.py):
  - `generar_video_avatar()` crea el job en HeyGen, poll hasta completed,
    descarga el MP4. Retorna `(bytes, meta)`.
  - `preparar_video_avatar()` / `confirmar_video_avatar()` flujo 2 pasos.
  - `HEYGEN_AVATAR_ID` y `HEYGEN_VOICE_ID` configurables por env (HeyGen pide
    IDs específicos — no hay "default universal"; el usuario debe elegir).
  - Costo plano `COSTO_VIDEO_AVATAR` (80 cr).
  - Sin key → MP4 stub.
"""

from __future__ import annotations

import os
import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta

logger = logging.getLogger("dona")


# ── Config ──────────────────────────────────────────────────────────────────

HEYGEN_API_BASE = os.getenv("HEYGEN_API_BASE", "https://api.heygen.com")

# IDs por defecto — el usuario debe configurarlos en su dashboard de HeyGen.
# HeyGen ofrece avatars/voices públicos; los siguientes IDs son placeholder
# (generalmente expirados). Sin configurar, el provider retorna stub.
HEYGEN_AVATAR_ID = os.getenv("HEYGEN_AVATAR_ID", "")
HEYGEN_VOICE_ID = os.getenv("HEYGEN_VOICE_ID", "")
# Locale de la voz (es-MX, es-419, es-AR, etc.). Solo aplica a voces que
# soportan `support_locale=true`. Vacío → HeyGen usa el acento default de la voz.
HEYGEN_VOICE_LOCALE = os.getenv("HEYGEN_VOICE_LOCALE", "")
HEYGEN_BACKGROUND = os.getenv("HEYGEN_BACKGROUND", "#F5F5F5")
HEYGEN_DIMENSION_W = int(os.getenv("HEYGEN_DIMENSION_W", "720"))
HEYGEN_DIMENSION_H = int(os.getenv("HEYGEN_DIMENSION_H", "1280"))

CREATE_TIMEOUT_S = float(os.getenv("HEYGEN_CREATE_TIMEOUT", "30"))
POLL_TIMEOUT_S = float(os.getenv("HEYGEN_POLL_TIMEOUT", "600"))  # 10 min
POLL_INTERVAL_S = float(os.getenv("HEYGEN_POLL_INTERVAL", "5"))
DOWNLOAD_TIMEOUT_S = float(os.getenv("HEYGEN_DOWNLOAD_TIMEOUT", "180"))

PENDIENTE_TTL_MIN = int(os.getenv("VIDEO_AVATAR_PENDIENTE_TTL_MIN", "15"))

MAX_SCRIPT_CHARS = int(os.getenv("VIDEO_AVATAR_MAX_CHARS", "1500"))


_STUB_MP4 = (
    b"\x00\x00\x00\x20ftypisom\x00\x00\x02\x00isomiso2avc1mp41"
    + b"\x00" * 128
)


class HeyGenError(Exception):
    """Error genérico del provider."""


# ── HTTP helpers ────────────────────────────────────────────────────────────

def _headers(api_key: str) -> dict:
    return {
        "X-Api-Key": api_key,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def _payload(texto: str, avatar_id: str, voice_id: str, locale: str = "") -> dict:
    voice_obj: dict = {
        "type": "text",
        "input_text": texto[:MAX_SCRIPT_CHARS],
        "voice_id": voice_id,
    }
    if locale:
        voice_obj["locale"] = locale
    return {
        "video_inputs": [
            {
                "character": {
                    "type": "avatar",
                    "avatar_id": avatar_id,
                    "avatar_style": "normal",
                },
                "voice": voice_obj,
                "background": {
                    "type": "color",
                    "value": HEYGEN_BACKGROUND,
                },
            }
        ],
        "dimension": {
            "width": HEYGEN_DIMENSION_W,
            "height": HEYGEN_DIMENSION_H,
        },
    }


async def _crear(client, api_key: str, payload: dict) -> str:
    endpoint = f"{HEYGEN_API_BASE}/v2/video/generate"
    resp = await client.post(endpoint, headers=_headers(api_key), json=payload)
    if resp.status_code >= 500:
        raise HeyGenError(f"HeyGen 5xx: {resp.status_code} {resp.text[:200]}")
    if resp.status_code == 402:
        raise HeyGenError("HeyGen: saldo insuficiente en la cuenta del proveedor")
    if resp.status_code >= 400:
        raise HeyGenError(f"HeyGen {resp.status_code}: {resp.text[:200]}")
    try:
        data = resp.json()
    except Exception as e:
        raise HeyGenError(f"Respuesta no-JSON de HeyGen: {e}")
    video_id = (data.get("data") or {}).get("video_id") or data.get("video_id") or ""
    if not video_id:
        raise HeyGenError(f"Respuesta HeyGen sin video_id: {str(data)[:200]}")
    return video_id


async def _poll(client, api_key: str, video_id: str) -> dict:
    """Devuelve el dict final con status in (completed, failed)."""
    endpoint = f"{HEYGEN_API_BASE}/v1/video_status.get"
    deadline = asyncio.get_event_loop().time() + POLL_TIMEOUT_S
    while True:
        if asyncio.get_event_loop().time() > deadline:
            raise HeyGenError("Timeout esperando el video de HeyGen")
        resp = await client.get(
            endpoint, headers=_headers(api_key), params={"video_id": video_id},
        )
        if resp.status_code >= 400:
            raise HeyGenError(f"HeyGen poll {resp.status_code}: {resp.text[:200]}")
        data = (resp.json().get("data") or {})
        status = (data.get("status") or "").lower()
        if status in ("completed", "failed", "error"):
            return data
        await asyncio.sleep(POLL_INTERVAL_S)


async def _descargar(client, url: str) -> bytes:
    resp = await client.get(url, follow_redirects=True)
    if resp.status_code != 200:
        raise HeyGenError(f"Descarga falló: {resp.status_code}")
    return resp.content


# ── Capa pura ──────────────────────────────────────────────────────────────

async def generar_video_avatar(
    texto: str,
    avatar_id: str = "",
    voice_id: str = "",
    locale: str = "",
    api_key: str | None = None,
) -> tuple[bytes, dict]:
    """
    Genera un video con avatar AI leyendo `texto`. Retorna `(mp4_bytes, meta)`.
    Sin key o sin avatar/voice ID configurados → MP4 stub.
    `locale` opcional (ej: "es-MX") fuerza acento en voces que lo soportan.
    """
    texto = (texto or "").strip()
    if not texto:
        raise ValueError("texto vacío")
    texto = texto[:MAX_SCRIPT_CHARS]

    key = api_key if api_key is not None else os.getenv("HEYGEN_API_KEY", "")
    aid = avatar_id or HEYGEN_AVATAR_ID
    vid = voice_id or HEYGEN_VOICE_ID
    loc = locale or HEYGEN_VOICE_LOCALE

    if not key or not aid or not vid:
        logger.warning(
            "[VIDEO_AVATAR] Falta HEYGEN_API_KEY/AVATAR_ID/VOICE_ID — usando stub MP4"
        )
        return _STUB_MP4, {
            "modelo": "placeholder",
            "mime_type": "video/mp4",
            "bytes_size": len(_STUB_MP4),
            "placeholder": True,
            "texto": texto,
            "avatar_id": aid,
            "voice_id": vid,
            "locale": loc,
        }

    import httpx

    payload = _payload(texto, aid, vid, locale=loc)

    async with httpx.AsyncClient(timeout=CREATE_TIMEOUT_S) as client:
        video_id = await _crear(client, key, payload)

    async with httpx.AsyncClient(timeout=POLL_TIMEOUT_S + 30) as client:
        final = await _poll(client, key, video_id)

    status = (final.get("status") or "").lower()
    if status != "completed":
        err = final.get("error") or f"status={status}"
        raise HeyGenError(f"Video HeyGen no exitoso: {str(err)[:200]}")

    url_video = final.get("video_url") or ""
    if not url_video:
        raise HeyGenError(f"Video HeyGen sin URL: {str(final)[:200]}")

    async with httpx.AsyncClient(timeout=DOWNLOAD_TIMEOUT_S) as client:
        video_bytes = await _descargar(client, url_video)

    if not video_bytes or len(video_bytes) < 1000:
        raise HeyGenError(f"Video HeyGen demasiado pequeño ({len(video_bytes)}B)")

    return video_bytes, {
        "modelo": "heygen",
        "mime_type": "video/mp4",
        "bytes_size": len(video_bytes),
        "placeholder": False,
        "texto": texto,
        "avatar_id": aid,
        "voice_id": vid,
        "locale": loc,
        "video_id": video_id,
        "source_url": url_video,
        "duracion_s": final.get("duration"),
    }


# ── Pendientes ─────────────────────────────────────────────────────────────

@dataclass
class VideoAvatarPendiente:
    telefono: str
    texto: str
    avatar_id: str
    voice_id: str
    costo_creditos: int
    creado: datetime = field(default_factory=datetime.utcnow)

    def expirado(self) -> bool:
        return datetime.utcnow() - self.creado > timedelta(minutes=PENDIENTE_TTL_MIN)


_PENDIENTES: dict[str, VideoAvatarPendiente] = {}


def obtener_pendiente(telefono: str) -> VideoAvatarPendiente | None:
    p = _PENDIENTES.get(telefono)
    if p is None:
        return None
    if p.expirado():
        _PENDIENTES.pop(telefono, None)
        return None
    return p


# ── API 2 pasos ─────────────────────────────────────────────────────────────

async def preparar_video_avatar(
    telefono: str,
    texto: str,
    avatar_id: str = "",
    voice_id: str = "",
) -> dict:
    from agent.billing import obtener_saldo, COSTO_VIDEO_AVATAR

    texto = (texto or "").strip()
    if not texto:
        raise ValueError("texto vacío")
    texto = texto[:MAX_SCRIPT_CHARS]

    costo = COSTO_VIDEO_AVATAR
    saldo = await obtener_saldo(telefono)
    aid = avatar_id or HEYGEN_AVATAR_ID
    vid = voice_id or HEYGEN_VOICE_ID

    # Solo puede haber UN pendiente activo por teléfono. Si había otro,
    # lo cancelamos y reportamos para mostrarlo en el preview.
    from agent.creativos.pendientes import cancelar_otros_pendientes
    reemplazo = cancelar_otros_pendientes(telefono, excepto="video_avatar")

    pendiente = VideoAvatarPendiente(
        telefono=telefono,
        texto=texto,
        avatar_id=aid,
        voice_id=vid,
        costo_creditos=costo,
    )
    _PENDIENTES[telefono] = pendiente

    return {
        "texto": texto,
        "avatar_id": aid,
        "voice_id": vid,
        "chars": len(texto),
        "costo_creditos": costo,
        "saldo_actual": saldo,
        "alcanza": saldo >= costo,
        "ttl_min": PENDIENTE_TTL_MIN,
        "sin_configurar": not (aid and vid),
        "reemplazo": reemplazo,
    }


async def confirmar_video_avatar(telefono: str) -> dict:
    pendiente = obtener_pendiente(telefono)
    if pendiente is None:
        return {"estado": "sin_pendiente"}

    from agent.billing import cobrar_o_rechazar
    from agent.jobs import encolar

    ok, err = await cobrar_o_rechazar(
        telefono,
        pendiente.costo_creditos,
        f"gen_video_avatar ({pendiente.costo_creditos}cr, {len(pendiente.texto)}ch)",
    )
    if not ok:
        return {"estado": "saldo_insuficiente", "mensaje": err}

    job_id = await encolar(
        "gen_video_avatar",
        telefono,
        {
            "texto": pendiente.texto,
            "avatar_id": pendiente.avatar_id,
            "voice_id": pendiente.voice_id,
            "costo_creditos": pendiente.costo_creditos,
        },
    )
    _PENDIENTES.pop(telefono, None)
    return {"estado": "ok", "job_id": job_id, "texto": pendiente.texto}


def cancelar_video_avatar(telefono: str) -> bool:
    return _PENDIENTES.pop(telefono, None) is not None
