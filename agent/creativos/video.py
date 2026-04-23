# agent/creativos/video.py — Generación de video corto (Replicate)

"""
Integración con Replicate para text-to-video (y opcionalmente image-to-video).

Diseño (mismo patrón que voz.py / imagen.py):
  - `generar_video()` crea la predicción, hace polling hasta completar y
    descarga el MP4. Retorna `(video_bytes, meta)`.
  - `preparar_video()` / `confirmar_video()` implementan el flujo 2 pasos
    (naming LITERAL según CLAUDE.md §3.1).
  - Modelo configurable via `REPLICATE_VIDEO_MODEL` (default:
    `bytedance/seedance-1-lite` — texto→video, económico).
  - Costo plano `COSTO_VIDEO_CORTO` (50 cr) por generación.
  - Sin key configurada → retorna MP4 stub para dev/tests.
"""

from __future__ import annotations

import os
import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta

logger = logging.getLogger("dona")


# ── Config ──────────────────────────────────────────────────────────────────

REPLICATE_API_BASE = os.getenv(
    "REPLICATE_API_BASE",
    "https://api.replicate.com/v1",
)

# Default: modelo económico para texto→video (~5s clips). Se puede overridear
# con el slug oficial de Replicate (`owner/name` o `owner/name:version`).
REPLICATE_VIDEO_MODEL = os.getenv(
    "REPLICATE_VIDEO_MODEL",
    "bytedance/seedance-1-lite",
)

# Timeouts
CREATE_TIMEOUT_S = float(os.getenv("REPLICATE_CREATE_TIMEOUT", "30"))
POLL_TIMEOUT_S = float(os.getenv("REPLICATE_POLL_TIMEOUT", "420"))  # 7 min total
POLL_INTERVAL_S = float(os.getenv("REPLICATE_POLL_INTERVAL", "3"))
DOWNLOAD_TIMEOUT_S = float(os.getenv("REPLICATE_DOWNLOAD_TIMEOUT", "120"))

PENDIENTE_TTL_MIN = int(os.getenv("VIDEO_PENDIENTE_TTL_MIN", "15"))

# Límites
MAX_PROMPT_CHARS = int(os.getenv("VIDEO_MAX_PROMPT", "500"))


# MP4 stub mínimo (header ISO BMFF, no reproducible como video real — sólo para
# que tests y dev tengan bytes con firma reconocible).
_STUB_MP4 = (
    b"\x00\x00\x00\x20ftypisom\x00\x00\x02\x00isomiso2avc1mp41"
    + b"\x00" * 128
)


class ReplicateError(Exception):
    """Error genérico del provider (auth, 4xx/5xx, timeout, predicción falló)."""


# ── Low-level HTTP ──────────────────────────────────────────────────────────

def _headers(api_key: str) -> dict:
    return {
        "Authorization": f"Token {api_key}",
        "Content-Type": "application/json",
    }


async def _crear_prediccion(
    client,
    api_key: str,
    prompt: str,
    image_url: str = "",
    model: str = "",
) -> dict:
    """
    Crea la predicción en Replicate.

    Replicate acepta dos formas:
      - Por `model`: {"model": "owner/name", "input": {...}}  (usa última version)
      - Por `version`: {"version": "hash", "input": {...}}
    Usamos la primera — más simple de mantener al día.
    """
    slug = model or REPLICATE_VIDEO_MODEL
    input_payload: dict = {"prompt": prompt[:MAX_PROMPT_CHARS]}
    if image_url:
        # La mayoría de modelos image-to-video acepta `image` como URL
        input_payload["image"] = image_url

    # Si el slug incluye ":hash", separarlo como `version`
    if ":" in slug:
        owner_name, version_hash = slug.rsplit(":", 1)
        payload = {"version": version_hash, "input": input_payload}
        endpoint = f"{REPLICATE_API_BASE}/predictions"
    else:
        # `model` style — el endpoint es /models/{owner}/{name}/predictions
        # https://replicate.com/docs/reference/http#models.predictions.create
        endpoint = f"{REPLICATE_API_BASE}/models/{slug}/predictions"
        payload = {"input": input_payload}

    resp = await client.post(endpoint, headers=_headers(api_key), json=payload)
    if resp.status_code >= 500:
        raise ReplicateError(f"Replicate 5xx: {resp.status_code} {resp.text[:200]}")
    if resp.status_code == 402:
        # Replicate usa 402 para varios escenarios: cuenta sin saldo, spend
        # limit alcanzado, hard-limit del plan, billing sin setup. Incluimos
        # el body real para poder distinguir desde los logs.
        raise ReplicateError(
            f"Replicate 402 (billing): {resp.text[:400]}"
        )
    if resp.status_code >= 400:
        raise ReplicateError(f"Replicate {resp.status_code}: {resp.text[:200]}")
    try:
        return resp.json()
    except Exception as e:
        raise ReplicateError(f"Respuesta no-JSON de Replicate: {e}")


async def _poll_prediccion(client, api_key: str, get_url: str) -> dict:
    """Polling con timeout total. Devuelve el dict final (succeeded/failed/canceled)."""
    deadline = asyncio.get_event_loop().time() + POLL_TIMEOUT_S
    while True:
        if asyncio.get_event_loop().time() > deadline:
            raise ReplicateError("Timeout esperando la predicción de Replicate")
        resp = await client.get(get_url, headers=_headers(api_key))
        if resp.status_code >= 400:
            raise ReplicateError(f"Replicate poll {resp.status_code}: {resp.text[:200]}")
        data = resp.json()
        status = (data.get("status") or "").lower()
        if status in ("succeeded", "failed", "canceled"):
            return data
        await asyncio.sleep(POLL_INTERVAL_S)


async def _descargar(client, url: str) -> bytes:
    resp = await client.get(url, follow_redirects=True)
    if resp.status_code != 200:
        raise ReplicateError(f"Descarga falló: {resp.status_code}")
    return resp.content


# ── Capa pura ──────────────────────────────────────────────────────────────

async def generar_video(
    prompt: str,
    image_url: str = "",
    model: str = "",
    api_key: str | None = None,
) -> tuple[bytes, dict]:
    """
    Genera un video (MP4) desde `prompt`. Si `image_url` está presente y el
    modelo lo acepta, hace image-to-video.

    Retorna `(video_bytes, meta)` con `meta` incluyendo `modelo`, `mime_type`,
    `prediction_id`, `bytes_size`, `duracion_s` (si el modelo la reporta).
    Lanza `ReplicateError` si falla.

    Sin `REPLICATE_API_TOKEN` → retorna MP4 stub (placeholder).
    """
    prompt = (prompt or "").strip()
    if not prompt:
        raise ValueError("prompt vacío")

    key = api_key if api_key is not None else os.getenv("REPLICATE_API_TOKEN", "")
    if not key:
        logger.warning("[VIDEO] REPLICATE_API_TOKEN no configurada — usando stub MP4")
        return _STUB_MP4, {
            "modelo": "placeholder",
            "mime_type": "video/mp4",
            "bytes_size": len(_STUB_MP4),
            "placeholder": True,
            "prompt": prompt[:MAX_PROMPT_CHARS],
        }

    import httpx

    async with httpx.AsyncClient(timeout=CREATE_TIMEOUT_S) as client:
        creada = await _crear_prediccion(client, key, prompt, image_url=image_url, model=model)
        pred_id = creada.get("id") or ""
        get_url = (creada.get("urls") or {}).get("get") or (
            f"{REPLICATE_API_BASE}/predictions/{pred_id}" if pred_id else ""
        )
        if not get_url:
            raise ReplicateError(f"Respuesta de Replicate sin urls.get: {str(creada)[:200]}")

        # Si ya llegó completada (raro pero posible), saltamos el poll.
        status = (creada.get("status") or "").lower()
        final = creada if status in ("succeeded", "failed", "canceled") else None

    if final is None:
        async with httpx.AsyncClient(timeout=POLL_TIMEOUT_S + 30) as client:
            final = await _poll_prediccion(client, key, get_url)

    status = (final.get("status") or "").lower()
    if status != "succeeded":
        err = final.get("error") or f"status={status}"
        raise ReplicateError(f"Predicción no exitosa: {str(err)[:200]}")

    # `output` puede ser str (URL) o lista de URLs. Algunos modelos lo devuelven
    # como dict anidado. Tomamos la primera URL que encontremos.
    out = final.get("output")
    url_video = ""
    if isinstance(out, str):
        url_video = out
    elif isinstance(out, list) and out:
        for item in out:
            if isinstance(item, str) and item.startswith("http"):
                url_video = item
                break
    elif isinstance(out, dict):
        for v in out.values():
            if isinstance(v, str) and v.startswith("http"):
                url_video = v
                break

    if not url_video:
        raise ReplicateError(f"Predicción sin URL de video: output={str(out)[:200]}")

    async with httpx.AsyncClient(timeout=DOWNLOAD_TIMEOUT_S) as client:
        video_bytes = await _descargar(client, url_video)

    if not video_bytes or len(video_bytes) < 1000:
        raise ReplicateError(f"Video descargado demasiado pequeño ({len(video_bytes)}B)")

    metrics = final.get("metrics") or {}
    return video_bytes, {
        "modelo": model or REPLICATE_VIDEO_MODEL,
        "mime_type": "video/mp4",
        "bytes_size": len(video_bytes),
        "placeholder": False,
        "prompt": prompt[:MAX_PROMPT_CHARS],
        "prediction_id": final.get("id", ""),
        "predict_time_s": metrics.get("predict_time"),
        "source_url": url_video,
    }


# ── Pendientes (preparar → confirmar) ───────────────────────────────────────

@dataclass
class VideoPendiente:
    telefono: str
    prompt: str
    image_url: str
    costo_creditos: int
    creado: datetime = field(default_factory=datetime.utcnow)

    def expirado(self) -> bool:
        return datetime.utcnow() - self.creado > timedelta(minutes=PENDIENTE_TTL_MIN)


_PENDIENTES: dict[str, VideoPendiente] = {}


def obtener_pendiente(telefono: str) -> VideoPendiente | None:
    p = _PENDIENTES.get(telefono)
    if p is None:
        return None
    if p.expirado():
        _PENDIENTES.pop(telefono, None)
        return None
    return p


# ── API 2 pasos ─────────────────────────────────────────────────────────────

async def preparar_video(
    telefono: str,
    prompt: str,
    image_url: str = "",
) -> dict:
    """Guarda el pedido como pendiente y retorna preview. NO cobra, NO genera."""
    from agent.billing import obtener_saldo, COSTO_VIDEO_CORTO
    from agent.creativos.pendientes import cancelar_otros_pendientes

    prompt = (prompt or "").strip()
    if not prompt:
        raise ValueError("prompt vacío")
    prompt = prompt[:MAX_PROMPT_CHARS]

    # Un solo pendiente activo por teléfono — si había otro, lo reemplazamos.
    reemplazo = cancelar_otros_pendientes(telefono, excepto="video")

    costo = COSTO_VIDEO_CORTO
    saldo = await obtener_saldo(telefono)

    pendiente = VideoPendiente(
        telefono=telefono,
        prompt=prompt,
        image_url=image_url or "",
        costo_creditos=costo,
    )
    _PENDIENTES[telefono] = pendiente

    return {
        "prompt": prompt,
        "image_url": image_url,
        "costo_creditos": costo,
        "saldo_actual": saldo,
        "alcanza": saldo >= costo,
        "ttl_min": PENDIENTE_TTL_MIN,
        "modelo": REPLICATE_VIDEO_MODEL,
        "reemplazo": reemplazo,
    }


async def confirmar_video(telefono: str) -> dict:
    """Cobra y encola job `gen_video`."""
    pendiente = obtener_pendiente(telefono)
    if pendiente is None:
        return {"estado": "sin_pendiente"}

    from agent.billing import cobrar_o_rechazar
    from agent.jobs import encolar

    ok, err = await cobrar_o_rechazar(
        telefono,
        pendiente.costo_creditos,
        f"gen_video ({pendiente.costo_creditos}cr)",
    )
    if not ok:
        return {"estado": "saldo_insuficiente", "mensaje": err}

    job_id = await encolar(
        "gen_video",
        telefono,
        {
            "prompt": pendiente.prompt,
            "image_url": pendiente.image_url,
            "costo_creditos": pendiente.costo_creditos,
        },
    )
    _PENDIENTES.pop(telefono, None)
    return {"estado": "ok", "job_id": job_id, "prompt": pendiente.prompt}


def cancelar_video(telefono: str) -> bool:
    return _PENDIENTES.pop(telefono, None) is not None
