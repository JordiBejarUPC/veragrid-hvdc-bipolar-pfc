"""
Small example to create the VeraGrid PostgreSQL schema on localhost.
"""

from __future__ import annotations

from VeraGridServer.db.database import (
    create_veragrid_schema,
    PostgreSqlConnectionSettings,
    create_database_if_not_exists
)


def main() -> int:
    """
    Connect to localhost PostgreSQL and create the VeraGrid schema.

    :return: Process exit code.
    """


    # settings = PostgreSqlConnectionSettings(
    #     host="localhost",
    #     port=5432,
    #     database="veragrid",
    #     user_name="admin",
    #     password="pgpwd",
    #     schema_name="veragrid",
    # )

    settings: PostgreSqlConnectionSettings = PostgreSqlConnectionSettings(
        host="10.8.0.124",
        port=5432,
        database="veragrid",
        user_name="postgres",
        password="Map.160222",
        schema_name="veragrid",
    )

    create_database_if_not_exists(settings=settings)
    table_names = create_veragrid_schema(settings=settings)

    print(f"Created or reconciled schema '{settings.schema_name}' on {settings.host}:{settings.port}.")
    print(f"Detected {len(table_names)} VeraGrid object tables.")

    return 0


if __name__ == "__main__":
    main()
