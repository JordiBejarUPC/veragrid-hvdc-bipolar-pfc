"""
Small example to start VeraGridServer with PostgreSQL schema creation enabled.
"""

from __future__ import annotations

from VeraGridServer.run import start_server


def main() -> int:
    """
    Start one local VeraGridServer instance using the shared DB example settings.

    :return: Process exit code.
    """
    start_server(
        key_file_name="key.pem",
        cert_file_name="cert.pem",
        port=8000,
        domain="localhost",
        master_host="",
        master_port=0,
        username="admin",
        password="veragrid is great",
        is_master=True,
        secure=False,
        db_host="localhost",
        db_port=5432,
        db_name="veragrid",
        db_user="admin",
        db_password="pgpwd",
        db_schema="veragrid",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
