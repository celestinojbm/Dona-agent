from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from scripts.validate_agent_runs import validar_agent_runs


def copiar_agent_runs(tmp_path: Path) -> Path:
    origen = Path("docs/ops/agent-runs")
    destino = tmp_path / "agent-runs"
    shutil.copytree(origen, destino)
    return destino


def test_valida_index_y_ledgers_actuales() -> None:
    resultado = validar_agent_runs(Path("docs/ops/agent-runs"))

    assert resultado.ok is True
    assert resultado.total_runs >= 4
    assert resultado.errores == []


def run_minimo(run_id: str) -> dict[str, object]:
    return {
        "run_id": run_id,
        "fecha": "2026-05-25",
        "riesgo": "MEDIUM",
        "estado": "merged",
        "objetivo": "Probar que los runs nuevos requieren carpeta y ledgers mínimos.",
        "branch": "docs/test",
        "pr": 99,
        "commit": "abc1234",
        "agentes": ["Hermes"],
        "archivos_resumen": ["docs/ops/agent-runs/index.json"],
        "verificaciones": ["pytest: esperado"],
        "costo_estimado": "bajo",
        "riesgos_residuales": ["ninguno para test"],
        "proxima_accion": "Corregir ledgers faltantes.",
    }


def test_falla_si_un_run_del_index_no_tiene_carpeta(tmp_path: Path) -> None:
    agent_runs = copiar_agent_runs(tmp_path)
    index_path = agent_runs / "index.json"
    data = json.loads(index_path.read_text(encoding="utf-8"))
    data["runs"].append(run_minimo("2026-05-25-pr99-run-sin-carpeta"))
    index_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    resultado = validar_agent_runs(agent_runs)

    assert resultado.ok is False
    assert any("falta carpeta" in error for error in resultado.errores)


def test_falla_si_un_run_nuevo_no_tiene_ledgers_minimos(tmp_path: Path) -> None:
    agent_runs = copiar_agent_runs(tmp_path)
    index_path = agent_runs / "index.json"
    data = json.loads(index_path.read_text(encoding="utf-8"))
    data["runs"].append(run_minimo("2026-05-25-pr99-run-sin-ledgers"))
    index_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    (agent_runs / "2026-05-25-pr99-run-sin-ledgers").mkdir()

    resultado = validar_agent_runs(agent_runs)

    assert resultado.ok is False
    assert any("run-ledger.md" in error for error in resultado.errores)
    assert any("cost-ledger.md" in error for error in resultado.errores)
    assert any("tool-ledger.md" in error for error in resultado.errores)


def test_falla_si_index_contiene_patron_de_secret(tmp_path: Path) -> None:
    agent_runs = copiar_agent_runs(tmp_path)
    index_path = agent_runs / "index.json"
    texto = index_path.read_text(encoding="utf-8")
    nombre_campo = "api" + "_key"
    valor = "live" + "_credential_" + "1234567890"
    index_path.write_text(texto.replace("Indice estatico", f"{nombre_campo}: {valor}"), encoding="utf-8")

    resultado = validar_agent_runs(agent_runs)

    assert resultado.ok is False
    assert any("posible secret" in error.lower() for error in resultado.errores)


def test_falla_si_falta_campo_requerido_en_index(tmp_path: Path) -> None:
    agent_runs = copiar_agent_runs(tmp_path)
    index_path = agent_runs / "index.json"
    data = json.loads(index_path.read_text(encoding="utf-8"))
    del data["runs"][0]["proxima_accion"]
    index_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    resultado = validar_agent_runs(agent_runs)

    assert resultado.ok is False
    assert any("proxima_accion" in error for error in resultado.errores)


def test_falla_si_hay_run_id_duplicado(tmp_path: Path) -> None:
    """Dos entradas con el mismo run_id corrompen el ledger (evidencia
    ambigua). Propuesto por el scout autónomo de Phase 4 (2026-06-12)."""
    agent_runs = copiar_agent_runs(tmp_path)
    index_path = agent_runs / "index.json"
    data = json.loads(index_path.read_text(encoding="utf-8"))
    # Duplicar un run EXISTENTE: su carpeta/ledgers ya existen, así que el
    # único error nuevo posible es el run_id duplicado.
    data["runs"].append(dict(data["runs"][0]))
    index_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    resultado = validar_agent_runs(agent_runs)

    assert resultado.ok is False
    assert any("run_id duplicado" in error for error in resultado.errores)
