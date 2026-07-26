"""
Small example to create one model row and store a MultiCircuit in PostgreSQL.
"""

from __future__ import annotations

from uuid import uuid4

import VeraGridEngine as vg
from VeraGridServer.db.database import PostgreSqlConnectionSettings
from VeraGridServer.db.model_ops import create_model, put_multicircuit_in_database
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
    )

    fname = "/home/santi/Git/eRoots/VeraGrid/Grids_and_profiles/grids/2869 Pegase.gridcal"
    grid: vg.MultiCircuit = vg.open_file(filename=fname)
    user_idtag: str = "santi"
    model_idtag: str = f"pegase2869_{user_idtag}"  # uuid4().hex

    create_user(
        settings=settings,
        user_idtag=user_idtag,
        user_name="Demo user",
        password="demo_pwd",
    )

    model_idtag = create_model(
        settings=settings,
        model_name="2869 Pegase",
        user_idtag=user_idtag,
        parent_model_idtag=None,
        model_idtag=model_idtag,
    )

    put_multicircuit_in_database(
        settings=settings,
        circuit=grid,
        model_idtag=model_idtag,
    )

    print(f"Stored model '{model_idtag}' in database '{settings.database}'.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
