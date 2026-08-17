"""
Small example to retrieve one model from PostgreSQL and save it to disk.
"""

from __future__ import annotations

from pathlib import Path

import VeraGridEngine as vg
from VeraGridServer.db.database import PostgreSqlConnectionSettings
from VeraGridServer.db.model_ops import get_multicircuit_from_database


def main() -> int:
    """
    Retrieve one model from PostgreSQL and save the rebuilt MultiCircuit.

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

    model_idtag: str = "pegase2869_santi"
    output_file = f"{model_idtag}.gridcal"

    grid: vg.MultiCircuit = get_multicircuit_from_database(
        settings=settings,
        model_idtag=model_idtag,
        file_idtag="pegase2869",
    )

    vg.save_file(grid=grid, filename=output_file)

    print(
        f"Retrieved model '{model_idtag}' from database '{settings.database}' "
        f"schema '{settings.schema_name}'."
    )
    print(f"Saved rebuilt grid to '{output_file}'.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
