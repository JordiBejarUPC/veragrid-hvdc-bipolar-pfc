"""
Model persistence operations for the VeraGrid PostgreSQL store.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Sequence, Tuple
from uuid import uuid4

import psycopg
from psycopg.types.json import Json

from VeraGridEngine.Devices.multi_circuit import MultiCircuit
from VeraGridEngine.IO.veragrid.pack_unpack import gather_model_as_jsons, get_objects_dictionary
from VeraGridServer.db.database import (
    ConnectionLike,
    CursorLike,
    PostgreSqlConnectionSettings,
    build_connection_kwargs,
    create_veragrid_schema,
    get_veragrid_object_table_names,
    log_database_operation,
    quote_sql_identifier,
)


def get_supported_table_mappings() -> List[Tuple[str, str]]:
    """
    Build the serializer-bucket to SQL-table mapping supported by the schema.

    The JSON serializer uses the object keys from ``get_objects_dictionary()``,
    while the schema uses the device type value as the table name. This helper
    bridges both naming systems and filters out buckets with no backing table.

    :return: Ordered list of ``(json_key, table_name)`` pairs.
    """
    object_types: Dict[str, Any] = get_objects_dictionary()
    available_table_names: set[str] = set(get_veragrid_object_table_names())
    mappings: List[Tuple[str, str]] = list()

    # The pack/unpack layer keeps one legacy branch bucket that is not stored as
    # its own table in the current schema, so we skip it explicitly.
    if "branch" in object_types:
        del object_types["branch"]
    else:
        pass

    # Only buckets backed by real schema tables can be persisted safely.
    for json_key, template_elm in object_types.items():
        table_name: str = template_elm.device_type.value

        if table_name in available_table_names:
            mappings.append((json_key, table_name))
        else:
            log_database_operation(
                f"Skipping serializer bucket '{json_key}' because table '{table_name}' is not present in the schema."
            )

    return mappings


def ensure_model_row_exists(cursor: CursorLike,
                            schema_name: str,
                            model_idtag: str) -> None:
    """
    Validate that one model row already exists before storing objects into it.

    :param cursor: Open database cursor.
    :param schema_name: Target schema name.
    :param model_idtag: Model identifier to validate.
    :return: None.
    :raises ValueError: If the model does not exist.
    """
    quoted_schema_name: str = quote_sql_identifier(schema_name)

    # The object tables are children of Models, so failing early keeps the
    # snapshot write from creating orphan rows or partial data.
    log_database_operation(
        f"Checking whether model '{model_idtag}' exists in '{schema_name}.Models'."
    )
    cursor.execute(
        f'SELECT 1 FROM {quoted_schema_name}."Models" WHERE idtag = %s',
        (model_idtag,),
    )
    row: Any = cursor.fetchone()

    if row is None:
        raise ValueError(f"Model '{model_idtag}' does not exist in schema '{schema_name}'")
    else:
        pass


def create_model(settings: PostgreSqlConnectionSettings,
                 model_name: str,
                 user_idtag: str,
                 parent_model_idtag: str | None = None,
                 model_idtag: str | None = None,
                 schema_name: str = "veragrid") -> str:
    """
    Create or update one model row and return its identifier.

    When ``model_idtag`` is not provided, the function creates one with
    ``uuid.uuid4().hex`` as requested.

    :param settings: PostgreSQL connection settings.
    :param model_name: Human-readable model name.
    :param user_idtag: Owning user identifier.
    :param parent_model_idtag: Optional parent model identifier.
    :param model_idtag: Optional pre-existing model identifier.
    :param schema_name: Target schema name.
    :return: Model identifier.
    """
    resolved_model_idtag: str
    if model_idtag is None:
        resolved_model_idtag = uuid4().hex
    else:
        resolved_model_idtag = model_idtag

    # The schema must exist before any model metadata can be upserted.
    create_veragrid_schema(settings=settings, schema_name=schema_name)
    connection_kwargs: Dict[str, Any] = build_connection_kwargs(settings=settings)
    quoted_schema_name: str = quote_sql_identifier(schema_name)

    log_database_operation(
        f"Connecting to database '{settings.database}' to create model '{resolved_model_idtag}'."
    )
    with psycopg.connect(**connection_kwargs) as connection:
        cursor: CursorLike = connection.cursor()

        # The model row carries the owning user foreign key and the visible name.
        log_database_operation(
            f"Inserting model '{resolved_model_idtag}' into '{schema_name}.Models'."
        )
        cursor.execute(
            f'''
            INSERT INTO {quoted_schema_name}."Models" (idtag, name, "user", parent_model_idtag)
            VALUES (%s, %s, %s, %s)
            ''',
            (resolved_model_idtag, model_name, user_idtag, parent_model_idtag),
        )

        log_database_operation(
            f"Committing model metadata for '{resolved_model_idtag}'."
        )
        connection.commit()
        cursor.close()

    return resolved_model_idtag


def get_model(settings: PostgreSqlConnectionSettings,
              model_idtag: str,
              schema_name: str = "veragrid") -> Dict[str, str | None] | None:
    """
    Read one model row.

    :param settings: PostgreSQL connection settings.
    :param model_idtag: Model identifier.
    :param schema_name: Target schema name.
    :return: Model row dictionary or ``None``.
    """
    connection_kwargs: Dict[str, Any] = build_connection_kwargs(settings=settings)
    quoted_schema_name: str = quote_sql_identifier(schema_name)

    log_database_operation(
        f"Connecting to database '{settings.database}' to read model '{model_idtag}'."
    )
    with psycopg.connect(**connection_kwargs) as connection:
        cursor: CursorLike = connection.cursor()
        cursor.execute(
            f'''
            SELECT idtag, name, "user", parent_model_idtag
            FROM {quoted_schema_name}."Models"
            WHERE idtag = %s
            ''',
            (model_idtag,),
        )
        row: Any = cursor.fetchone()
        cursor.close()

    if row is None:
        return None
    else:
        return {
            "idtag": str(row[0]),
            "name": str(row[1]),
            "user": str(row[2]),
            "parent_model_idtag": None if row[3] is None else str(row[3]),
        }


def update_model(settings: PostgreSqlConnectionSettings,
                 model_idtag: str,
                 model_name: str,
                 user_idtag: str,
                 parent_model_idtag: str | None = None,
                 schema_name: str = "veragrid") -> None:
    """
    Update one existing model row.

    :param settings: PostgreSQL connection settings.
    :param model_idtag: Model identifier.
    :param model_name: Human-readable model name.
    :param user_idtag: Owning user identifier.
    :param parent_model_idtag: Optional parent model identifier.
    :param schema_name: Target schema name.
    :return: None.
    """
    connection_kwargs: Dict[str, Any] = build_connection_kwargs(settings=settings)
    quoted_schema_name: str = quote_sql_identifier(schema_name)

    log_database_operation(
        f"Connecting to database '{settings.database}' to update model '{model_idtag}'."
    )
    with psycopg.connect(**connection_kwargs) as connection:
        cursor: CursorLike = connection.cursor()
        cursor.execute(
            f'''
            UPDATE {quoted_schema_name}."Models"
            SET name = %s, "user" = %s, parent_model_idtag = %s
            WHERE idtag = %s
            ''',
            (model_name, user_idtag, parent_model_idtag, model_idtag),
        )
        connection.commit()
        cursor.close()


def delete_model(settings: PostgreSqlConnectionSettings,
                 model_idtag: str,
                 cascade: bool = False,
                 schema_name: str = "veragrid") -> None:
    """
    Delete one model row, optionally removing child models first.

    :param settings: PostgreSQL connection settings.
    :param model_idtag: Model identifier.
    :param cascade: Delete child models before deleting this model.
    :param schema_name: Target schema name.
    :return: None.
    """
    connection_kwargs: Dict[str, Any] = build_connection_kwargs(settings=settings)
    quoted_schema_name: str = quote_sql_identifier(schema_name)

    log_database_operation(
        f"Connecting to database '{settings.database}' to delete model '{model_idtag}'."
    )
    with psycopg.connect(**connection_kwargs) as connection:
        cursor: CursorLike = connection.cursor()

        if cascade:
            log_database_operation(
                f"Cascade deletion enabled for model '{model_idtag}', deleting child models first."
            )
            cursor.execute(
                f'''
                DELETE FROM {quoted_schema_name}."Models"
                WHERE parent_model_idtag = %s
                ''',
                (model_idtag,),
            )
        else:
            pass

        cursor.execute(
            f'''
            DELETE FROM {quoted_schema_name}."Models"
            WHERE idtag = %s
            ''',
            (model_idtag,),
        )
        connection.commit()
        cursor.close()


def delete_existing_model_object_rows(cursor: CursorLike,
                                      schema_name: str,
                                      table_mappings: Sequence[Tuple[str, str]],
                                      model_idtag: str) -> None:
    """
    Remove the previous object snapshot for one model from all supported tables.

    :param cursor: Open database cursor.
    :param schema_name: Target schema name.
    :param table_mappings: Serializer-to-table mappings to clear.
    :param model_idtag: Model identifier whose snapshot must be replaced.
    :return: None.
    """
    quoted_schema_name: str = quote_sql_identifier(schema_name)

    # Replacing the old snapshot first prevents stale rows from surviving when
    # devices were removed from the MultiCircuit between saves.
    for json_key, table_name in table_mappings:
        quoted_table_name: str = quote_sql_identifier(table_name)

        log_database_operation(
            f"Deleting previous rows for model '{model_idtag}' from '{schema_name}.{table_name}' (bucket '{json_key}')."
        )
        cursor.execute(
            f"DELETE FROM {quoted_schema_name}.{quoted_table_name} WHERE model_idtag = %s",
            (model_idtag,),
        )


def insert_model_object_rows(cursor: CursorLike,
                             schema_name: str,
                             table_mappings: Sequence[Tuple[str, str]],
                             model_data: Dict[str, Any],
                             model_idtag: str) -> None:
    """
    Insert one full MultiCircuit object snapshot into the typed object tables.

    :param cursor: Open database cursor.
    :param schema_name: Target schema name.
    :param table_mappings: Serializer-to-table mappings to fill.
    :param model_data: Packed model JSON dictionary from VeraGrid.
    :param model_idtag: Parent model identifier.
    :return: None.
    """
    quoted_schema_name: str = quote_sql_identifier(schema_name)

    # Each bucket contains the homogeneous JSON objects already serialized by
    # the VeraGrid engine, so the database layer only has to route them to the
    # matching typed tables without reshaping the payload.
    for json_key, table_name in table_mappings:
        quoted_table_name: str = quote_sql_identifier(table_name)
        entries: Any = model_data.get(json_key, list())

        if isinstance(entries, list):
            row_count: int = len(entries)
        else:
            row_count = 0

        log_database_operation(
            f"Inserting {row_count} rows into '{schema_name}.{table_name}' from serializer bucket '{json_key}'."
        )

        if isinstance(entries, list):
            for entry in entries:
                object_idtag: str = str(entry["idtag"])

                cursor.execute(
                    f"""
                    INSERT INTO {quoted_schema_name}.{quoted_table_name} (idtag, data, model_idtag)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (idtag)
                    DO UPDATE SET
                        data = EXCLUDED.data,
                        model_idtag = EXCLUDED.model_idtag
                    """,
                    (object_idtag, Json(entry), model_idtag),
                )
        else:
            pass


def put_multicircuit_in_database(settings: PostgreSqlConnectionSettings,
                                 circuit: MultiCircuit,
                                 model_idtag: str,
                                 schema_name: str = "veragrid",
                                 project_directory: Path | None = None) -> None:
    """
    Persist one ``MultiCircuit`` snapshot into the typed VeraGrid SQL tables.

    The function expects that the model row was created beforehand. It then
    clears the previous object snapshot for that model and writes the current
    JSON representation produced by the VeraGrid serializer.

    :param settings: PostgreSQL connection settings.
    :param circuit: VeraGrid circuit to persist.
    :param model_idtag: Existing parent model identifier.
    :param schema_name: Target schema name.
    :param project_directory: Optional project directory for the serializer.
    :return: None.
    """
    create_veragrid_schema(settings=settings, schema_name=schema_name)
    connection_kwargs: Dict[str, Any] = build_connection_kwargs(settings=settings)
    packed_model: Dict[str, Any] = gather_model_as_jsons(
        circuit=circuit,
        project_directory=project_directory,
    )
    model_data: Dict[str, Any] = packed_model["model_data"]
    table_mappings: List[Tuple[str, str]] = get_supported_table_mappings()

    log_database_operation(
        f"Connecting to database '{settings.database}' to persist MultiCircuit into model '{model_idtag}'."
    )
    with psycopg.connect(**connection_kwargs) as connection:
        cursor: CursorLike = connection.cursor()

        ensure_model_row_exists(
            cursor=cursor,
            schema_name=schema_name,
            model_idtag=model_idtag,
        )

        delete_existing_model_object_rows(
            cursor=cursor,
            schema_name=schema_name,
            table_mappings=table_mappings,
            model_idtag=model_idtag,
        )

        insert_model_object_rows(
            cursor=cursor,
            schema_name=schema_name,
            table_mappings=table_mappings,
            model_data=model_data,
            model_idtag=model_idtag,
        )

        log_database_operation(
            f"Committing MultiCircuit snapshot for model '{model_idtag}'."
        )
        connection.commit()
        cursor.close()
