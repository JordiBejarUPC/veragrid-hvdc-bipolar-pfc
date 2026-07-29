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
        host="10.8.0.124",
        port=5432,
        database="veragrid",
        user_name="postgres",
        password="Map.160222",
        schema_name="veragrid",
    )

    fname = "/home/santi/Git/eRoots/M-project/Model/daily_freezes/20260727/merge_20260727.veragrid"
    grid: vg.MultiCircuit = vg.open_file(filename=fname)
    user_idtag: str = "admin"
    file_idtag: str = "merge_20260727"
    model_idtag: str = f"merge_20260727_{user_idtag}"  # uuid4().hex
    model_name = "merge_20260727"
    # organization_idtag: str = "admin"


    file_idtag = create_file(
        settings=settings,
        file_name=file_idtag,
        user_idtag=user_idtag,
        file_idtag=file_idtag
    )

    model_idtag = create_model(
        settings=settings,
        model_name=model_name,
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
