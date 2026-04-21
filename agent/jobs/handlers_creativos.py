# agent/jobs/handlers_creativos.py — Handlers de jobs creativos

"""
Registra los handlers de generación creativa (imagen en Sprint 2, luego
video/voz/web). Cada handler:
  1. Recibe `(telefono, params)` del dispatcher.
  2. Llama al provider creativo (Gemini, Runway, etc.) para producir bytes.
  3. Sube el resultado via `storage.subir_asset` (R2 o FS).
  4. Registra el asset en DB via `storage.registrar_asset`.
  5. Envía la URL/imagen por WhatsApp al usuario.
  6. Retorna `asset_id` — el worker lo persiste en la fila del job.

Errores se propagan hacia `_ejecutar_con_estado` que los marca como job
en estado 'error'. El usuario recibe notificación de fallo por WhatsApp.
"""

from __future__ import annotations

import logging
from typing import Any

from agent.jobs.worker import registrar_handler

logger = logging.getLogger("dona")


def _proveedor_whatsapp():
    """Import diferido — evita ciclo al cargar."""
    from agent.providers import obtener_proveedor
    return obtener_proveedor()


async def _reembolsar(telefono: str, creditos: int, motivo: str) -> int | None:
    """
    Devuelve los créditos cobrados cuando la generación falla.
    Retorna el saldo nuevo o None si no se pudo reembolsar.
    """
    if creditos <= 0:
        return None
    from agent.billing import acreditar
    try:
        saldo = await acreditar(
            telefono,
            creditos,
            razon=f"Refund gen_imagen: {motivo}"[:120],
        )
        logger.info(f"[HANDLER gen_imagen] refund {creditos} cr → {telefono} (saldo={saldo})")
        return saldo
    except Exception as e:
        logger.exception(f"[HANDLER gen_imagen] Error reembolsando créditos: {e}")
        return None


@registrar_handler("gen_imagen")
async def _handler_gen_imagen(telefono: str, params: dict[str, Any]) -> int | None:
    """
    Handler de generación de imagen.

    params esperados:
      - prompt (str)
      - calidad (str): "standard" | "premium"
      - aspect_ratio (str): "1:1", "16:9", etc.
      - costo_creditos (int): ya cobrado por confirmar_imagen. Si la generación
        o el guardado fallan, se reembolsa acá y se notifica al usuario.
    """
    from agent.creativos.imagen import generar_imagen, GeminiError
    from agent import storage

    prompt = (params.get("prompt") or "").strip()
    calidad = params.get("calidad", "standard")
    aspect_ratio = params.get("aspect_ratio", "1:1")
    costo_creditos = int(params.get("costo_creditos", 0))

    if not prompt:
        raise ValueError("gen_imagen: prompt vacío")

    proveedor = _proveedor_whatsapp()

    # 1) Generar
    try:
        img_bytes, meta = await generar_imagen(prompt, calidad=calidad, aspect_ratio=aspect_ratio)
    except GeminiError as e:
        logger.error(f"[HANDLER gen_imagen] Gemini error: {e}")
        await _reembolsar(telefono, costo_creditos, "provider falló")
        try:
            nota = (
                f"Te devolví los *{costo_creditos}* créditos. "
                if costo_creditos > 0 else ""
            )
            await proveedor.enviar_mensaje(
                telefono,
                f"⚠️ No pude generar la imagen (el modelo rechazó el prompt o hubo un error temporal). "
                f"{nota}Prueba reformulando el prompt o escribe *dona soporte* si crees que es un bug.",
            )
        except Exception:
            pass
        raise

    # 2) Subir
    try:
        guardado = await storage.subir_asset(
            telefono=telefono,
            tipo="image",
            contenido=img_bytes,
            mime_type=meta.get("mime_type", "image/png"),
            nombre_sugerido="imagen.png",
        )
    except Exception as e:
        logger.exception(f"[HANDLER gen_imagen] Error subiendo imagen: {e}")
        await _reembolsar(telefono, costo_creditos, "fallo al guardar")
        try:
            nota = (
                f"Te devolví los *{costo_creditos}* créditos. "
                if costo_creditos > 0 else ""
            )
            await proveedor.enviar_mensaje(
                telefono,
                f"⚠️ Generé la imagen pero no pude guardarla. "
                f"{nota}Intenta de nuevo en un momento.",
            )
        except Exception:
            pass
        raise

    # 3) Registrar
    asset_id = await storage.registrar_asset(
        telefono=telefono,
        tipo="image",
        guardado=guardado,
        prompt=prompt,
        modelo=meta.get("modelo", ""),
        costo_creditos=costo_creditos,
        meta={
            "aspect_ratio": meta.get("aspect_ratio"),
            "placeholder": meta.get("placeholder", False),
            "calidad": calidad,
        },
    )

    # 4) Enviar por WhatsApp
    caption = f"🎨 {prompt[:900]}"
    ok = False
    # URLs fs:// no son servibles externamente — mandar texto en su lugar
    if guardado.backend == "r2" and guardado.url_publica.startswith("http"):
        ok = await proveedor.enviar_imagen(
            telefono,
            url=guardado.url_publica,
            caption=caption,
            mime_type=guardado.mime_type,
        )
    if not ok:
        # Fallback: mandar los bytes directamente
        ok = await proveedor.enviar_imagen(
            telefono,
            imagen_bytes=img_bytes,
            caption=caption,
            mime_type=guardado.mime_type,
        )
    if not ok:
        # Último recurso: texto con la URL (útil en dev con fs backend)
        await proveedor.enviar_mensaje(
            telefono,
            f"✅ Imagen lista:\n{guardado.url_publica}\n\n🎨 {prompt[:200]}",
        )

    logger.info(f"[HANDLER gen_imagen] asset_id={asset_id} enviado a {telefono}")
    return asset_id
