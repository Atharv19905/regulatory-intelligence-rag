
import sqlite3

DB_PATH = "data/regulatory.db"

with sqlite3.connect(DB_PATH) as connection:
    connection.row_factory = sqlite3.Row

    rows = connection.execute("""
        SELECT
            d.document_id,
            d.title,
            d.regulator,
            v.version_number,
            v.file_path,
            v.publication_date,
            v.effective_date,
            v.sha256
        FROM documents AS d
        JOIN document_versions AS v
            ON d.document_id = v.document_id
        WHERE d.title LIKE '%Section 51A%'
        ORDER BY v.version_number
    """).fetchall()

    if not rows:
        print("No matching circular found.")
    else:
        for row in rows:
            for key in row.keys():
                print(f"{key}: {row[key]}")
            print("-" * 50)
