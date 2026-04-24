# agent/creativos/imagen.py — Generación de imágenes (Gemini Flash Image)

"""
Wrapper del endpoint de Gemini para generación de imágenes + flujo
preparar/confirmar para cobrar sólo cuando el usuario confirma.

Diseño:
  - `generar_imagen()` es la capa pura: recibe prompt, retorna `(bytes, meta)`.
    No toca storage, billing, ni DB — se puede probar con mocks de httpx.
  - `preparar_imagen()` / `confirmar_imagen()` implementan el flujo de 2 pasos:
      preparar  → guarda el prompt como "pendiente" y retorna preview + costo
      confirmar → cobra créditos y encola el job real
    El naming es LITERAL (preparar/confirmar) para evitar que el LLM
    alucine éxito antes de confirmar (ver feedback_tools_naming_2pasos).
  - Si `GEMINI_API_KEY` no está seteada, `generar_imagen` retorna un
    placeholder PNG 1x1 — permite dev/tests sin quemar cuota.
"""

from __future__ import annotations

import os
import base64
import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

logger = logging.getLogger("dona")


# ── Config ──────────────────────────────────────────────────────────────────

# Modelos soportados. El default (flash) es más rápido y barato; pro es
# para casos de máxima calidad. El usuario los selecciona via `calidad`.
MODELO_FLASH = os.getenv("GEMINI_IMAGE_MODEL_FLASH", "gemini-2.5-flash-image-preview")
MODELO_PRO   = os.getenv("GEMINI_IMAGE_MODEL_PRO",   "gemini-3.0-pro-image-preview")

GEMINI_ENDPOINT_BASE = "https://generativelanguage.googleapis.com/v1beta/models"

# Timeout y retries de generación — imagen puede tardar 5-20s
REQUEST_TIMEOUT_S = float(os.getenv("GEMINI_IMAGE_TIMEOUT", "60"))
MAX_RETRIES = int(os.getenv("GEMINI_IMAGE_RETRIES", "2"))

# TTL de preparaciones pendientes en memoria — si el usuario no confirma en
# este tiempo, se descarta (evita que "confirmar" cobre un prompt viejo).
PENDIENTE_TTL_MIN = int(os.getenv("IMAGEN_PENDIENTE_TTL_MIN", "15"))


# 1x1 PNG transparente — placeholder cuando no hay key (base64 decoded)
_PLACEHOLDER_PNG = base64.b64decode(
    b"iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="
)


class GeminiError(Exception):
    """Error genérico del provider (timeout, 4xx/5xx, JSON inválido)."""


# ── Low-level: llamada HTTP ────────────────────────────────────────────────

async def generar_imagen(
    prompt: str,
    calidad: str = "standard",
    aspect_ratio: str = "1:1",
    api_key: str | None = None,
) -> tuple[bytes, dict]:
    """
    Genera una imagen desde `prompt`. Retorna `(image_bytes, meta)`.

    `meta` incluye `modelo`, `mime_type`, `bytes_size` y el aspect_ratio usado.
    Lanza `GeminiError` si no fue posible generar tras reintentos.

    Routing por calidad:
      - "premium" + IDEOGRAM_API_KEY presente → Ideogram v2 Turbo (mejor texto
        en la imagen, ideal para flyers/promos con precio/logo).
      - "premium" sin Ideogram → cae a Gemini Pro.
      - "standard" → Gemini Flash Image.

    Si no hay ninguna key configurada, retorna un PNG 1x1 placeholder (dev/tests).
    """
    if not prompt or not prompt.strip():
        raise ValueError("prompt vacío")

    # Routing: premium → Ideogram si hay key, sino Gemini Pro
    if calidad == "premium" and os.getenv("IDEOGRAM_API_KEY"):
        try:
            return await _generar_ideogram(prompt, aspect_ratio)
        except GeminiError as e:
            logger.warning(f"[IMAGEN] Ideogram falló ({e}) — fallback a Gemini Pro")
            # Cae al flujo Gemini normal abajo

    key = api_key if api_key is not None else os.getenv("GEMINI_API_KEY", "")
    modelo = MODELO_PRO if calidad == "premium" else MODELO_FLASH

    if not key:
        logger.warning("[IMAGEN] GEMINI_API_KEY no configurada — usando placeholder PNG")
        return _PLACEHOLDER_PNG, {
            "modelo": "placeholder",
            "mime_type": "image/png",
            "bytes_size": len(_PLACEHOLDER_PNG),
            "aspect_ratio": aspect_ratio,
            "placeholder": True,
        }

    import httpx  # import diferido para que los tests puedan mockear

    url = f"{GEMINI_ENDPOINT_BASE}/{modelo}:generateContent?key={key}"
    payload = {
        "contents": [{"parts": [{"text": prompt.strip()}]}],
        "generationConfig": {
            "responseModalities": ["IMAGE"],
            "imageConfig": {"aspectRatio": aspect_ratio},
        },
    }

    ultimo_error: Exception | None = None
    for intento in range(MAX_RETRIES + 1):
        try:
            async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT_S) as client:
                resp = await client.post(url, json=payload)

            if resp.status_code >= 500:
                raise GeminiError(f"Gemini 5xx: {resp.status_code} {resp.text[:200]}")
            if resp.status_code >= 400:
                # 4xx típicamente es prompt filtrado o key inválida — no reintenta
                raise GeminiError(f"Gemini {resp.status_code}: {resp.text[:200]}")

            data = resp.json()
            img_bytes, mime = _extraer_imagen_inline(data)
            if not img_bytes:
                raise GeminiError(f"Respuesta Gemini sin imagen: {str(data)[:300]}")

            return img_bytes, {
                "modelo": modelo,
                "mime_type": mime,
                "bytes_size": len(img_bytes),
                "aspect_ratio": aspect_ratio,
                "placeholder": False,
            }

        except GeminiError as e:
            ultimo_error = e
            # 4xx no se reintenta
            if "4" in str(e)[:10] and "5" not in str(e)[:10]:
                break
            if intento < MAX_RETRIES:
                backoff = 2 ** intento
                logger.warning(f"[IMAGEN] intento {intento+1} falló ({e}); reintentando en {backoff}s")
                await asyncio.sleep(backoff)
        except Exception as e:
            ultimo_error = GeminiError(f"{type(e).__name__}: {e}")
            if intento < MAX_RETRIES:
                await asyncio.sleep(2 ** intento)

    raise ultimo_error or GeminiError("fallo desconocido")


# ── Ideogram (premium) ──────────────────────────────────────────────────────

IDEOGRAM_ENDPOINT = os.getenv("IDEOGRAM_ENDPOINT", "https://api.ideogram.ai/generate")
IDEOGRAM_MODEL = os.getenv("IDEOGRAM_MODEL", "V_2_TURBO")

_ASPECT_A_IDEOGRAM = {
    "1:1":  "ASPECT_1_1",
    "16:9": "ASPECT_16_9",
    "9:16": "ASPECT_9_16",
    "4:3":  "ASPECT_4_3",
    "3:4":  "ASPECT_3_4",
}


async def _generar_ideogram(prompt: str, aspect_ratio: str) -> tuple[bytes, dict]:
    """
    Llama a Ideogram v2 Turbo. Ideogram devuelve una URL; hay que descargarla
    para retornar bytes como el resto de la API.

    Reutiliza `GeminiError` como error unificado del módulo — el caller no
    distingue provider.
    """
    import httpx

    key = os.getenv("IDEOGRAM_API_KEY", "")
    if not key:
        raise GeminiError("IDEOGRAM_API_KEY ausente")

    payload = {
        "image_request": {
            "prompt": prompt.strip(),
            "aspect_ratio": _ASPECT_A_IDEOGRAM.get(aspect_ratio, "ASPECT_1_1"),
            "model": IDEOGRAM_MODEL,
            "magic_prompt_option": "AUTO",
        }
    }
    headers = {"Api-Key": key, "Content-Type": "application/json"}

    ultimo_error: Exception | None = None
    for intento in range(MAX_RETRIES + 1):
        try:
            async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT_S) as client:
                resp = await client.post(IDEOGRAM_ENDPOINT, headers=headers, json=payload)
                if resp.status_code >= 500:
                    raise GeminiError(f"Ideogram 5xx: {resp.status_code} {resp.text[:200]}")
                if resp.status_code >= 400:
                    raise GeminiError(f"Ideogram {resp.status_code}: {resp.text[:200]}")

                data = resp.json()
                items = data.get("data") or []
                if not items or not items[0].get("url"):
                    raise GeminiError(f"Respuesta Ideogram sin URL: {str(data)[:200]}")

                img_url = items[0]["url"]
                img_resp = await client.get(img_url)
                if img_resp.status_code != 200:
                    raise GeminiError(f"Ideogram GET imagen falló: {img_resp.status_code}")
                img_bytes = img_resp.content
                mime = img_resp.headers.get("content-type", "image/png").split(";")[0].strip()

            return img_bytes, {
                "modelo": f"ideogram-{IDEOGRAM_MODEL.lower()}",
                "mime_type": mime or "image/png",
                "bytes_size": len(img_bytes),
                "aspect_ratio": aspect_ratio,
                "placeholder": False,
            }

        except GeminiError as e:
            ultimo_error = e
            if "4" in str(e)[:14] and "5" not in str(e)[:14]:
                break
            if intento < MAX_RETRIES:
                await asyncio.sleep(2 ** intento)
        except Exception as e:
            ultimo_error = GeminiError(f"Ideogram {type(e).__name__}: {e}")
            if intento < MAX_RETRIES:
                await asyncio.sleep(2 ** intento)

    raise ultimo_error or GeminiError("Ideogram: fallo desconocido")


def _extraer_imagen_inline(data: dict) -> tuple[bytes, str]:
    """Busca `inlineData` con datos base64 en la respuesta de Gemini."""
    for cand in data.get("candidates", []):
        content = cand.get("content", {}) or {}
        for part in content.get("parts", []) or []:
            inline = part.get("inlineData") or part.get("inline_data")
            if inline and inline.get("data"):
                try:
                    raw = base64.b64decode(inline["data"])
                    mime = inline.get("mimeType") or inline.get("mime_type") or "image/png"
                    return raw, mime
                except Exception as e:
                    logger.warning(f"[IMAGEN] base64 inválido: {e}")
    return b"", ""


# ── Pendientes en memoria (preparar → confirmar) ────────────────────────────

@dataclass
class ImagenPendiente:
    telefono: str
    prompt: str
    calidad: str
    aspect_ratio: str
    costo_creditos: int
    creado: datetime = field(default_factory=datetime.utcnow)

    def expirado(self) -> bool:
        return datetime.utcnow() - self.creado > timedelta(minutes=PENDIENTE_TTL_MIN)


_PENDIENTES: dict[str, ImagenPendiente] = {}


def obtener_pendiente(telefono: str) -> ImagenPendiente | None:
    p = _PENDIENTES.get(telefono)
    if p is None:
        return None
    if p.expirado():
        _PENDIENTES.pop(telefono, None)
        return None
    return p


# ── API 2 pasos ─────────────────────────────────────────────────────────────

async def preparar_imagen(
    telefono: str,
    prompt: str,
    calidad: str = "standard",
    aspect_ratio: str = "1:1",
) -> dict:
    """
    Guarda el prompt como pendiente y retorna dict con los datos para mostrar
    al usuario (prompt, costo, saldo, modelo). NO cobra, NO genera.
    """
    from agent.billing import (
        COSTO_IMAGEN_STANDARD, COSTO_IMAGEN_PREMIUM, obtener_saldo,
    )
    from agent.creativos.pendientes import cancelar_otros_pendientes

    prompt = (prompt or "").strip()
    if not prompt:
        raise ValueError("prompt vacío")
    if calidad not in ("standard", "premium"):
        calidad = "standard"
    if aspect_ratio not in ("1:1", "16:9", "9:16", "4:3", "3:4"):
        aspect_ratio = "1:1"

    # Un solo pendiente activo por teléfono — si había otro, lo reemplazamos.
    reemplazo = cancelar_otros_pendientes(telefono, excepto="imagen")

    costo = COSTO_IMAGEN_PREMIUM if calidad == "premium" else COSTO_IMAGEN_STANDARD
    saldo = await obtener_saldo(telefono)

    pendiente = ImagenPendiente(
        telefono=telefono,
        prompt=prompt[:2000],
        calidad=calidad,
        aspect_ratio=aspect_ratio,
        costo_creditos=costo,
    )
    _PENDIENTES[telefono] = pendiente

    return {
        "prompt": pendiente.prompt,
        "calidad": calidad,
        "aspect_ratio": aspect_ratio,
        "costo_creditos": costo,
        "saldo_actual": saldo,
        "alcanza": saldo >= costo,
        "ttl_min": PENDIENTE_TTL_MIN,
        "reemplazo": reemplazo,
    }


async def ajustar_imagen(telefono: str, nuevo_prompt: str) -> dict:
    """
    Reemplaza el prompt de la imagen pendiente con uno nuevo. NO cobra, NO
    cancela — solo deja el pendiente listo para confirmar/cancelar con la
    nueva descripción.

    Retorna:
      - {"estado": "sin_pendiente"} si no había imagen pendiente
      - {"estado": "ok", ...preview} con el nuevo preview
    """
    from agent.billing import obtener_saldo

    pendiente = obtener_pendiente(telefono)
    if pendiente is None:
        return {"estado": "sin_pendiente"}

    nuevo = (nuevo_prompt or "").strip()[:2000]
    if not nuevo:
        raise ValueError("nuevo_prompt vacío")

    pendiente.prompt = nuevo
    # Reseteamos TTL al iterar — el usuario sigue activo.
    pendiente.creado = datetime.utcnow()

    saldo = await obtener_saldo(telefono)

    logger.info(f"[IMAGEN] ajustar → {telefono} nuevo_prompt=\"{nuevo[:60]}\"")

    return {
        "estado": "ok",
        "prompt": pendiente.prompt,
        "calidad": pendiente.calidad,
        "aspect_ratio": pendiente.aspect_ratio,
        "costo_creditos": pendiente.costo_creditos,
        "saldo_actual": saldo,
        "alcanza": saldo >= pendiente.costo_creditos,
        "ttl_min": PENDIENTE_TTL_MIN,
        "reemplazo": None,
    }


async def confirmar_imagen(telefono: str) -> dict:
    """
    Cobra los créditos y encola un job `gen_imagen`.
    Retorna `{"estado": "ok"|"sin_pendiente"|"saldo_insuficiente", ...}`.
    NO espera a que termine el job — el worker notifica al usuario cuando listo.
    """
    pendiente = obtener_pendiente(telefono)
    if pendiente is None:
        return {"estado": "sin_pendiente"}

    from agent.billing import cobrar_o_rechazar
    from agent.jobs import encolar

    ok, err = await cobrar_o_rechazar(
        telefono,
        pendiente.costo_creditos,
        f"gen_imagen {pendiente.calidad}",
    )
    if not ok:
        return {"estado": "saldo_insuficiente", "mensaje": err}

    job_id = await encolar(
        "gen_imagen",
        telefono,
        {
            "prompt": pendiente.prompt,
            "calidad": pendiente.calidad,
            "aspect_ratio": pendiente.aspect_ratio,
            "costo_creditos": pendiente.costo_creditos,
        },
    )
    _PENDIENTES.pop(telefono, None)
    return {"estado": "ok", "job_id": job_id, "prompt": pendiente.prompt}


def cancelar_imagen(telefono: str) -> bool:
    """Descarta el pendiente sin cobrar. Retorna True si había uno."""
    return _PENDIENTES.pop(telefono, None) is not None
