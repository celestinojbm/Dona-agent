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


async def _reembolsar(telefono: str, creditos: int, motivo: str, scope: str = "gen_imagen") -> int | None:
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
            razon=f"Refund {scope}: {motivo}"[:120],
        )
        logger.info(f"[HANDLER {scope}] refund {creditos} cr → {telefono} (saldo={saldo})")
        return saldo
    except Exception as e:
        logger.exception(f"[HANDLER {scope}] Error reembolsando créditos: {e}")
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


# ── bg_remove (Photoroom) ───────────────────────────────────────────────────

async def _descargar_url(url: str, timeout_s: float = 30.0) -> tuple[bytes, str]:
    """
    Descarga bytes de una URL pública o firmada. Retorna `(bytes, mime_type)`.
    Lanza Exception si falla.
    """
    import httpx
    async with httpx.AsyncClient(timeout=timeout_s, follow_redirects=True) as client:
        resp = await client.get(url)
        if resp.status_code != 200:
            raise RuntimeError(f"GET {url[:120]} → {resp.status_code}")
        mime = resp.headers.get("content-type", "image/jpeg").split(";")[0].strip()
        return resp.content, mime or "image/jpeg"


@registrar_handler("bg_remove")
async def _handler_bg_remove(telefono: str, params: dict[str, Any]) -> int | None:
    """
    Handler de eliminación de fondo.

    params:
      - source_url (str): URL pública/firmada de la imagen original
      - source_mime (str)
      - source_asset_id (int | None)
      - costo_creditos (int)
    """
    from agent.creativos.bg_remove import remove_background, PhotoroomError
    from agent import storage

    source_url = (params.get("source_url") or "").strip()
    source_mime = params.get("source_mime") or "image/jpeg"
    costo_creditos = int(params.get("costo_creditos", 0))

    if not source_url:
        raise ValueError("bg_remove: source_url vacío")

    proveedor = _proveedor_whatsapp()

    # 1) Descargar la imagen fuente
    try:
        src_bytes, src_mime_real = await _descargar_url(source_url)
    except Exception as e:
        logger.exception(f"[HANDLER bg_remove] Error descargando source: {e}")
        await _reembolsar(telefono, costo_creditos, "no pude descargar tu imagen", scope="bg_remove")
        try:
            nota = f"Te devolví el *{costo_creditos}* crédito. " if costo_creditos > 0 else ""
            await proveedor.enviar_mensaje(
                telefono,
                f"⚠️ No pude descargar tu imagen para procesarla. "
                f"{nota}Intenta enviarla de nuevo.",
            )
        except Exception:
            pass
        raise

    mime_efectivo = src_mime_real or source_mime

    # 2) Procesar con Photoroom
    try:
        out_bytes, meta = await remove_background(src_bytes, mime_type=mime_efectivo)
    except PhotoroomError as e:
        logger.error(f"[HANDLER bg_remove] Photoroom error: {e}")
        await _reembolsar(telefono, costo_creditos, "provider falló", scope="bg_remove")
        try:
            nota = f"Te devolví el *{costo_creditos}* crédito. " if costo_creditos > 0 else ""
            await proveedor.enviar_mensaje(
                telefono,
                f"⚠️ No pude quitar el fondo (el servicio rechazó la imagen o hubo un error temporal). "
                f"{nota}Prueba con otra imagen o escribe *dona soporte* si crees que es un bug.",
            )
        except Exception:
            pass
        raise

    # 3) Subir el resultado
    try:
        guardado = await storage.subir_asset(
            telefono=telefono,
            tipo="image",
            contenido=out_bytes,
            mime_type=meta.get("mime_type", "image/png"),
            nombre_sugerido="sin_fondo.png",
        )
    except Exception as e:
        logger.exception(f"[HANDLER bg_remove] Error subiendo resultado: {e}")
        await _reembolsar(telefono, costo_creditos, "fallo al guardar", scope="bg_remove")
        try:
            nota = f"Te devolví el *{costo_creditos}* crédito. " if costo_creditos > 0 else ""
            await proveedor.enviar_mensaje(
                telefono,
                f"⚠️ Procesé la imagen pero no pude guardarla. "
                f"{nota}Intenta de nuevo en un momento.",
            )
        except Exception:
            pass
        raise

    # 4) Registrar
    asset_id = await storage.registrar_asset(
        telefono=telefono,
        tipo="image",
        guardado=guardado,
        prompt="bg_remove",
        modelo=meta.get("modelo", "photoroom"),
        costo_creditos=costo_creditos,
        meta={
            "operacion": "bg_remove",
            "source_asset_id": params.get("source_asset_id"),
            "placeholder": meta.get("placeholder", False),
        },
    )

    # 5) Enviar por WhatsApp
    caption = "✂️ Sin fondo"
    ok = False
    if guardado.backend == "r2" and guardado.url_publica.startswith("http"):
        ok = await proveedor.enviar_imagen(
            telefono,
            url=guardado.url_publica,
            caption=caption,
            mime_type=guardado.mime_type,
        )
    if not ok:
        ok = await proveedor.enviar_imagen(
            telefono,
            imagen_bytes=out_bytes,
            caption=caption,
            mime_type=guardado.mime_type,
        )
    if not ok:
        await proveedor.enviar_mensaje(
            telefono,
            f"✅ Imagen lista (sin fondo):\n{guardado.url_publica}",
        )

    logger.info(f"[HANDLER bg_remove] asset_id={asset_id} enviado a {telefono}")
    return asset_id


# ── gen_voz (ElevenLabs) ────────────────────────────────────────────────────

@registrar_handler("gen_voz")
async def _handler_gen_voz(telefono: str, params: dict[str, Any]) -> int | None:
    """
    Handler de text-to-speech.

    params:
      - texto (str)
      - voice_id (str)
      - costo_creditos (int)
    """
    from agent.creativos.voz import text_to_speech, ElevenLabsError
    from agent import storage

    texto = (params.get("texto") or "").strip()
    voice_id = params.get("voice_id")
    costo_creditos = int(params.get("costo_creditos", 0))

    if not texto:
        raise ValueError("gen_voz: texto vacío")

    proveedor = _proveedor_whatsapp()

    # 1) Generar audio
    try:
        audio_bytes, meta = await text_to_speech(texto, voice_id=voice_id)
    except ElevenLabsError as e:
        logger.error(f"[HANDLER gen_voz] ElevenLabs error: {e}")
        await _reembolsar(telefono, costo_creditos, "provider falló", scope="gen_voz")
        try:
            nota = f"Te devolví los *{costo_creditos}* créditos. " if costo_creditos > 0 else ""
            await proveedor.enviar_mensaje(
                telefono,
                f"⚠️ No pude generar la nota de voz (error del servicio). "
                f"{nota}Intenta de nuevo en un momento.",
            )
        except Exception:
            pass
        raise

    # 2) Subir
    try:
        guardado = await storage.subir_asset(
            telefono=telefono,
            tipo="audio",
            contenido=audio_bytes,
            mime_type=meta.get("mime_type", "audio/mpeg"),
            nombre_sugerido="voz.mp3",
        )
    except Exception as e:
        logger.exception(f"[HANDLER gen_voz] Error subiendo audio: {e}")
        await _reembolsar(telefono, costo_creditos, "fallo al guardar", scope="gen_voz")
        try:
            nota = f"Te devolví los *{costo_creditos}* créditos. " if costo_creditos > 0 else ""
            await proveedor.enviar_mensaje(
                telefono,
                f"⚠️ Generé el audio pero no pude guardarlo. "
                f"{nota}Intenta de nuevo.",
            )
        except Exception:
            pass
        raise

    # 3) Registrar
    asset_id = await storage.registrar_asset(
        telefono=telefono,
        tipo="audio",
        guardado=guardado,
        prompt=texto[:4000],
        modelo=meta.get("modelo", ""),
        costo_creditos=costo_creditos,
        meta={
            "voice_id": meta.get("voice_id"),
            "chars": meta.get("chars"),
            "placeholder": meta.get("placeholder", False),
        },
    )

    # 4) Enviar como nota de voz. Si el proveedor no soporta, fallback a texto+URL.
    ok = await proveedor.enviar_audio(
        telefono,
        audio_bytes=audio_bytes,
        mime_type=meta.get("mime_type", "audio/mpeg"),
    )
    if not ok:
        if guardado.backend == "r2" and guardado.url_publica.startswith("http"):
            await proveedor.enviar_mensaje(
                telefono,
                f"🎙️ Nota de voz lista:\n{guardado.url_publica}",
            )
        else:
            await proveedor.enviar_mensaje(
                telefono,
                "🎙️ Generé el audio pero tu proveedor de WhatsApp no permitió enviarlo.",
            )

    logger.info(f"[HANDLER gen_voz] asset_id={asset_id} enviado a {telefono}")
    return asset_id


# ── gen_documento (reportlab PDF) ───────────────────────────────────────────

@registrar_handler("gen_documento")
async def _handler_gen_documento(telefono: str, params: dict[str, Any]) -> int | None:
    """
    Handler de generación de documentos PDF (factura/presupuesto/recibo).

    params:
      - tipo (str): "factura" | "presupuesto" | "recibo"
      - datos (dict): {cliente, items, ...} ya normalizados
      - emisor (dict): {nombre_negocio, moneda, ...}
      - costo_creditos (int)
    """
    from agent.creativos.pdf import generar_pdf, PDFError
    from agent import storage

    tipo = (params.get("tipo") or "factura").lower()
    datos = params.get("datos") or {}
    emisor = params.get("emisor") or {}
    costo_creditos = int(params.get("costo_creditos", 0))

    proveedor = _proveedor_whatsapp()

    # 1) Generar PDF
    try:
        pdf_bytes, meta = await generar_pdf(tipo, datos, emisor=emisor)
    except PDFError as e:
        logger.error(f"[HANDLER gen_documento] PDF error: {e}")
        await _reembolsar(telefono, costo_creditos, str(e)[:80], scope="gen_documento")
        try:
            nota = f"Te devolví los *{costo_creditos}* créditos. " if costo_creditos > 0 else ""
            await proveedor.enviar_mensaje(
                telefono,
                f"⚠️ No pude generar el documento (faltan datos o hubo un error). "
                f"{nota}Intenta con un pedido más claro (cliente, ítems y montos).",
            )
        except Exception:
            pass
        raise

    folio = meta.get("folio", "documento")
    filename = f"{tipo}_{folio}.pdf"

    # 2) Subir
    try:
        guardado = await storage.subir_asset(
            telefono=telefono,
            tipo="document",
            contenido=pdf_bytes,
            mime_type="application/pdf",
            nombre_sugerido=filename,
        )
    except Exception as e:
        logger.exception(f"[HANDLER gen_documento] Error subiendo PDF: {e}")
        await _reembolsar(telefono, costo_creditos, "fallo al guardar", scope="gen_documento")
        try:
            nota = f"Te devolví los *{costo_creditos}* créditos. " if costo_creditos > 0 else ""
            await proveedor.enviar_mensaje(
                telefono,
                f"⚠️ Generé el PDF pero no pude guardarlo. {nota}Intenta de nuevo.",
            )
        except Exception:
            pass
        raise

    # 3) Registrar
    cliente = (datos.get("cliente") or {}).get("nombre", "")
    asset_id = await storage.registrar_asset(
        telefono=telefono,
        tipo="document",
        guardado=guardado,
        prompt=f"{tipo} para {cliente}"[:200],
        modelo=meta.get("modelo", "reportlab"),
        costo_creditos=costo_creditos,
        meta={
            "operacion": "gen_documento",
            "tipo_doc": tipo,
            "folio": folio,
            "total": meta.get("total"),
            "moneda": meta.get("moneda"),
            "placeholder": meta.get("placeholder", False),
        },
    )

    # 4) Enviar por WhatsApp
    total_str = f"${meta.get('total', 0):,.2f} {meta.get('moneda', 'USD')}"
    caption = f"{tipo.capitalize()} #{folio} — {total_str}"

    ok = await proveedor.enviar_documento(
        telefono,
        archivo_bytes=pdf_bytes,
        filename=filename,
        mime_type="application/pdf",
        caption=caption,
    )
    if not ok:
        # Fallback: si el proveedor no soporta, mandar link o mensaje
        if guardado.backend == "r2" and guardado.url_publica.startswith("http"):
            await proveedor.enviar_mensaje(
                telefono,
                f"📄 *{tipo.capitalize()} lista #{folio}*\n{total_str}\n\n{guardado.url_publica}",
            )
        else:
            await proveedor.enviar_mensaje(
                telefono,
                f"📄 Generé el {tipo} #{folio} ({total_str}) pero tu proveedor de "
                f"WhatsApp no permitió enviarlo como adjunto. Revisa en /admin/jobs.",
            )

    logger.info(f"[HANDLER gen_documento] asset_id={asset_id} folio={folio} enviado a {telefono}")
    return asset_id


# ── gen_video (Replicate) ───────────────────────────────────────────────────

@registrar_handler("gen_video")
async def _handler_gen_video(telefono: str, params: dict[str, Any]) -> int | None:
    """
    Handler de generación de video corto (Replicate).

    params:
      - prompt (str): prompt optimizado (en inglés) listo para Replicate
      - image_url (str): opcional, para image-to-video
      - duration_s (int): duración en segundos (5 o 10)
      - costo_creditos (int)
    """
    from agent.creativos.video import generar_video, ReplicateError
    from agent import storage

    prompt = (params.get("prompt") or "").strip()
    image_url = params.get("image_url") or ""
    duration_s = int(params.get("duration_s") or 0)
    aspect_ratio = (params.get("aspect_ratio") or "").strip()
    costo_creditos = int(params.get("costo_creditos", 0))

    if not prompt:
        raise ValueError("gen_video: prompt vacío")

    proveedor = _proveedor_whatsapp()

    # 1) Generar
    try:
        video_bytes, meta = await generar_video(
            prompt, image_url=image_url, duration_s=duration_s,
            aspect_ratio=aspect_ratio,
        )
    except ReplicateError as e:
        logger.error(f"[HANDLER gen_video] Replicate error: {e}")
        await _reembolsar(telefono, costo_creditos, str(e)[:80], scope="gen_video")
        try:
            nota = f"Te devolví los *{costo_creditos}* créditos. " if costo_creditos > 0 else ""
            await proveedor.enviar_mensaje(
                telefono,
                f"⚠️ No pude generar el video (el modelo falló o rechazó el prompt). "
                f"{nota}Prueba reformulando o escribe *dona soporte* si crees que es un bug.",
            )
        except Exception:
            pass
        raise

    # 2) Subir
    try:
        guardado = await storage.subir_asset(
            telefono=telefono,
            tipo="video",
            contenido=video_bytes,
            mime_type=meta.get("mime_type", "video/mp4"),
            nombre_sugerido="video.mp4",
        )
    except Exception as e:
        logger.exception(f"[HANDLER gen_video] Error subiendo video: {e}")
        await _reembolsar(telefono, costo_creditos, "fallo al guardar", scope="gen_video")
        try:
            nota = f"Te devolví los *{costo_creditos}* créditos. " if costo_creditos > 0 else ""
            await proveedor.enviar_mensaje(
                telefono,
                f"⚠️ Generé el video pero no pude guardarlo. {nota}Intenta de nuevo.",
            )
        except Exception:
            pass
        raise

    # 3) Registrar
    asset_id = await storage.registrar_asset(
        telefono=telefono,
        tipo="video",
        guardado=guardado,
        prompt=prompt[:1000],
        modelo=meta.get("modelo", ""),
        costo_creditos=costo_creditos,
        meta={
            "operacion": "gen_video",
            "prediction_id": meta.get("prediction_id"),
            "predict_time_s": meta.get("predict_time_s"),
            "placeholder": meta.get("placeholder", False),
            "image_url": image_url or None,
        },
    )

    # 4) Enviar por WhatsApp
    caption = f"🎬 {prompt[:900]}"
    ok = False
    if guardado.backend == "r2" and guardado.url_publica.startswith("http"):
        ok = await proveedor.enviar_video(
            telefono,
            url=guardado.url_publica,
            caption=caption,
            mime_type=guardado.mime_type,
        )
    if not ok:
        ok = await proveedor.enviar_video(
            telefono,
            video_bytes=video_bytes,
            caption=caption,
            mime_type=guardado.mime_type,
        )
    if not ok:
        if guardado.backend == "r2" and guardado.url_publica.startswith("http"):
            await proveedor.enviar_mensaje(
                telefono,
                f"✅ Video listo:\n{guardado.url_publica}\n\n🎬 {prompt[:200]}",
            )
        else:
            await proveedor.enviar_mensaje(
                telefono,
                "🎬 Generé el video pero tu proveedor de WhatsApp no permitió enviarlo como adjunto.",
            )

    logger.info(f"[HANDLER gen_video] asset_id={asset_id} enviado a {telefono}")
    return asset_id


# ── gen_video_avatar (HeyGen) ───────────────────────────────────────────────

@registrar_handler("gen_video_avatar")
async def _handler_gen_video_avatar(telefono: str, params: dict[str, Any]) -> int | None:
    """
    Handler de generación de video con avatar AI (HeyGen).

    params:
      - texto (str): guion que lee el avatar
      - avatar_id (str)
      - voice_id (str)
      - costo_creditos (int)
    """
    from agent.creativos.video_avatar import generar_video_avatar, HeyGenError
    from agent import storage

    texto = (params.get("texto") or "").strip()
    avatar_id = params.get("avatar_id") or ""
    voice_id = params.get("voice_id") or ""
    costo_creditos = int(params.get("costo_creditos", 0))

    if not texto:
        raise ValueError("gen_video_avatar: texto vacío")

    proveedor = _proveedor_whatsapp()

    # 1) Generar
    try:
        video_bytes, meta = await generar_video_avatar(
            texto, avatar_id=avatar_id, voice_id=voice_id,
        )
    except HeyGenError as e:
        logger.error(f"[HANDLER gen_video_avatar] HeyGen error: {e}")
        await _reembolsar(telefono, costo_creditos, str(e)[:80], scope="gen_video_avatar")
        try:
            nota = f"Te devolví los *{costo_creditos}* créditos. " if costo_creditos > 0 else ""
            await proveedor.enviar_mensaje(
                telefono,
                f"⚠️ No pude grabar el video con avatar (el servicio falló). "
                f"{nota}Intenta de nuevo en un momento.",
            )
        except Exception:
            pass
        raise

    # 2) Subir
    try:
        guardado = await storage.subir_asset(
            telefono=telefono,
            tipo="video",
            contenido=video_bytes,
            mime_type=meta.get("mime_type", "video/mp4"),
            nombre_sugerido="avatar.mp4",
        )
    except Exception as e:
        logger.exception(f"[HANDLER gen_video_avatar] Error subiendo video: {e}")
        await _reembolsar(telefono, costo_creditos, "fallo al guardar", scope="gen_video_avatar")
        try:
            nota = f"Te devolví los *{costo_creditos}* créditos. " if costo_creditos > 0 else ""
            await proveedor.enviar_mensaje(
                telefono,
                f"⚠️ Grabé el video pero no pude guardarlo. {nota}Intenta de nuevo.",
            )
        except Exception:
            pass
        raise

    # 3) Registrar
    asset_id = await storage.registrar_asset(
        telefono=telefono,
        tipo="video",
        guardado=guardado,
        prompt=texto[:1500],
        modelo=meta.get("modelo", "heygen"),
        costo_creditos=costo_creditos,
        meta={
            "operacion": "gen_video_avatar",
            "video_id": meta.get("video_id"),
            "avatar_id": meta.get("avatar_id"),
            "voice_id": meta.get("voice_id"),
            "duracion_s": meta.get("duracion_s"),
            "placeholder": meta.get("placeholder", False),
        },
    )

    # 4) Enviar por WhatsApp
    caption = f"🎥 {texto[:900]}"
    ok = False
    if guardado.backend == "r2" and guardado.url_publica.startswith("http"):
        ok = await proveedor.enviar_video(
            telefono,
            url=guardado.url_publica,
            caption=caption,
            mime_type=guardado.mime_type,
        )
    if not ok:
        ok = await proveedor.enviar_video(
            telefono,
            video_bytes=video_bytes,
            caption=caption,
            mime_type=guardado.mime_type,
        )
    if not ok:
        if guardado.backend == "r2" and guardado.url_publica.startswith("http"):
            await proveedor.enviar_mensaje(
                telefono,
                f"✅ Video con avatar listo:\n{guardado.url_publica}",
            )
        else:
            await proveedor.enviar_mensaje(
                telefono,
                "🎥 Grabé el video pero tu proveedor de WhatsApp no permitió enviarlo como adjunto.",
            )

    logger.info(f"[HANDLER gen_video_avatar] asset_id={asset_id} enviado a {telefono}")
    return asset_id
