from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import psycopg
import pytest

import VeraGridEngine.api as vge
from VeraGridServer.db.database import PostgreSqlConnectionSettings
from VeraGridServer.db.model_ops import (
    create_model,
    delete_model,
    get_multicircuit_from_database,
    put_multicircuit_in_database,
)
from VeraGridServer.db.user_ops import create_user, delete_user


GRID_FOLDER = Path(__file__).resolve().parents[1] / "data" / "grids"


def _assert_circuits_equal(grid1: vge.MultiCircuit, grid2: vge.MultiCircuit) -> None:
    """
    Assert semantic circuit equality and print the engine logger on mismatch.

    :param grid1: First circuit.
    :param grid2: Second circuit.
    :return: None.
    """
    equal, logger = grid1.compare_circuits(
        grid2,
        detailed_profile_comparison=True,
        skip_internals=True,
    )

    if not equal:
        logger.print()
    else:
        pass

    assert equal


def _get_local_db_settings() -> PostgreSqlConnectionSettings:
    """
    Return the localhost PostgreSQL settings used by the DB examples.

    :return: PostgreSQL connection settings.
    """
    return PostgreSqlConnectionSettings(
        host="localhost",
        port=5432,
        database="veragrid",
        user_name="admin",
        password="pgpwd",
    )


def _skip_when_local_db_is_unavailable(settings: PostgreSqlConnectionSettings) -> None:
    """
    Skip the test when the expected localhost PostgreSQL instance is unreachable.

    :param settings: PostgreSQL connection settings.
    :return: None.
    """
    try:
        with psycopg.connect(
            host=settings.host,
            port=settings.port,
            dbname="postgres",
            user=settings.user_name,
            password=settings.password,
            connect_timeout=2,
        ) as connection:
            _unused_connection = connection
    except psycopg.Error as exc:
        pytest.skip(f"Local PostgreSQL is not accessible: {exc}")


def test_multicircuit_db_roundtrip_when_local_db_is_available() -> None:
    """
    Roundtrip one shipped grid through the local PostgreSQL store when available.

    :return: None.
    """
    settings: PostgreSqlConnectionSettings = _get_local_db_settings()
    _skip_when_local_db_is_unavailable(settings=settings)

    source_grid: vge.MultiCircuit = vge.open_file(str(GRID_FOLDER / "case14.gridcal"))
    user_idtag: str = f"db_test_user_{uuid4().hex}"
    model_idtag: str = f"db_test_model_{uuid4().hex}"

    try:
        create_user(
            settings=settings,
            user_idtag=user_idtag,
            user_name="DB Test User",
            password="db_test_pwd",
        )
        create_model(
            settings=settings,
            model_name="case14_db_roundtrip",
            user_idtag=user_idtag,
            parent_model_idtag=None,
            model_idtag=model_idtag,
        )
        put_multicircuit_in_database(
            settings=settings,
            circuit=source_grid,
            model_idtag=model_idtag,
        )

        loaded_grid: vge.MultiCircuit = get_multicircuit_from_database(
            settings=settings,
            model_idtag=model_idtag,
        )

        _assert_circuits_equal(source_grid, loaded_grid)
    finally:
        delete_model(settings=settings, model_idtag=model_idtag, cascade=False)
        delete_user(settings=settings, user_idtag=user_idtag, cascade=False)
