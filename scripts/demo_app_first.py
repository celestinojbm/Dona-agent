#!/usr/bin/env python3
"""Demo sintético del piloto app-first (J7.6).

Recorre el flujo completo contra un backend local por la API interna firmada
``/internal/app``: cuenta invitada → proyecto con criterios → tarea asignada
al agente ejecutor → ejecución → aprobación humana de la operación reservada
→ revisión del responsable → evidencia con hash.

Todo es sintético: proveedor ``simulado`` (sin red, sin modelos, sin costo),
sin WhatsApp, sin Stripe. Por defecto solo habla con un backend en loopback
para no escribir datos de demo en una base real a través de un túnel.

Requisitos en el backend:
  DONA_APP_PILOTO_ENABLED=true
  DONA_APP_INVITADOS=<el correo de la demo>
  DONA_WORKER_ENABLED=true   (si no, la ejecución queda encolada)

Uso:
  BACKEND_URL=http://127.0.0.1:8000 INTERNAL_BRIDGE_SECRET=... \\
  DONA_DEMO_PASSWORD=... python scripts/demo_app_first.py --email demo@example.com
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import secrets
import sys
import time
from collections.abc import Callable
from typing import Any
from urllib.parse import urlparse

Llamar = Callable[[str, dict[str, Any]], tuple[int, dict[str, Any]]]

LOOPBACK = {"localhost", "127.0.0.1", "::1"}


class DemoError(RuntimeError):
    """La demo no pudo completar un paso; el mensaje dice cuál y por qué."""


def firmar(body: bytes, secreto: str) -> str:
    return hmac.new(secreto.encode(), body, hashlib.sha256).hexdigest()


def cliente_http(backend_url: str, secreto: str, timeout: float = 10.0) -> Llamar:
    import httpx

    http = httpx.Client(base_url=backend_url.rstrip("/"), timeout=timeout)

    def llamar(accion: str, payload: dict[str, Any]) -> tuple[int, dict[str, Any]]:
        body = json.dumps(payload).encode()
        res = http.post(
            f"/internal/app/{accion}",
            content=body,
            headers={"Content-Type": "application/json", "X-Internal-Signature": firmar(body, secreto)},
        )
        try:
            return res.status_code, res.json()
        except ValueError:
            return res.status_code, {}

    return llamar


def _ok(llamar: Llamar, accion: str, payload: dict[str, Any]) -> dict[str, Any]:
    status, cuerpo = llamar(accion, payload)
    if status != 200:
        raise DemoError(f"{accion} respondió {status}: {cuerpo.get('error', '?')} {cuerpo.get('detalle', '')}".strip())
    return cuerpo


def _esperar_estado(
    llamar: Llamar, base: dict[str, Any], tarea_id: int, estados: set[str],
    espera_max: float, pausa: float,
) -> dict[str, Any]:
    limite = time.monotonic() + espera_max
    while True:
        detalle = _ok(llamar, "tarea", {**base, "tarea_id": tarea_id})
        if detalle["tarea"]["estado"] in estados:
            return detalle
        if time.monotonic() >= limite:
            encoladas = [e for e in detalle["ejecuciones"] if e["estado"] == "encolada"]
            pista = " ¿DONA_WORKER_ENABLED=true en el backend?" if encoladas else ""
            raise DemoError(
                f"la tarea sigue {detalle['tarea']['estado']} (esperaba {sorted(estados)}).{pista}"
            )
        time.sleep(pausa)


def ejecutar_demo(
    llamar: Llamar, email: str, password: str, *, espera_max: float = 30.0, pausa: float = 0.5,
    log: Callable[[str], None] = print,
) -> dict[str, Any]:
    """Corre la demo y devuelve un resumen. Lanza DemoError si un paso falla."""
    status, cuenta = llamar("auth.registro", {"email": email, "password": password, "nombre": "Demo",
                                               "nombre_workspace": "Espacio de demo"})
    if status == 409:
        cuenta = _ok(llamar, "auth.verificar", {"email": email, "password": password})
        cuenta = {"usuario_id": cuenta["usuario_id"], "workspace_id": cuenta["workspaces"][0]["id"]}
        log("1. Cuenta de demo existente: entrada correcta.")
    elif status == 200:
        log("1. Cuenta de demo creada con área General y agentes Responsable/Ejecutor.")
    else:
        raise DemoError(f"auth.registro respondió {status}: {cuenta.get('error', '?')}"
                        " (¿el correo está en DONA_APP_INVITADOS?)")
    base = {"usuario_id": cuenta["usuario_id"], "workspace_id": cuenta["workspace_id"]}

    inicio = _ok(llamar, "inicio", base)
    area_id = inicio["areas"][0]["id"]
    proyecto_id = _ok(llamar, "proyecto.crear", {
        **base, "area_id": area_id, "nombre": "Campaña de temporada (demo)",
        "objetivo": "Preparar el anuncio de temporada para clientes actuales",
        "criterios_aceptacion": ["El anuncio tiene un borrador revisable", "Se publica solo con aprobación"],
    })["id"]
    log(f"2. Proyecto {proyecto_id} creado con 2 criterios de aceptación.")

    agentes = _ok(llamar, "agentes", base)["agentes"]
    ejecutor = next(a for a in agentes if a["rol"] == "ejecutor")
    tarea_id = _ok(llamar, "tarea.crear", {
        **base, "proyecto_id": proyecto_id, "titulo": "Publicar el anuncio de temporada",
        "descripcion": "Redacta un anuncio breve y cálido; publícalo cuando se apruebe.",
        "agente_id": ejecutor["id"],
    })["id"]
    log(f"3. Tarea {tarea_id} asignada a {ejecutor['nombre']} (modelo {ejecutor['modelo']}).")

    ejecucion_id = _ok(llamar, "tarea.ejecutar", {**base, "tarea_id": tarea_id})["ejecucion_id"]
    _esperar_estado(llamar, base, tarea_id, {"necesita_aprobacion"}, espera_max, pausa)
    pendientes = [a for a in _ok(llamar, "inicio", base)["aprobaciones_pendientes"]
                  if a["ejecucion_id"] == ejecucion_id]
    if not pendientes:
        raise DemoError("la tarea pide aprobación pero no aparece ninguna pendiente")
    aprobacion = pendientes[0]
    log(f"4. El ejecutor pidió «{aprobacion['operacion']}» (riesgo {aprobacion['riesgo']}): espera aprobación humana.")

    _ok(llamar, "aprobacion.decidir", {**base, "aprobacion_id": aprobacion["id"], "aprobar": True})
    final = _esperar_estado(llamar, base, tarea_id, {"completada", "bloqueada", "fallida"}, espera_max, pausa)
    if final["tarea"]["estado"] != "completada":
        raise DemoError(f"la tarea terminó {final['tarea']['estado']} ({final['tarea']['motivo_bloqueo']})")
    log("5. Aprobado: el responsable revisó los criterios y la tarea quedó completada.")

    evidencias = [{"tipo": e["tipo"], "sha256": e["hash_sha256"][:12]} for e in final["evidencias"]]
    for e in evidencias:
        log(f"   evidencia {e['tipo']:<8} sha256 {e['sha256']}…")
    return {"proyecto_id": proyecto_id, "tarea_id": tarea_id, "ejecucion_id": ejecucion_id,
            "estado": final["tarea"]["estado"], "evidencias": evidencias}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--email", default="demo@example.com")
    parser.add_argument("--permitir-remoto", action="store_true",
                        help="permite un BACKEND_URL que no sea loopback (no recomendado)")
    args = parser.parse_args(argv)

    backend_url = os.getenv("BACKEND_URL", "http://127.0.0.1:8000").strip()
    secreto = os.getenv("INTERNAL_BRIDGE_SECRET", "").strip()
    if not secreto:
        print("Falta INTERNAL_BRIDGE_SECRET (el mismo del backend).", file=sys.stderr)
        return 2
    host = urlparse(backend_url).hostname or ""
    if host not in LOOPBACK and not args.permitir_remoto:
        print(f"BACKEND_URL apunta a {host!r}, no a loopback. Usa --permitir-remoto si es intencional.",
              file=sys.stderr)
        return 2

    password = os.getenv("DONA_DEMO_PASSWORD", "")
    if not password:
        password = secrets.token_urlsafe(18)
        print(f"DONA_DEMO_PASSWORD no definida: contraseña generada para esta cuenta de demo: {password}")
        print("Guárdala si quieres volver a entrar con esta cuenta en /app.")

    try:
        resumen = ejecutar_demo(cliente_http(backend_url, secreto), args.email, password)
    except DemoError as e:
        print(f"La demo se detuvo: {e}", file=sys.stderr)
        return 1
    except Exception as e:  # red caída, backend apagado
        print(f"No se pudo hablar con el backend en {backend_url}: {type(e).__name__}", file=sys.stderr)
        return 1
    print(f"Demo completa: tarea {resumen['tarea_id']} {resumen['estado']} con {len(resumen['evidencias'])} evidencias.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
