from lnbits.db import Connection


async def delete_table_column(
    conn: Connection, table: str, table_name: str, columns_to_keep: list[str]
):
    """
    service to delete columns from a table, works on sqlite and postgres
    :param db: Database connection
    :param table: Table name
    :param table_name: Table name with schema
    :param columns_to_keep: List of columns to keep
    """
    await conn.execute(f"DROP TABLE IF EXISTS {table_name}_backup")
    await conn.execute(
        f"""
        CREATE TABLE {table_name}_backup AS
        SELECT {", ".join(columns_to_keep)} FROM {table_name}
        """
    )
    await conn.execute(f"DROP TABLE IF EXISTS {table_name}")
    # NOTE using `{table_name}` for the RENAME TO clause will not work in sqlite
    await conn.execute(f"ALTER TABLE {table_name}_backup RENAME TO {table}")
