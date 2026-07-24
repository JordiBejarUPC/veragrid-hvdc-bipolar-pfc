"""
User CRUD operations for the VeraGrid PostgreSQL store.
"""

from __future__ import annotations

from typing import Any, Dict

import psycopg

from VeraGridServer.db.database import (
    CursorLike,
    PostgreSqlConnectionSettings,
    build_connection_kwargs,
    create_veragrid_schema,
    log_database_operation,
    quote_sql_identifier,
)


def create_user(settings: PostgreSqlConnectionSettings,
                user_idtag: str,
                user_name: str,
                password: str,
                schema_name: str = "veragrid") -> None:
    """
    Create one user row.

    :param settings: PostgreSQL connection settings.
    :param user_idtag: User identifier.
    :param user_name: User display name.
    :param password: User password.
    :param schema_name: Target schema name.
    :return: None.
    """
    create_veragrid_schema(settings=settings, schema_name=schema_name)
    connection_kwargs: Dict[str, Any] = build_connection_kwargs(settings=settings)
    quoted_schema_name: str = quote_sql_identifier(schema_name)

    log_database_operation(
        f"Connecting to database '{settings.database}' to create user '{user_idtag}'."
    )
    with psycopg.connect(**connection_kwargs) as connection:
        cursor: CursorLike = connection.cursor()
        cursor.execute(
            f'''
            INSERT INTO {quoted_schema_name}."Users" (idtag, name, password)
            VALUES (%s, %s, %s)
            ''',
            (user_idtag, user_name, password),
        )
        connection.commit()
        cursor.close()


def get_user(settings: PostgreSqlConnectionSettings,
             user_idtag: str,
             schema_name: str = "veragrid") -> Dict[str, str] | None:
    """
    Read one user row.

    :param settings: PostgreSQL connection settings.
    :param user_idtag: User identifier.
    :param schema_name: Target schema name.
    :return: User row dictionary or ``None``.
    """
    connection_kwargs: Dict[str, Any] = build_connection_kwargs(settings=settings)
    quoted_schema_name: str = quote_sql_identifier(schema_name)

    log_database_operation(
        f"Connecting to database '{settings.database}' to read user '{user_idtag}'."
    )
    with psycopg.connect(**connection_kwargs) as connection:
        cursor: CursorLike = connection.cursor()
        cursor.execute(
            f'''
            SELECT idtag, name, password
            FROM {quoted_schema_name}."Users"
            WHERE idtag = %s
            ''',
            (user_idtag,),
        )
        row: Any = cursor.fetchone()
        cursor.close()

    if row is None:
        return None
    else:
        return {
            "idtag": str(row[0]),
            "name": str(row[1]),
            "password": str(row[2]),
        }


def update_user(settings: PostgreSqlConnectionSettings,
                user_idtag: str,
                user_name: str,
                password: str,
                schema_name: str = "veragrid") -> None:
    """
    Update one existing user row.

    :param settings: PostgreSQL connection settings.
    :param user_idtag: User identifier.
    :param user_name: User display name.
    :param password: User password.
    :param schema_name: Target schema name.
    :return: None.
    """
    connection_kwargs: Dict[str, Any] = build_connection_kwargs(settings=settings)
    quoted_schema_name: str = quote_sql_identifier(schema_name)

    log_database_operation(
        f"Connecting to database '{settings.database}' to update user '{user_idtag}'."
    )
    with psycopg.connect(**connection_kwargs) as connection:
        cursor: CursorLike = connection.cursor()
        cursor.execute(
            f'''
            UPDATE {quoted_schema_name}."Users"
            SET name = %s, password = %s
            WHERE idtag = %s
            ''',
            (user_name, password, user_idtag),
        )
        connection.commit()
        cursor.close()


def delete_user(settings: PostgreSqlConnectionSettings,
                user_idtag: str,
                cascade: bool = False,
                schema_name: str = "veragrid") -> None:
    """
    Delete one user row, optionally removing its models first.

    :param settings: PostgreSQL connection settings.
    :param user_idtag: User identifier.
    :param cascade: Delete the user's models before deleting the user.
    :param schema_name: Target schema name.
    :return: None.
    """
    connection_kwargs: Dict[str, Any] = build_connection_kwargs(settings=settings)
    quoted_schema_name: str = quote_sql_identifier(schema_name)

    log_database_operation(
        f"Connecting to database '{settings.database}' to delete user '{user_idtag}'."
    )
    with psycopg.connect(**connection_kwargs) as connection:
        cursor: CursorLike = connection.cursor()

        if cascade:
            log_database_operation(
                f"Cascade deletion enabled for user '{user_idtag}', deleting dependent models first."
            )
            cursor.execute(
                f'''
                DELETE FROM {quoted_schema_name}."Models"
                WHERE "user" = %s
                ''',
                (user_idtag,),
            )
        else:
            pass

        cursor.execute(
            f'''
            DELETE FROM {quoted_schema_name}."Users"
            WHERE idtag = %s
            ''',
            (user_idtag,),
        )
        connection.commit()
        cursor.close()
