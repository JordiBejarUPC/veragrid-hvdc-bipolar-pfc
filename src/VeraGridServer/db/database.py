"""
Database schema helpers for VeraGridServer.
"""

from __future__ import annotations
import logging
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

    def fetchone(self) -> Any:
        """
        Fetch one row from the previous query.

        :return: Driver-defined row object.
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


def log_database_operation(message: str) -> None:
    """
    Emit one database operation log line to the standard logging system.

    :param message: Operation description to log.
    :return: None.
    """
    logger: logging.Logger = logging.getLogger("VeraGridServer.db")

    # The handler is attached only once so repeated database calls do not emit
    # duplicated lines while still writing to the normal process stderr stream.
    if len(logger.handlers) == 0:
        handler: logging.StreamHandler = logging.StreamHandler()
        formatter: logging.Formatter = logging.Formatter(
            fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    else:
        pass

    logger.setLevel(logging.INFO)
    logger.propagate = False
    logger.info(message)


def create_database_if_not_exists(settings: PostgreSqlConnectionSettings,
                                  maintenance_database: str = "postgres") -> bool:
    """
    Create the target PostgreSQL database when it does not exist yet.

    PostgreSQL requires connecting to an existing maintenance database before
    issuing ``CREATE DATABASE``, so this helper uses the provided server and
    credentials but temporarily switches the database name for the check.

    :param settings: Target PostgreSQL connection settings.
    :param maintenance_database: Existing database used to manage databases.
    :return: ``True`` when the database was created, ``False`` otherwise.
    """
    maintenance_settings: PostgreSqlConnectionSettings = PostgreSqlConnectionSettings(
        host=settings.host,
        port=settings.port,
        database=maintenance_database,
        user_name=settings.user_name,
        password=settings.password,
    )
    connection_kwargs: Dict[str, Any] = build_connection_kwargs(settings=maintenance_settings)
    created: bool = False

    # The first connection goes to a maintenance database because PostgreSQL can
    # only create databases from an already existing database context.
    log_database_operation(
        f"Connecting to maintenance database '{maintenance_database}' on "
        f"{settings.host}:{settings.port} to verify database '{settings.database}'."
    )

    # PostgreSQL does not allow CREATE DATABASE inside a transaction, so this
    # management connection must run in autocommit mode.
    with psycopg.connect(autocommit=True, **connection_kwargs) as connection:
        cursor: CursorLike = connection.cursor()

        # The catalog lookup avoids a failing CREATE DATABASE call and keeps the
        # utility re-runnable on machines where the database is already present.
        log_database_operation(
            f"Checking whether database '{settings.database}' already exists."
        )
        cursor.execute(
            "SELECT 1 FROM pg_database WHERE datname = %s",
            (settings.database,),
        )
        row: Any = cursor.fetchone()

        if row is None:
            quoted_database_name: str = quote_sql_identifier(settings.database)
            log_database_operation(
                f"Creating PostgreSQL database '{settings.database}'."
            )
            cursor.execute(f"CREATE DATABASE {quoted_database_name}")
            created = True
        else:
            log_database_operation(
                f"Database '{settings.database}' already exists, skipping creation."
            )
            created = False

        log_database_operation(
            f"Closing maintenance cursor for database '{maintenance_database}'."
        )
        cursor.close()

    return created


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
    created_database: bool = create_database_if_not_exists(settings=settings)
    connection_kwargs: Dict[str, Any] = build_connection_kwargs(settings=settings)

    if created_database:
        log_database_operation(
            f"Database '{settings.database}' was created and is ready for schema setup."
        )
    else:
        log_database_operation(
            f"Database '{settings.database}' already existed, continuing with schema setup."
        )

    # The second connection targets the real application database where the
    # schema and tables must be reconciled.
    log_database_operation(
        f"Connecting to application database '{settings.database}' on "
        f"{settings.host}:{settings.port}."
    )

    # The context manager keeps the example small and ensures the connection is
    # closed even when PostgreSQL rejects the credentials or the network fails.
    with psycopg.connect(**connection_kwargs) as connection:
        cursor: CursorLike = connection.cursor()
        object_table_names: List[str] = get_veragrid_object_table_names()
        quoted_schema_name: str = quote_sql_identifier(schema_name)

        # The schema boundary isolates the VeraGrid persistence objects from any
        # other application tables and keeps the DDL idempotent across deployments.
        log_database_operation(
            f"Creating schema '{schema_name}' if it does not exist."
        )
        cursor.execute(f"CREATE SCHEMA IF NOT EXISTS {quoted_schema_name}")

        # Users are the root owner records, so the Models table can safely point to
        # them through a foreign key in the next step.
        log_database_operation(
            f"Creating table '{schema_name}.Users' if it does not exist."
        )
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
        log_database_operation(
            f"Creating table '{schema_name}.Models' if it does not exist."
        )
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

            log_database_operation(
                f"Creating table '{schema_name}.{table_name}' if it does not exist."
            )
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

        log_database_operation(
            f"Committing schema changes for database '{settings.database}'."
        )
        connection.commit()
        log_database_operation(
            f"Closing schema cursor for database '{settings.database}'."
        )
        cursor.close()

    return object_table_names

