# agent/web_agent/tareas/consultar_pagina_publica.py

"""
Tarea de ejemplo: abre una URL pública, extrae título y meta-description.

Útil como:
  - Smoke test del runner de Playwright (no requiere login ni cookies).
  - Plantilla mínima para implementar tareas reales (portales, POS legacy, etc).

Parámetros esperados:
  - `url` (str): URL pública a consultar (http/https).
  - `timeout_ms` (int, opcional, default 15000): máximo tiempo de carga.
"""

from agent.web_agent.base import ContextoTarea, ResultadoTarea, WebAgentTarea
from agent.web_agent.registro import registrar


class ConsultarPaginaPublica(WebAgentTarea):
    nombre = "consultar_pagina_publica"

    async def ejecutar(self, contexto: ContextoTarea, parametros: dict) -> ResultadoTarea:
        url = (parametros or {}).get("url", "").strip()
        if not url or not (url.startswith("http://") or url.startswith("https://")):
            return ResultadoTarea(
                exito=False,
                mensaje="Falta parámetro 'url' o no empieza con http(s)://",
            )
        timeout_ms = int((parametros or {}).get("timeout_ms", 15000))

        page = contexto.page
        if page is None:
            # Caso raro: el runner no inyectó page (debería, pero defensivo)
            return ResultadoTarea(
                exito=False,
                mensaje="Runner no proveyó Playwright Page",
            )

        await page.goto(url, timeout=timeout_ms, wait_until="domcontentloaded")
        titulo = await page.title()

        # meta description es best-effort — no todas las páginas la traen
        try:
            descripcion = await page.locator(
                'meta[name="description"]'
            ).first.get_attribute("content", timeout=2000)
        except Exception:
            descripcion = None

        return ResultadoTarea(
            exito=True,
            datos={
                "url": url,
                "titulo": titulo or "",
                "descripcion": descripcion or "",
            },
            mensaje=f"'{titulo or url}' cargado OK",
        )


# Auto-registro al importar
registrar(ConsultarPaginaPublica())
