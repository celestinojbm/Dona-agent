# agent/creativos/voz.py — Text-to-Speech (ElevenLabs)

"""
Integración con ElevenLabs para convertir texto a voz natural.

Diseño (mismo patrón que imagen.py / bg_remove.py):
  - `text_to_speech()` es la capa pura: recibe texto, retorna `(mp3_bytes, meta)`.
  - `preparar_voz()` / `confirmar_voz()` implementan el flujo de 2 pasos.
    El naming es LITERAL (preparar/confirmar) para evitar que el LLM alucine
    éxito antes de confirmar.
  - Costo depende del largo del texto — hasta 500 chars cuesta COSTO_VOZ_CORTA,
    más de 500 cuesta COSTO_VOZ_LARGA.
  - Si `ELEVENLABS_API_KEY` no está seteada, retorna un MP3 stub (silencio)
    para tests/dev.
"""

from __future__ import annotations

import os
import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta

logger = logging.getLogger("dona")


# ── Config ──────────────────────────────────────────────────────────────────

# Voice ID por defecto — Rachel (inglés) es el fallback del free tier.
# Para español nativo recomendado: "XrExE9yKIg1WjnnlVkGX" (Matilda, multilingual)
# o voices marcadas multilingual_v2. El usuario puede override via env.
ELEVEN_DEFAULT_VOICE = os.getenv("ELEVENLABS_VOICE_ID", "21m00Tcm4TlvDq8ikWAM")
ELEVEN_MODEL = os.getenv("ELEVENLABS_MODEL", "eleven_multilingual_v2")
ELEVEN_ENDPOINT_BASE = os.getenv(
    "ELEVENLABS_ENDPOINT",
    "https://api.elevenlabs.io/v1/text-to-speech",
)

REQUEST_TIMEOUT_S = float(os.getenv("ELEVENLABS_TIMEOUT", "60"))
MAX_RETRIES = int(os.getenv("ELEVENLABS_RETRIES", "2"))

PENDIENTE_TTL_MIN = int(os.getenv("VOZ_PENDIENTE_TTL_MIN", "15"))

# Límite duro: ElevenLabs tiene 5000 chars por request. Cortamos antes para
# no exceder y para que el costo no se dispare accidentalmente.
MAX_CHARS = int(os.getenv("VOZ_MAX_CHARS", "2000"))

# Threshold entre "corta" y "larga" — alinea con COSTO_VOZ_CORTA/LARGA en billing
UMBRAL_CORTA_CHARS = 500


# Stub MP3 válido: header ID3v2 + 1 frame de silencio (~26 bytes) — reproducible
# en la mayoría de clientes como silencio de ~0.03s. Útil para dev sin API key.
_STUB_MP3 = b"ID3\x04\x00\x00\x00\x00\x00\x00" + b"\xff\xfb\x90\x00" + b"\x00" * 32


class ElevenLabsError(Exception):
    """Error genérico del provider (timeout, 4xx/5xx, respuesta vacía)."""


# ── Low-level: llamada HTTP ─────────────────────────────────────────────────

async def text_to_speech(
    texto: str,
    voice_id: str | None = None,
    modelo: str | None = None,
    api_key: str | None = None,
) -> tuple[bytes, dict]:
    """
    Convierte `texto` en MP3. Retorna `(mp3_bytes, meta)`.

    `meta` incluye `modelo`, `voice_id`, `mime_type` y `bytes_size`.
    Lanza `ElevenLabsError` si falla tras reintentos.

    Si no hay key configurada, retorna un MP3 stub (silencio) — dev/tests.
    """
    if not texto or not texto.strip():
        raise ValueError("texto vacío")

    key = api_key if api_key is not None else os.getenv("ELEVENLABS_API_KEY", "")
    vid = voice_id or ELEVEN_DEFAULT_VOICE
    mod = modelo or ELEVEN_MODEL
    txt = texto.strip()[:MAX_CHARS]

    if not key:
        logger.warning("[VOZ] ELEVENLABS_API_KEY no configurada — usando stub MP3")
        return _STUB_MP3, {
            "modelo": "placeholder",
            "voice_id": vid,
            "mime_type": "audio/mpeg",
            "bytes_size": len(_STUB_MP3),
            "placeholder": True,
            "chars": len(txt),
        }

    import httpx

    url = f"{ELEVEN_ENDPOINT_BASE}/{vid}"
    headers = {
        "xi-api-key": key,
        "Content-Type": "application/json",
        "Accept": "audio/mpeg",
    }
    payload = {
        "text": txt,
        "model_id": mod,
        "voice_settings": {"stability": 0.5, "similarity_boost": 0.75},
    }

    ultimo_error: Exception | None = None
    for intento in range(MAX_RETRIES + 1):
        try:
            async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT_S) as client:
                resp = await client.post(url, headers=headers, json=payload)

            if resp.status_code >= 500:
                raise ElevenLabsError(f"ElevenLabs 5xx: {resp.status_code} {resp.text[:200]}")
            if resp.status_code >= 400:
                raise ElevenLabsError(f"ElevenLabs {resp.status_code}: {resp.text[:200]}")

            content = resp.content
            if not content or len(content) < 100:
                raise ElevenLabsError(f"Respuesta ElevenLabs vacía o inválida ({len(content)} bytes)")

            resp_mime = resp.headers.get("content-type", "audio/mpeg").split(";")[0].strip()
            return content, {
                "modelo": mod,
                "voice_id": vid,
                "mime_type": resp_mime or "audio/mpeg",
                "bytes_size": len(content),
                "placeholder": False,
                "chars": len(txt),
            }

        except ElevenLabsError as e:
            ultimo_error = e
            if "4" in str(e)[:14] and "5" not in str(e)[:14]:
                break
            if intento < MAX_RETRIES:
                backoff = 2 ** intento
                logger.warning(f"[VOZ] intento {intento+1} falló ({e}); reintentando en {backoff}s")
                await asyncio.sleep(backoff)
        except Exception as e:
            ultimo_error = ElevenLabsError(f"{type(e).__name__}: {e}")
            if intento < MAX_RETRIES:
                await asyncio.sleep(2 ** intento)

    raise ultimo_error or ElevenLabsError("fallo desconocido")


# ── Pendientes (preparar → confirmar) ───────────────────────────────────────

@dataclass
class VozPendiente:
    telefono: str
    texto: str
    voice_id: str
    costo_creditos: int
    creado: datetime = field(default_factory=datetime.utcnow)

    def expirado(self) -> bool:
        return datetime.utcnow() - self.creado > timedelta(minutes=PENDIENTE_TTL_MIN)


_PENDIENTES: dict[str, VozPendiente] = {}


def obtener_pendiente(telefono: str) -> VozPendiente | None:
    p = _PENDIENTES.get(telefono)
    if p is None:
        return None
    if p.expirado():
        _PENDIENTES.pop(telefono, None)
        return None
    return p


def costo_por_largo(texto: str) -> int:
    """Devuelve COSTO_VOZ_CORTA o COSTO_VOZ_LARGA según el largo del texto."""
    from agent.billing import COSTO_VOZ_CORTA, COSTO_VOZ_LARGA
    return COSTO_VOZ_CORTA if len(texto) <= UMBRAL_CORTA_CHARS else COSTO_VOZ_LARGA


# ── API 2 pasos ─────────────────────────────────────────────────────────────

async def preparar_voz(
    telefono: str,
    texto: str,
    voice_id: str | None = None,
) -> dict:
    """Guarda el texto como pendiente y retorna preview. NO cobra, NO genera."""
    from agent.billing import obtener_saldo

    texto = (texto or "").strip()
    if not texto:
        raise ValueError("texto vacío")
    texto = texto[:MAX_CHARS]

    costo = costo_por_largo(texto)
    saldo = await obtener_saldo(telefono)
    vid = voice_id or ELEVEN_DEFAULT_VOICE

    pendiente = VozPendiente(
        telefono=telefono,
        texto=texto,
        voice_id=vid,
        costo_creditos=costo,
    )
    _PENDIENTES[telefono] = pendiente

    return {
        "texto": texto,
        "voice_id": vid,
        "chars": len(texto),
        "costo_creditos": costo,
        "saldo_actual": saldo,
        "alcanza": saldo >= costo,
        "ttl_min": PENDIENTE_TTL_MIN,
    }


async def confirmar_voz(telefono: str) -> dict:
    """Cobra y encola job `gen_voz`. Retorna estado."""
    pendiente = obtener_pendiente(telefono)
    if pendiente is None:
        return {"estado": "sin_pendiente"}

    from agent.billing import cobrar_o_rechazar
    from agent.jobs import encolar

    ok, err = await cobrar_o_rechazar(
        telefono,
        pendiente.costo_creditos,
        f"gen_voz ({pendiente.costo_creditos}cr, {len(pendiente.texto)}ch)",
    )
    if not ok:
        return {"estado": "saldo_insuficiente", "mensaje": err}

    job_id = await encolar(
        "gen_voz",
        telefono,
        {
            "texto": pendiente.texto,
            "voice_id": pendiente.voice_id,
            "costo_creditos": pendiente.costo_creditos,
        },
    )
    _PENDIENTES.pop(telefono, None)
    return {"estado": "ok", "job_id": job_id, "texto": pendiente.texto}


def cancelar_voz(telefono: str) -> bool:
    return _PENDIENTES.pop(telefono, None) is not None
