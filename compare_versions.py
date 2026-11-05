
import sqlite3
import re
from pathlib import Path
from difflib import SequenceMatcher
import pymupdf


BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "data" / "regulatory.db"


def extract_pdf_pages(file_path):
    """Extract text from a PDF while preserving page numbers."""

    pages = []

    with pymupdf.open(file_path) as pdf:
        for page_number, page in enumerate(pdf, start=1):
            text = page.get_text("text")

            pages.append({
                "page_number": page_number,
                "text": text,
            })

    return pages


def normalize_text(text):
    """Normalize whitespace without removing meaningful wording."""

    text = text.replace("\u00a0", " ")
    text = re.sub(r"\s+", " ", text)

    return text.strip()


def get_versions(document_id, db_path=None):
    """Fetch registered versions of a document."""

    database = Path(db_path) if db_path else DB_PATH

    connection = sqlite3.connect(
        f"file:{database.resolve().as_posix()}?mode=ro",
        uri=True,
    )

    connection.row_factory = sqlite3.Row

    try:
        versions = connection.execute(
            """
            SELECT
                version_id,
                document_id,
                version_number,
                file_path,
                sha256,
                publication_date,
                effective_date
            FROM document_versions
            WHERE document_id = ?
            ORDER BY version_number
            """,
            (document_id,),
        ).fetchall()

        return [dict(row) for row in versions]

    finally:
        connection.close()


def compare_texts(old_text, new_text):
    """Compare normalized text and return structured differences."""

    old_lines = [
        normalize_text(line)
        for line in old_text.splitlines()
        if normalize_text(line)
    ]

    new_lines = [
        normalize_text(line)
        for line in new_text.splitlines()
        if normalize_text(line)
    ]

    matcher = SequenceMatcher(
        None,
        old_lines,
        new_lines,
        autojunk=False,
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

            old_block = old_lines[i1:i2]
            new_block = new_lines[j1:j2]

            removed.extend(old_block)
            added.extend(new_block)

            modified.append({
                "old": old_block,
                "new": new_block,
            })

    return {
        "added": added,
        "removed": removed,
        "modified": modified,
        "identical": old_lines == new_lines,
    }


def compare_pages(old_pages, new_pages):
    """
    Compare two PDF versions while preserving source page numbers.
    Uses a document-wide comparison so page insertions do not
    incorrectly shift every subsequent page comparison.
    """

    def prepare_lines(pages):
        lines = []
        page_numbers = []

        for page in pages:
            page_number = page["page_number"]
            text = normalize_text(page["text"])

            for line in text.splitlines():
                line = line.strip()

                if line:
                    lines.append(line)
                    page_numbers.append(page_number)

        return lines, page_numbers

    old_lines, old_page_numbers = prepare_lines(old_pages)
    new_lines, new_page_numbers = prepare_lines(new_pages)

    matcher = SequenceMatcher(
        None,
        old_lines,
        new_lines,
        autojunk=False
    )

    added = []
    removed = []
    modified = []

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():

        if tag == "equal":
            continue

        old_evidence = [
            {
                "page_number": old_page_numbers[i],
                "text": old_lines[i]
            }
            for i in range(i1, i2)
        ]

        new_evidence = [
            {
                "page_number": new_page_numbers[i],
                "text": new_lines[i]
            }
            for i in range(j1, j2)
        ]

        if tag == "replace":
            modified.append({
                "old": old_evidence,
                "new": new_evidence
            })

        elif tag == "delete":
            removed.extend(old_evidence)

        elif tag == "insert":
            added.extend(new_evidence)

    return {
        "added": added,
        "removed": removed,
        "modified": modified,
        "identical": not (added or removed or modified)
    }

def compare_versions(
    document_id,
    old_version,
    new_version,
    db_path=None,
):
    """Compare two registered PDF versions of a regulation."""

    if old_version == new_version:
        raise ValueError("Old and new versions must be different.")

    versions = get_versions(document_id, db_path)

    old_doc = next(
        (
            version for version in versions
            if version["version_number"] == old_version
        ),
        None,
    )

    new_doc = next(
        (
            version for version in versions
            if version["version_number"] == new_version
        ),
        None,
    )

    if old_doc is None or new_doc is None:
        raise ValueError("One or both versions were not found.")

    old_path = Path(old_doc["file_path"])
    new_path = Path(new_doc["file_path"])

    if not old_path.is_file() or not new_path.is_file():
        raise FileNotFoundError(
            "One or both registered PDF files could not be found."
        )

    if old_doc["sha256"] == new_doc["sha256"]:
        return {
            "document_id": document_id,
            "old_version": old_version,
            "new_version": new_version,
            "old_publication_date": old_doc["publication_date"],
            "new_publication_date": new_doc["publication_date"],
            "old_effective_date": old_doc["effective_date"],
            "new_effective_date": new_doc["effective_date"],
            "identical": True,
            "added": [],
            "removed": [],
            "modified": [],
        }

    old_pages = extract_pdf_pages(old_path)
    new_pages = extract_pdf_pages(new_path)

    old_text = "\n".join(
        page["text"] for page in old_pages
    )

    new_text = "\n".join(
        page["text"] for page in new_pages
    )

    differences = compare_pages(old_pages, new_pages)
    return {
        "document_id": document_id,
        "old_version": old_version,
        "new_version": new_version,
        "old_publication_date": old_doc["publication_date"],
        "new_publication_date": new_doc["publication_date"],
        "old_effective_date": old_doc["effective_date"],
        "new_effective_date": new_doc["effective_date"],
        "identical": differences["identical"],
        "added": differences["added"],
        "removed": differences["removed"],
        "modified": differences["modified"],
    }


def print_comparison(result):
    """Display a structured comparison report."""

    print("\n========== VERSION COMPARISON ==========")

    print(f"Document ID: {result['document_id']}")
    print(f"Old version: {result['old_version']}")
    print(f"New version: {result['new_version']}")

    print(
        f"Old publication date: "
        f"{result['old_publication_date']}"
    )

    print(
        f"New publication date: "
        f"{result['new_publication_date']}"
    )

    print(
        f"Old effective date: "
        f"{result['old_effective_date']}"
    )

    print(
        f"New effective date: "
        f"{result['new_effective_date']}"
    )

    if result["identical"]:
        print("\nThe two PDF versions have identical SHA-256 hashes or text.")
        return

    print("\n--- ADDED TEXT ---")
    print("\n".join(result["added"]) or "No added text detected.")

    print("\n--- REMOVED TEXT ---")
    print("\n".join(result["removed"]) or "No removed text detected.")

    print("\n--- POTENTIALLY MODIFIED TEXT ---")

    if result["modified"]:
        for item in result["modified"]:
            print("\nOLD:")
            print("\n".join(item["old"]))

            print("\nNEW:")
            print("\n".join(item["new"]))

    else:
        print("No modified text detected.")


if __name__ == "__main__":
    with sqlite3.connect(
        f"file:{DB_PATH.as_posix()}?mode=ro",
        uri=True,
    ) as connection:

        rows = connection.execute(
            """
            SELECT
                d.document_id,
                d.title,
                v.version_number,
                v.publication_date
            FROM documents d
            JOIN document_versions v
                ON d.document_id = v.document_id
            ORDER BY d.document_id, v.version_number
            """
        ).fetchall()

    print("\nRegistered documents and versions:\n")

    for row in rows:
        print(
            f"Document ID: {row[0]} | "
            f"Title: {row[1]} | "
            f"Version: {row[2]} | "
            f"Published: {row[3]}"
        )
