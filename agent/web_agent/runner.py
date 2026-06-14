# agent/web_agent/runner.py — Runner de tareas web con Playwright

"""
Orquestador que ejecuta una tarea registrada:
  1. Lanza Playwright (Chromium headless).
  2. Carga cookies cifradas del usuario (si existen).
  3. Ejecuta la tarea.
  4. Persiste cookies actualizadas al terminar.

Playwright es una dependencia *opcional* — si no está instalada, el runner
retorna un ResultadoTarea con `exito=False` y un mensaje explicativo.
Esto permite que Dona siga funcionando en entornos (ej. Render Free Tier)
donde todavía no se desplegó Playwright.

Para habilitarlo:
    pip install playwright
    python -m playwright install chromium
"""

import logging

from agent.web_agent.base import ContextoTarea, ResultadoTarea
from agent.web_agent.registro import obtener as obtener_tarea
from agent.web_agent import session as _session

logger = logging.getLogger("dona")


def _playwright_disponible() -> bool:
    try:
        import playwright  # noqa: F401
        return True
    except ImportError:
        return False


async def ejecutar_tarea(
    nombre: str,
    telefono: str,
    parametros: dict,
    dominio: str = "",
    solicitar_mfa=None,
    headless: bool = True,
) -> ResultadoTarea:
    """
    Ejecuta la tarea `nombre` para `telefono` con `parametros`.

    Args:
        dominio: si se indica, se cargan/persisten cookies de ese dominio.
        solicitar_mfa: callback async(prompt:str)->str|None. Lo pasa el caller
                       si puede hacer MFA human-in-the-loop por WhatsApp.
        headless: si es False, abre ventana visible (solo para debug local).
    """
    tarea = obtener_tarea(nombre)
    if tarea is None:
        return ResultadoTarea(
            exito=False,
            mensaje=f"Tarea web '{nombre}' no registrada",
        )

    if not _playwright_disponible():
        return ResultadoTarea(
            exito=False,
            mensaje=(
                "Playwright no está instalado en este entorno. "
                "Instala con `pip install playwright && python -m playwright install chromium`."
            ),
        )

    # Import tardío para no explotar al importar este módulo cuando Playwright no existe
    from playwright.async_api import async_playwright

    cookies_prev = await _session.cargar_sesion(telefono, dominio) if dominio else []

    try:
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=headless)
            context = await browser.new_context()
            if cookies_prev:
                try:
                    await context.add_cookies(cookies_prev)
                except Exception as e_cookie:
                    logger.warning(f"[WEB_AGENT] cookies inválidas, se ignoran: {e_cookie}")

            page = await context.new_page()

            ctx = ContextoTarea(
                telefono=telefono,
                page=page,
                cookies=cookies_prev,
                solicitar_mfa=solicitar_mfa,
            )

            try:
                resultado = await tarea.ejecutar(ctx, parametros)
            except Exception as e:
                logger.error(f"[WEB_AGENT] tarea '{nombre}' falló: {type(e).__name__}: {e}")
                resultado = ResultadoTarea(
                    exito=False,
                    mensaje=f"Error durante la tarea: {type(e).__name__}",
                )

            # Capturar cookies actualizadas antes de cerrar
            try:
                cookies_final = await context.cookies()
                resultado.cookies_actualizadas = cookies_final
            except Exception:
                cookies_final = []

            await browser.close()
    except Exception as e_browser:
        logger.error(f"[WEB_AGENT] No se pudo iniciar browser: {e_browser}")
        return ResultadoTarea(
            exito=False,
            mensaje=f"No se pudo iniciar el navegador: {type(e_browser).__name__}",
        )

    # Persistir cookies si la tarea fue bien y hay dominio
    if resultado.exito and dominio and resultado.cookies_actualizadas:
        try:
            await _session.guardar_sesion(
                telefono, dominio, resultado.cookies_actualizadas
            )
        except Exception as e_save:
            logger.warning(f"[WEB_AGENT] no se pudieron guardar cookies: {e_save}")

    return resultado
