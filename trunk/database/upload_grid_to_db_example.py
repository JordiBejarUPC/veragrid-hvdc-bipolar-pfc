"""
Small example to create one model row and store a MultiCircuit in PostgreSQL.
"""

from __future__ import annotations

import VeraGridEngine as vg
from VeraGridServer.db.database import PostgreSqlConnectionSettings
from VeraGridServer.db.model_ops import create_model, put_multicircuit_in_database, create_file
from VeraGridServer.db.user_ops import create_user


def main() -> int:
    """
    Create one user, one model row, and persist one MultiCircuit into PostgreSQL.

    :return: Process exit code.
    """
    settings: PostgreSqlConnectionSettings = PostgreSqlConnectionSettings(
        host="localhost",
        port=5432,
        database="veragrid",
        user_name="admin",
        password="pgpwd",
        schema_name="veragrid",
    )

    fname = "/home/santi/Git/eRoots/VeraGrid/Grids_and_profiles/grids/2869 Pegase.gridcal"
    grid: vg.MultiCircuit = vg.open_file(filename=fname)
    user_idtag: str = "santi"
    file_idtag: str = "pegase2869"
    model_idtag: str = f"pegase2869_{user_idtag}"  # uuid4().hex
    organization_idtag: str = "admin"

    create_user(
        settings=settings,
        organization_idtag=organization_idtag,
        user_idtag=user_idtag,
        user_name="Demo user",
        password="demo_pwd",
    )

    file_idtag = create_file(
        settings=settings,
        file_name=file_idtag,
        user_idtag=user_idtag,
        file_idtag=file_idtag
    )

    model_idtag = create_model(
        settings=settings,
        model_name="2869 Pegase",
        file_idtag=file_idtag,
        parent_model_idtag=None,
        model_idtag=model_idtag,
    )

    put_multicircuit_in_database(
        settings=settings,
        circuit=grid,
        model_idtag=model_idtag,
        file_idtag=file_idtag,
    )

    print(
        f"Stored model '{model_idtag}' in database '{settings.database}' "
        f"schema '{settings.schema_name}'."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
