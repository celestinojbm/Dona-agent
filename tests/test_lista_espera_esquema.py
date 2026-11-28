"""El esquema de lista_espera / lista_espera_limite no depende de quién lo cree.

En prod el backend no corre ``alembic upgrade head``: las tablas las crea
``create_all`` a partir de los modelos. En un entorno migrado las crean las
migraciones 010/011. Si modelo y migración divergen (defaults en la BD,
nulabilidad), la misma app ve dos esquemas distintos según el entorno.

Este test corre sin PostgreSQL (SQLite, en tests.yml): aplica ``upgrade()`` de
010 y 011 con ``alembic.operations.Operations`` sobre una BD y ``create_all``
sobre otra, y compara las columnas reflejadas. La versión contra Postgres real
está en tests/test_migraciones_lista_espera_pg.py.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations

_VERSIONES = Path(__file__).resolve().parents[1] / "alembic" / "versions"
_MIGRACIONES = ("010_lista_espera.py", "011_lista_espera_limite.py")
_TABLAS = ("lista_espera", "lista_espera_limite")


def _cargar_migracion(nombre: str):
    spec = importlib.util.spec_from_file_location(f"_mig_{nombre[:3]}", _VERSIONES / nombre)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def _modelos():
    # Import tardío: otros tests recargan agent.memory y re-registran los modelos.
    from agent.lista_espera.limites import ListaEsperaLimite
    from agent.lista_espera.models import ListaEspera

    return ListaEspera, ListaEsperaLimite


def _por_migracion(tmp_path) -> sa.Engine:
    motor = sa.create_engine(f"sqlite:///{tmp_path / 'migracion.db'}")
    with motor.begin() as conn:
        with Operations.context(MigrationContext.configure(conn)):
            for nombre in _MIGRACIONES:
                _cargar_migracion(nombre).upgrade()
    return motor


def _por_create_all(tmp_path) -> sa.Engine:
    motor = sa.create_engine(f"sqlite:///{tmp_path / 'create_all.db'}")
    for modelo in _modelos():
        modelo.__table__.create(motor)
    return motor


def _columnas(motor, tabla: str) -> dict[str, tuple]:
    return {
        c["name"]: (str(c["type"]), c["nullable"], c.get("default"))
        for c in sa.inspect(motor).get_columns(tabla)
    }


@pytest.mark.parametrize("tabla", _TABLAS)
def test_migracion_y_create_all_dejan_las_mismas_columnas(tmp_path, tabla):
    migrado = _columnas(_por_migracion(tmp_path), tabla)
    creado = _columnas(_por_create_all(tmp_path), tabla)
    assert migrado == creado, (
        f"{tabla}: modelo y migración divergen.\n  migración: {migrado}\n  create_all: {creado}"
    )


def test_defaults_en_la_bd_sin_pasar_por_el_orm(tmp_path):
    """Un INSERT crudo (consola, script de soporte) recibe los mismos defaults
    en una BD creada por create_all que en una migrada."""
    motor = _por_create_all(tmp_path)
    with motor.begin() as c:
        estado, origen = c.execute(
            sa.text(
                "INSERT INTO lista_espera (email, creado) "
                "VALUES ('a@example.com', CURRENT_TIMESTAMP) RETURNING estado, origen"
            )
        ).one()
        conteo = c.execute(
            sa.text(
                "INSERT INTO lista_espera_limite (clave, expira_en) "
                "VALUES ('alta:global:1', CURRENT_TIMESTAMP) RETURNING conteo"
            )
        ).scalar_one()
    assert (estado, origen, conteo) == ("en_espera", "web", 0)


def test_creado_es_obligatorio_en_la_migracion(tmp_path):
    """Sin ``creado`` la fila nunca caducaría: purgar_vencidos compara
    ``creado < límite`` y NULL no cumple nunca la condición."""
    motor = _por_migracion(tmp_path)
    with pytest.raises(sa.exc.IntegrityError):
        with motor.begin() as c:
            c.execute(sa.text("INSERT INTO lista_espera (email) VALUES ('b@example.com')"))
