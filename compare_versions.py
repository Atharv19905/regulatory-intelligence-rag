
import sqlite3
from pathlib import Path
from difflib import SequenceMatcher
import pymupdf

DB_PATH = Path("data/regulatory.db")


def extract_text(file_path):
    """Extract text from every page of a PDF."""
    text_parts = []

    with pymupdf.open(file_path) as pdf:
        for page in pdf:
            text_parts.append(page.get_text())

    return "\n".join(text_parts)


def get_versions(document_id):
    """Fetch all registered versions of a document."""
    with sqlite3.connect(DB_PATH) as connection:
        connection.row_factory = sqlite3.Row

        versions = connection.execute(
            """
            SELECT version_id, version_number, file_path,
                   publication_date, effective_date
            FROM document_versions
            WHERE document_id = ?
            ORDER BY version_number
            """,
            (document_id,)
        ).fetchall()

    return versions


def compare_versions(document_id, old_version, new_version):
    versions = get_versions(document_id)

    old_doc = next(
        (v for v in versions if v["version_number"] == old_version),
        None
    )
    new_doc = next(
        (v for v in versions if v["version_number"] == new_version),
        None
    )

    if old_doc is None or new_doc is None:
        print("One or both versions were not found.")
        return

    old_path = Path(old_doc["file_path"])
    new_path = Path(new_doc["file_path"])

    if not old_path.is_file() or not new_path.is_file():
        print("One or both PDF files could not be found.")
        return

    old_text = extract_text(old_path)
    new_text = extract_text(new_path)

    # Split text into lines and compare them.
    old_lines = [
        line.strip() for line in old_text.splitlines() if line.strip()
    ]
    new_lines = [
        line.strip() for line in new_text.splitlines() if line.strip()
    ]

    matcher = SequenceMatcher(
        None, old_lines, new_lines, autojunk=False
    )

    added = []
    removed = []
    modified = []

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "insert":
            added.extend(new_lines[j1:j2])

        elif tag == "delete":
            removed.extend(old_lines[i1:i2])

        elif tag == "replace":
            removed.extend(old_lines[i1:i2])
            added.extend(new_lines[j1:j2])

            modified.append({
                "old": old_lines[i1:i2],
                "new": new_lines[j1:j2]
            })

    print("\n========== VERSION COMPARISON ==========")
    print(f"Document ID: {document_id}")
    print(f"Old version: {old_version}")
    print(f"New version: {new_version}")
    print(f"Old publication date: {old_doc['publication_date']}")
    print(f"New publication date: {new_doc['publication_date']}")

    print("\n--- ADDED TEXT ---")
    print("\n".join(added) if added else "No added text detected.")

    print("\n--- REMOVED TEXT ---")
    print("\n".join(removed) if removed else "No removed text detected.")

    print("\n--- POTENTIALLY MODIFIED TEXT ---")
    if modified:
        for item in modified:
            print("\nOLD:")
            print("\n".join(item["old"]))
            print("NEW:")
            print("\n".join(item["new"]))
    else:
        print("No modified text detected.")

    if not added and not removed:
        print("\nNo text differences detected.")


if __name__ == "__main__":
    with sqlite3.connect(DB_PATH) as connection:
        rows = connection.execute("""
            SELECT d.document_id, d.title,
                   v.version_number, v.publication_date
            FROM documents d
            JOIN document_versions v
                ON d.document_id = v.document_id
            ORDER BY d.document_id, v.version_number
        """).fetchall()

    print("\nRegistered documents and versions:\n")

    for row in rows:
        print(
            f"Document ID: {row[0]} | "
            f"Title: {row[1]} | "
            f"Version: {row[2]} | "
            f"Published: {row[3]}"
        )