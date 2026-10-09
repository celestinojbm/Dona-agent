# tests/test_deploy_msi.py — J5 · el paquete de la MSI cumple sus reglas
#
# Valida deploy/msi/ sin Docker (corre en CI): exposición solo en loopback,
# Redis sin puertos, imagen atada a un SHA, efectos apagados en el env de
# ejemplo, ningún comando que borre volúmenes y ningún secreto con valor.

import re
from pathlib import Path

import yaml

from agent.efectos import INTERRUPTORES

DIR = Path(__file__).resolve().parent.parent / "deploy" / "msi"


def _compose() -> dict:
    return yaml.safe_load((DIR / "compose.yml").read_text(encoding="utf-8"))


def test_proyecto_y_etiquetas_propias():
    cfg = _compose()
    assert cfg["name"] == "dona"
    for nombre, svc in cfg["services"].items():
        assert nombre.startswith("dona-")
        assert svc.get("container_name", nombre).startswith("dona-")
        assert svc["labels"]["com.dona.stack"] == "staging"
    assert set(cfg["volumes"]) == {"dona-assets", "dona-redis"}
    assert all(v["name"].startswith("dona-") for v in cfg["volumes"].values())


def test_puertos_solo_en_loopback_y_redis_sin_puertos():
    servicios = _compose()["services"]
    publicados = [(n, p) for n, s in servicios.items() for p in s.get("ports", [])]
    assert publicados, "dona-api debe publicar su puerto en loopback"
    for nombre, puerto in publicados:
        assert str(puerto).startswith("127.0.0.1:"), f"{nombre} publica {puerto}"
    assert not servicios["dona-redis"].get("ports")
    assert not servicios["dona-worker"].get("ports")


def test_imagen_atada_a_un_sha_obligatorio():
    for nombre in ("dona-api", "dona-worker"):
        imagen = _compose()["services"][nombre]["image"]
        assert imagen.startswith("dona-api:${DONA_SHA:?"), imagen
    assert "latest" not in (DIR / "compose.yml").read_text(encoding="utf-8")


def test_scheduler_solo_en_la_api():
    worker = _compose()["services"]["dona-worker"]
    assert worker["environment"]["DONA_SCHEDULER_ENABLED"] == "false"


def test_ningun_script_borra_volumenes_ni_purga():
    prohibido = re.compile(r"down\s+(-v|--volumes)|volume\s+rm|system\s+prune|volume\s+prune|rm\s+-rf\s+/")
    for script in DIR.glob("*.sh"):
        texto = script.read_text(encoding="utf-8")
        lineas = [ln for ln in texto.splitlines() if not ln.lstrip().startswith("#")]
        assert not prohibido.search("\n".join(lineas)), script.name
        assert texto.startswith("#!/usr/bin/env bash"), script.name
        assert "set -euo pipefail" in texto, script.name


def test_env_de_ejemplo_con_efectos_apagados_y_sin_valores_secretos():
    texto = (DIR / "dona.env.example").read_text(encoding="utf-8")
    pares = dict(
        ln.split("=", 1) for ln in texto.splitlines() if ln and not ln.startswith("#") and "=" in ln
    )
    for var in INTERRUPTORES.values():
        assert pares.get(var) == "false", var
    for secreto in ("DATABASE_URL", "ENCRYPTION_KEY", "INTERNAL_BRIDGE_SECRET", "ADMIN_TOKEN"):
        assert pares.get(secreto) == "", f"{secreto} no debe traer valor en el ejemplo"
    for clave in pares:
        assert not clave.startswith(("STRIPE_", "WHAPI_", "META_", "ANTHROPIC_", "OPENAI_")), clave
