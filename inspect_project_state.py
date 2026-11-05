
import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "data" / "regulatory.db"


def main():
    if not DB_PATH.is_file():
        print(f"Database not found: {DB_PATH}")
        return

    connection = sqlite3.connect(
        f"file:{DB_PATH.as_posix()}?mode=ro",
        uri=True
    )

    try:
        connection.row_factory = sqlite3.Row

        print("=" * 55)
        print("READ-ONLY SQLITE INSPECTION")
        print("=" * 55)

        integrity = connection.execute(
            "PRAGMA integrity_check"
        ).fetchone()[0]
        print(f"\nDatabase integrity: {integrity}")

        document_count = connection.execute(
            "SELECT COUNT(*) FROM documents"
        ).fetchone()[0]

        version_count = connection.execute(
            "SELECT COUNT(*) FROM document_versions"
        ).fetchone()[0]

        print(f"Registered documents: {document_count}")
        print(f"Registered versions: {version_count}")

        print("\nDocuments by regulator:")
        rows = connection.execute(
            """
            SELECT regulator, COUNT(*) AS total
            FROM documents
            GROUP BY regulator
            ORDER BY regulator
            """
        ).fetchall()

        for row in rows:
            print(f"- {row['regulator']}: {row['total']}")

        print("\nVersion date coverage:")
        row = connection.execute(
            """
            SELECT
                COUNT(*) AS total,
                SUM(CASE WHEN publication_date IS NOT NULL
                    THEN 1 ELSE 0 END) AS publication_dates,
                SUM(CASE WHEN effective_date IS NOT NULL
                    THEN 1 ELSE 0 END) AS effective_dates
            FROM document_versions
            """
        ).fetchone()

        print(f"Total versions: {row['total']}")
        print(f"With publication date: {row['publication_dates']}")
        print(f"With effective date: {row['effective_dates']}")

        print("\nLatest registered versions:")
        rows = connection.execute(
            """
            SELECT
                d.document_id,
                d.title,
                d.regulator,
                v.version_id,
                v.version_number,
                v.publication_date,
                v.effective_date
            FROM documents d
            JOIN document_versions v
                ON d.document_id = v.document_id
            ORDER BY v.retrieved_at DESC
            LIMIT 10
            """
        ).fetchall()

        for row in rows:
            print("-" * 55)
            print(f"Document ID: {row['document_id']}")
            print(f"Title: {row['title']}")
            print(f"Regulator: {row['regulator']}")
            print(f"Version ID: {row['version_id']}")
            print(f"Version number: {row['version_number']}")
            print(f"Publication date: {row['publication_date']}")
            print(f"Effective date: {row['effective_date']}")

        print("\nInspection completed. No database changes made.")

    finally:
        connection.close()


if __name__ == "__main__":
    main()
