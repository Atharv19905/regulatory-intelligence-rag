
import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "data" / "regulatory.db"

# Open SQLite strictly in read-only mode.
connection = sqlite3.connect(
    f"{DB_PATH.as_uri()}?mode=ro",
    uri=True
)
connection.row_factory = sqlite3.Row

try:
    print("\n========== DATABASE TABLES ==========\n")

    tables = connection.execute("""
        SELECT name
        FROM sqlite_master
        WHERE type = 'table'
        ORDER BY name
    """).fetchall()

    for table in tables:
        print(f"\n--- TABLE: {table['name']} ---")

        columns = connection.execute(
            f'PRAGMA table_info("{table["name"]}")'
        ).fetchall()

        for column in columns:
            print(
                f"{column['name']} | "
                f"type={column['type']} | "
                f"not_null={column['notnull']} | "
                f"primary_key={column['pk']}"
            )

    print("\n========== DOCUMENT VERSIONS ==========\n")

    versions = connection.execute("""
        SELECT
            d.document_id,
            d.title,
            d.regulator,
            v.version_id,
            v.version_number,
            v.publication_date,
            v.effective_date,
            v.retrieved_at,
            v.file_path
        FROM documents AS d
        JOIN document_versions AS v
            ON d.document_id = v.document_id
        ORDER BY d.document_id, v.version_number
    """).fetchall()

    for row in versions:
        print(dict(row))

    print("\n========== REGULATORY CHANGE EVENTS ==========\n")

    try:
        changes = connection.execute("""
            SELECT *
            FROM regulatory_changes
            ORDER BY change_id
        """).fetchall()

        print(f"Total change events: {len(changes)}")

        for row in changes:
            print(dict(row))

    except sqlite3.OperationalError as error:
        print(f"Could not read regulatory_changes: {error}")

finally:
    connection.close()

print("\nRead-only inspection completed.")
