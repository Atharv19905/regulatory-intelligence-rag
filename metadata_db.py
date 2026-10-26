
import sqlite3
from pathlib import Path
import hashlib

DB_PATH = Path("data/regulatory.db")
DB_PATH.parent.mkdir(parents=True, exist_ok=True)


def get_connection():
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def initialize_database():
    with get_connection() as connection:
        connection.executescript("""
            CREATE TABLE IF NOT EXISTS documents (
                document_id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_url TEXT NOT NULL UNIQUE,
                title TEXT,
                regulator TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS document_versions (
                version_id INTEGER PRIMARY KEY AUTOINCREMENT,
                document_id INTEGER NOT NULL,
                version_number INTEGER NOT NULL,
                file_path TEXT NOT NULL,
                sha256 TEXT NOT NULL,
                publication_date TEXT,
                effective_date TEXT,
                retrieved_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

                UNIQUE(document_id, version_number),
                UNIQUE(document_id, sha256),

                FOREIGN KEY(document_id)
                    REFERENCES documents(document_id)
            );
        """)

    print("Database initialized successfully.")


def calculate_sha256(file_path):
    sha256_hash = hashlib.sha256()

    with open(file_path, "rb") as file:
        for block in iter(lambda: file.read(4096), b""):
            sha256_hash.update(block)

    return sha256_hash.hexdigest()


def register_document(
    source_url,
    title,
    regulator,
    file_path,
    publication_date=None,
    effective_date=None
):
    file_path = Path(file_path)

    if not file_path.is_file():
        print(f"File not found: {file_path}")
        return

    file_hash = calculate_sha256(file_path)

    with get_connection() as connection:
        # Find or create the logical document.
        document = connection.execute(
            "SELECT document_id FROM documents WHERE source_url = ?",
            (source_url,)
        ).fetchone()

        if document is None:
            cursor = connection.execute(
                """
                INSERT INTO documents (source_url, title, regulator)
                VALUES (?, ?, ?)
                """,
                (source_url, title, regulator)
            )
            document_id = cursor.lastrowid
        else:
            document_id = document["document_id"]

            connection.execute(
                """
                UPDATE documents
                SET title = ?, regulator = ?
                WHERE document_id = ?
                """,
                (title, regulator, document_id)
            )

        # Skip the file if this exact content is already registered.
        existing_version = connection.execute(
            """
            SELECT version_number
            FROM document_versions
            WHERE document_id = ? AND sha256 = ?
            """,
            (document_id, file_hash)
        ).fetchone()

        if existing_version:
            print(
                "Duplicate content: already registered as version "
                f"{existing_version['version_number']}."
            )
            return

        # Assign the next version number.
        latest = connection.execute(
            """
            SELECT MAX(version_number) AS latest_version
            FROM document_versions
            WHERE document_id = ?
            """,
            (document_id,)
        ).fetchone()

        next_version = (latest["latest_version"] or 0) + 1

        connection.execute(
            """
            INSERT INTO document_versions (
                document_id,
                version_number,
                file_path,
                sha256,
                publication_date,
                effective_date
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                document_id,
                next_version,
                str(file_path.resolve()),
                file_hash,
                publication_date,
                effective_date
            )
        )

        print(
            f"Registered '{title}' as version {next_version}."
        )


def list_document_versions(source_url):
    with get_connection() as connection:
        document = connection.execute(
            """
            SELECT document_id, title, regulator
            FROM documents
            WHERE source_url = ?
            """,
            (source_url,)
        ).fetchone()

        if document is None:
            print("Document not found.")
            return

        versions = connection.execute(
            """
            SELECT version_number, file_path, sha256,
                   publication_date, effective_date, retrieved_at
            FROM document_versions
            WHERE document_id = ?
            ORDER BY version_number
            """,
            (document["document_id"],)
        ).fetchall()

        print(f"\nTitle: {document['title']}")
        print(f"Regulator: {document['regulator']}")
        print(f"Total versions: {len(versions)}")

        for version in versions:
            print(f"\nVersion: {version['version_number']}")
            print(f"File: {version['file_path']}")
            print(f"SHA-256: {version['sha256']}")
            print(f"Published: {version['publication_date']}")
            print(f"Effective: {version['effective_date']}")
            print(f"Retrieved: {version['retrieved_at']}")


if __name__ == "__main__":
    initialize_database()

    list_document_versions(
        "https://www.rbi.org.in/example-circular"
    )
