"""
Database schema helpers for VeraGridServer.
"""

from __future__ import annotations
import psycopg
from typing import Any, Dict, List, Protocol, Sequence
from VeraGridEngine.Devices.multi_circuit import MultiCircuit


class PostgreSqlConnectionSettings:
    """
    Small container for PostgreSQL connection settings.
    """

    __slots__ = ("host", "port", "database", "user_name", "password")

    def __init__(self,
                 host: str,
                 port: int,
                 database: str,
                 user_name: str,
                 password: str) -> None:
        """
        Build one PostgreSQL connection settings object.

        :param host: PostgreSQL host name.
        :param port: PostgreSQL port number.
        :param database: Database name.
        :param user_name: Login user name.
        :param password: Login password.
        :return: None.
        """
        self.host: str = host
        self.port: int = port
        self.database: str = database
        self.user_name: str = user_name
        self.password: str = password


def build_connection_kwargs(settings: PostgreSqlConnectionSettings) -> Dict[str, Any]:
    """
    Convert the settings object into ``psycopg.connect`` keyword arguments.

    :param settings: Localhost PostgreSQL settings.
    :return: Keyword arguments for ``psycopg.connect``.
    """
    connection_kwargs: Dict[str, Any] = dict()

    # This helper preserves the original call surface for existing code paths
    # while the explicit example below shows the exact connection values inline.
    connection_kwargs["host"] = settings.host
    connection_kwargs["port"] = settings.port
    connection_kwargs["dbname"] = settings.database
    connection_kwargs["user"] = settings.user_name
    connection_kwargs["password"] = settings.password

    return connection_kwargs


class CursorLike(Protocol):
    """
    Minimal DB-API cursor protocol used by the schema helpers.
    """

    def execute(self, operation: str, parameters: Sequence[Any] | None = None) -> Any:
        """
        Execute one SQL operation.

        :param operation: SQL statement to execute.
        :param parameters: Optional positional parameters.
        :return: Driver-defined execution result.
        """
        ...

    def close(self) -> None:
        """
        Close the cursor.

        :return: None.
        """
        ...


class ConnectionLike(Protocol):
    """
    Minimal DB-API connection protocol used by the schema helpers.
    """

    def cursor(self) -> CursorLike:
        """
        Create one cursor.

        :return: Database cursor.
        """
        ...

    def commit(self) -> None:
        """
        Commit the active transaction.

        :return: None.
        """
        ...


def quote_sql_identifier(identifier: str) -> str:
    """
    Quote one SQL identifier for PostgreSQL.

    :param identifier: Raw identifier.
    :return: Double-quoted identifier.
    :raises ValueError: If the identifier is empty.
    """
    if len(identifier) == 0:
        raise ValueError("The SQL identifier cannot be empty")
    else:
        pass

    return '"' + identifier.replace('"', '""') + '"'


def get_veragrid_object_table_names() -> List[str]:
    """
    Inspect ``MultiCircuit`` and return the available VeraGrid object table names.

    The function uses the template device instances declared by ``MultiCircuit``
    so the schema follows the same object catalogue exposed by the engine.

    :return: Ordered list of distinct table names.
    """
    circuit: MultiCircuit = MultiCircuit()
    discovered_names: Dict[str, None] = dict()
    ordered_names: List[str] = list()

    # The template items are the authoritative list of object kinds supported by
    # the current MultiCircuit implementation, so we derive the database tables
    # from that list instead of maintaining a second manual registry.
    for template_item in circuit.template_items():
        table_name: str = template_item.device_type.value

        # Some names can be grouped or repeated through aliases in the engine;
        # the dictionary preserves uniqueness while the list preserves order.
        if table_name not in discovered_names:
            discovered_names[table_name] = None
            ordered_names.append(table_name)
        else:
            pass

    return ordered_names


def create_veragrid_schema(settings: PostgreSqlConnectionSettings,
                           schema_name: str = "veragrid") -> List[str]:
    """
    Create the PostgreSQL schema used to persist VeraGrid models and objects.

    The created structure is:

    - ``Users`` with ``(idtag, name)``
    - ``Models`` with ``(idtag, name, user)``, linked to ``Users``
    - One table per VeraGrid object type with ``(idtag, data, model_idtag)``,
      linked to ``Models``

    :param settings: Open DB-API compatible PostgreSQL connection.
    :param schema_name: Target PostgreSQL schema name.
    :return: Ordered list of created VeraGrid object table names.
    """
    connection_kwargs: dict[str, Any] = build_connection_kwargs(settings=settings)

    # The context manager keeps the example small and ensures the connection is
    # closed even when PostgreSQL rejects the credentials or the network fails.
    with psycopg.connect(**connection_kwargs) as connection:


        cursor: CursorLike = connection.cursor()
        object_table_names: List[str] = get_veragrid_object_table_names()
        quoted_schema_name: str = quote_sql_identifier(schema_name)

        # The schema boundary isolates the VeraGrid persistence objects from any
        # other application tables and keeps the DDL idempotent across deployments.
        cursor.execute(f"CREATE SCHEMA IF NOT EXISTS {quoted_schema_name}")

        # Users are the root owner records, so the Models table can safely point to
        # them through a foreign key in the next step.
        cursor.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {quoted_schema_name}."Users" (
                idtag TEXT PRIMARY KEY,
                name TEXT NOT NULL
            )
            """
        )

        # Models hold the logical grid/container metadata. The "user" column name is
        # kept exactly as requested, and quoted because PostgreSQL treats USER as a
        # special keyword.
        cursor.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {quoted_schema_name}."Models" (
                idtag TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                "user" TEXT NOT NULL,
                CONSTRAINT models_user_fk
                    FOREIGN KEY ("user")
                    REFERENCES {quoted_schema_name}."Users"(idtag)
                    ON DELETE RESTRICT
            )
            """
        )

        # Each VeraGrid object type gets its own payload table. The payload is kept
        # as JSON so the object structure can evolve without forcing a table redesign
        # for every engine-side property change.
        for table_name in object_table_names:
            quoted_table_name: str = quote_sql_identifier(table_name)
            constraint_name: str = f"{table_name}_model_fk".lower().replace(" ", "_")

            cursor.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {quoted_schema_name}.{quoted_table_name} (
                    idtag TEXT PRIMARY KEY,
                    data JSON NOT NULL,
                    model_idtag TEXT NOT NULL,
                    CONSTRAINT {quote_sql_identifier(constraint_name)}
                        FOREIGN KEY (model_idtag)
                        REFERENCES {quoted_schema_name}."Models"(idtag)
                        ON DELETE CASCADE
                )
                """
            )

        connection.commit()
        cursor.close()

    return object_table_names



