import os
import sqlite3

from .helpers import ExtensionManager
from .settings import LNBITS_PATH, LNBITS_DATA_FOLDER


class Database:
    def __init__(self, db_path: str):
        self.path = db_path
        self.connection = sqlite3.connect(db_path)
        self.connection.row_factory = sqlite3.Row
        self.cursor = self.connection.cursor()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.cursor.close()
        self.connection.close()

    def fetchall(self, query: str, values: tuple) -> list:
        """Given a query, return cursor.fetchall() rows."""
        self.cursor.execute(query, values)
        return self.cursor.fetchall()

    def fetchone(self, query: str, values: tuple):
        self.cursor.execute(query, values)
        return self.cursor.fetchone()

    def execute(self, query: str, values: tuple) -> None:
        """Given a query, cursor.execute() it."""
        self.cursor.execute(query, values)
        self.connection.commit()


def open_db(db_name: str = "database") -> Database:
    db_path = os.path.join(LNBITS_DATA_FOLDER, f"{db_name}.sqlite3")
    return Database(db_path=db_path)


def open_ext_db(extension_name: str) -> Database:
    return open_db(f"ext_{extension_name}")


def init_databases() -> None:
    """Creates the necessary databases if they don't exist already."""
    """TODO: see how we can deal with migrations."""

    schemas = [
        ("database", os.path.join(LNBITS_PATH, "data", "schema.sql")),
    ]

    for extension in ExtensionManager().extensions:
        schemas.append((f"ext_{extension.code}", os.path.join(extension.path, "schema.sql")))

    for schema in [s for s in schemas if os.path.exists(s[1])]:
        with open_db(schema[0]) as db:
            with open(schema[1]) as schemafile:
                for stmt in schemafile.read().split(";\n\n"):
                    db.execute(stmt, [])
