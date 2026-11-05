import sqlite3

conn = sqlite3.connect("data/regulatory.db")
cursor = conn.cursor()

tables = ["documents", "document_versions"]

for table in tables:
    print(f"\n{'=' * 50}")
    print(f"TABLE: {table}")
    print("=" * 50)

    cursor.execute(
        "SELECT sql FROM sqlite_master WHERE type = ? AND name = ?",
        ("table", table)
    )

    result = cursor.fetchone()

    if result:
        print(result[0])
    else:
        print("Table not found.")

conn.close()