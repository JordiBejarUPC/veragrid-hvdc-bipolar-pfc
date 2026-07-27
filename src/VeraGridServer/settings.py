# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from VeraGridServer.db.database import PostgreSqlConnectionSettings

class ExtraSettings:
    def __init__(self):
        self.am_i_master: bool = True
        self.master_host: str = ""
        self.master_port = 0
        self.this_host: str = ""
        self.this_port = 0
        self.this_username = ""
        self.this_password = ""
        self.db_host: str = ""
        self.db_port: int = 0
        self.db_name: str = ""
        self.db_user: str = ""
        self.db_password: str = ""
        self.db_schema: str = "veragrid"

    def has_database_configuration(self) -> bool:
        """
        Check whether the database configuration is complete.

        :return: ``True`` when every database setting is present, ``False`` otherwise.
        """
        if (
            len(self.db_host) > 0
            and self.db_port > 0
            and len(self.db_name) > 0
            and len(self.db_user) > 0
            and len(self.db_password) > 0
        ):
            return True
        else:
            return False

    def get_database_settings(self) -> PostgreSqlConnectionSettings | None:
        """
        Build one PostgreSQL settings object when the configuration is complete.

        :return: PostgreSQL connection settings or ``None``.
        """
        if self.has_database_configuration():
            return PostgreSqlConnectionSettings(
                host=self.db_host,
                port=self.db_port,
                database=self.db_name,
                user_name=self.db_user,
                password=self.db_password,
                schema_name=self.db_schema,
            )
        else:
            return None


settings = ExtraSettings()
