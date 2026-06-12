#!/usr/bin/env python3
"""Valida el índice estático de agent-runs y sus ledgers mínimos.

Este script es deliberadamente local/offline: no llama GitHub, Vercel,
producción ni servicios externos. Su objetivo es proteger el Control Room
contra metadata rota o accidentalmente sensible.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

CAMPOS_REQUERIDOS_RUN = {
    "run_id",
    "fecha",
    "riesgo",
    "estado",
    "objetivo",
    "branch",
    "pr",
    "commit",
    "agentes",
    "archivos_resumen",
    "verificaciones",
    "costo_estimado",
    "riesgos_residuales",
    "proxima_accion",
}

LEDGERS_MINIMOS = ("run-ledger.md", "cost-ledger.md", "tool-ledger.md")
RIESGOS_VALIDOS = {"LOW", "MEDIUM", "HIGH", "CRITICAL"}
ESTADOS_VALIDOS = {"merged", "open", "draft", "blocked", "cancelled", "completed"}
PATRONES_SECRET = {
    "possible_github_token": re.compile(r"gh[pousr]_[A-Za-z0-9_]{20,}"),
    "private_key": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    "common_live_secret": re.compile(
        r"(?i)(api[_-]?key|secret|token|password)\s*[:=]\s*[A-Za-z0-9_\-]{16,}"
    ),
}


@dataclass(frozen=True)
class ResultadoValidacion:
    ok: bool
    total_runs: int
    errores: list[str]


def _leer_json(index_path: Path, errores: list[str]) -> dict[str, Any]:
    try:
        data = json.loads(index_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        errores.append(f"Falta index.json en {index_path.parent}")
        return {}
    except json.JSONDecodeError as exc:
        errores.append(f"index.json no es JSON válido: línea {exc.lineno}, columna {exc.colno}")
        return {}

    if not isinstance(data, dict):
        errores.append("index.json debe contener un objeto raíz")
        return {}
    return data


def _validar_secretos(agent_runs_dir: Path, errores: list[str]) -> None:
    archivos = [agent_runs_dir / "index.json"]
    archivos.extend(agent_runs_dir.glob("*/run-ledger.md"))
    archivos.extend(agent_runs_dir.glob("*/cost-ledger.md"))
    archivos.extend(agent_runs_dir.glob("*/tool-ledger.md"))

    for archivo in archivos:
        if not archivo.exists():
            continue
        texto = archivo.read_text(encoding="utf-8")
        for nombre, patron in PATRONES_SECRET.items():
            if patron.search(texto):
                rel = archivo.relative_to(agent_runs_dir)
                errores.append(f"{rel}: posible secret detectado ({nombre})")


def _validar_run(run: Any, indice: int, agent_runs_dir: Path, errores: list[str]) -> None:
    if not isinstance(run, dict):
        errores.append(f"runs[{indice}] debe ser un objeto")
        return

    run_id = run.get("run_id", f"runs[{indice}]")
    faltantes = sorted(CAMPOS_REQUERIDOS_RUN - set(run))
    for campo in faltantes:
        errores.append(f"{run_id}: falta campo requerido {campo}")

    if run.get("riesgo") not in RIESGOS_VALIDOS:
        errores.append(f"{run_id}: riesgo inválido {run.get('riesgo')!r}")

    if run.get("estado") not in ESTADOS_VALIDOS:
        errores.append(f"{run_id}: estado inválido {run.get('estado')!r}")

    if not isinstance(run.get("pr"), int):
        errores.append(f"{run_id}: pr debe ser entero")

    for campo_lista in ("agentes", "archivos_resumen", "verificaciones", "riesgos_residuales"):
        valor = run.get(campo_lista)
        if not isinstance(valor, list) or not valor:
            errores.append(f"{run_id}: {campo_lista} debe ser una lista no vacía")

    run_id_valor = run.get("run_id")
    if isinstance(run_id_valor, str):
        carpeta = agent_runs_dir / run_id_valor
        if not carpeta.exists():
            errores.append(f"{run_id_valor}: falta carpeta")
            return
        if not carpeta.is_dir():
            errores.append(f"{run_id_valor}: la ruta de carpeta no es un directorio")
            return
        for ledger in LEDGERS_MINIMOS:
            if not (carpeta / ledger).is_file():
                errores.append(f"{run_id_valor}: falta {ledger}")


def validar_agent_runs(agent_runs_dir: Path | str = Path("docs/ops/agent-runs")) -> ResultadoValidacion:
    agent_runs_path = Path(agent_runs_dir)
    errores: list[str] = []
    data = _leer_json(agent_runs_path / "index.json", errores)

    runs = data.get("runs", []) if data else []
    if data:
        if data.get("schema_version") != 1:
            errores.append("schema_version debe ser 1")
        if not isinstance(data.get("generated_at"), str) or not data.get("generated_at"):
            errores.append("generated_at debe ser string no vacío")
        if data.get("source") != "docs/ops/agent-runs":
            errores.append("source debe ser docs/ops/agent-runs")
        if not isinstance(runs, list) or not runs:
            errores.append("runs debe ser una lista no vacía")
            runs = []

    # run_id duplicado: dos entradas con el mismo id corrompen el ledger
    # (evidencia ambigua, lookups no determinísticos). Propuesto por el
    # scout autónomo de Phase 4 (corrida 2026-06-12).
    run_ids_vistos: set[str] = set()
    for indice, run in enumerate(runs):
        if isinstance(run, dict) and isinstance(run.get("run_id"), str):
            run_id = run["run_id"]
            if run_id in run_ids_vistos:
                errores.append(f"{run_id}: run_id duplicado")
            else:
                run_ids_vistos.add(run_id)
        _validar_run(run, indice, agent_runs_path, errores)

    _validar_secretos(agent_runs_path, errores)
    return ResultadoValidacion(ok=not errores, total_runs=len(runs), errores=errores)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Valida docs/ops/agent-runs/index.json y ledgers mínimos.")
    parser.add_argument(
        "agent_runs_dir",
        nargs="?",
        default="docs/ops/agent-runs",
        help="Directorio agent-runs a validar",
    )
    args = parser.parse_args(argv)

    resultado = validar_agent_runs(Path(args.agent_runs_dir))
    if resultado.ok:
        print(f"agent-runs OK: {resultado.total_runs} runs")
        return 0

    print("agent-runs inválido:", file=sys.stderr)
    for error in resultado.errores:
        print(f"- {error}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
