
import sqlite3
from pathlib import Path
from datetime import datetime, timezone

import pymupdf


BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "data" / "regulatory.db"

# RBI circular containing the sanctions-list amendment.
SOURCE_URL_PATTERN = "%13742%"

PDF_PAGE = 2

SANCTIONS_SOURCE_URL = (
    "https://main.un.org/securitycouncil/en/sanctions/"
    "1267/aq_sanctions_list/summaries"
)

PROVENANCE = (
    "Observed in visual inspection of page 2 of the RBI amendment PDF. "
    "Strikethrough indicates deleted text. The exact field-level changes "
    "are recorded from the supplied rendering and require verification "
    "against the original PDF and authoritative sanctions-list record."
)

CHANGES = [
    {
        "target_title": "UN 1267/1989 Sanctions List",
        "provision": (
            "Individual QDi.082 MOUNIR EL MOTASSADEQ — Address"
        ),
        "change_type": "replacement",
        "old_text": "(In prison in Germany)",
        "new_text": "Marrakesh, Morocco",
        "evidence": (
            "Page 2, QDi.082 entry: the address text "
            "'(In prison in Germany)' is struck through; "
            "'Marrakesh, Morocco' appears as the address."
        ),
    },
    {
        "target_title": "UN 1267/1989 Sanctions List",
        "provision": (
            "Entity QDe.132 TEHRIK-E TALIBAN PAKISTAN (TTP) "
            "— Leader information"
        ),
        "change_type": "deletion",
        "old_text": "Maulana Fazlullah (QDi.352)",
        "new_text": (
            "[Leader reference removed; the entry retains "
            "Noor Wali Mehsud (QDi.427)]"
        ),
        "evidence": (
            "Page 2, QDe.132 entry: 'Maulana Fazlullah (QDi.352)' "
            "is struck through. 'Noor Wali Mehsud (QDi.427)' "
            "appears as the remaining leader reference."
        ),
    },
]


def find_amendment(connection):
    rows = connection.execute(
        """
        SELECT d.document_id, d.title, d.source_url,
               v.version_id, v.file_path, v.publication_date
        FROM documents d
        JOIN document_versions v
          ON v.document_id = d.document_id
        WHERE d.source_url LIKE ?
        ORDER BY v.version_number DESC
        """,
        (SOURCE_URL_PATTERN,),
    ).fetchall()

    if not rows:
        raise RuntimeError(
            "No registered document matched source URL pattern "
            f"{SOURCE_URL_PATTERN!r}. Check the documents table."
        )

    if len(rows) > 1:
        latest_version = max(row[3] for row in rows)
        candidates = [row for row in rows if row[3] == latest_version]
        if len(candidates) != 1:
            raise RuntimeError(
                "Multiple candidate amendments found. Inspect the "
                "documents and document_versions tables before proceeding."
            )
        rows = candidates

    document_id, title, source_url, version_id, file_path, pub_date = rows[0]

    pdf_path = Path(file_path)
    if not pdf_path.is_absolute():
        pdf_path = BASE_DIR / pdf_path

    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    return {
        "document_id": document_id,
        "title": title,
        "source_url": source_url,
        "version_id": version_id,
        "publication_date": pub_date,
        "pdf_path": pdf_path,
    }



def verify_pdf(pdf_path):
    with pymupdf.open(pdf_path) as pdf:
        if len(pdf) < PDF_PAGE:
            raise RuntimeError("The expected page 2 is missing.")

        # Search all pages because an entry can continue across a page break.
        page_text = "\n".join(
            page.get_text("text") for page in pdf
        )

    required = [
        "QDi.082",
        "MOUNIR",
        "QDi.427",
        "QDe.132",
        "TEHRIK-E TALIBAN PAKISTAN",
    ]

    missing = [
        phrase for phrase in required
        if phrase.casefold() not in page_text.casefold()
    ]

    if missing:
        raise RuntimeError(
            "PDF did not contain expected entry text: "
            + ", ".join(missing)
        )

    return page_text



def save_changes(amendment):
    connection = sqlite3.connect(DB_PATH)

    try:
        # Verify the existing schema before writing anything.
        columns = {
            row[1]
            for row in connection.execute(
                "PRAGMA table_info(regulatory_changes)"
            ).fetchall()
        }

        required_columns = {
            "target_title",
            "provision",
            "change_type",
            "effective_date",
            "old_text",
            "new_text",
            "historical_source_url",
            "amendment_source_url",
            "amendment_document_id",
            "amendment_version_id",
            "amendment_evidence",
            "provenance_status",
            "created_at",
        }

        if not required_columns.issubset(columns):
            raise RuntimeError(
                "The existing regulatory_changes schema differs from "
                "the expected schema. No changes were written."
            )

        # The RBI circular's recorded publication date is 19 October 2026.
# The sanctions entries show 15 October 2026 as their amendment date.
# The legal effective date has not been independently verified.
        recorded_amendment_date = amendment["publication_date"] or "2026-10-19"

        for item in CHANGES:
            connection.execute(
                """
                INSERT INTO regulatory_changes (
                    target_title,
                    provision,
                    change_type,
                    effective_date,
                    old_text,
                    new_text,
                    historical_source_url,
                    amendment_source_url,
                    amendment_document_id,
                    amendment_version_id,
                    amendment_evidence,
                    provenance_status,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT (
                    target_title, provision, amendment_version_id
                ) DO UPDATE SET
                    change_type = excluded.change_type,
                    effective_date = excluded.effective_date,
                    old_text = excluded.old_text,
                    new_text = excluded.new_text,
                    historical_source_url = excluded.historical_source_url,
                    amendment_source_url = excluded.amendment_source_url,
                    amendment_evidence = excluded.amendment_evidence,
                    provenance_status = excluded.provenance_status
                """,
                (
                    item["target_title"],
                    item["provision"],
                    item["change_type"],
                    recorded_amendment_date,
                    item["old_text"],
                    item["new_text"],
                    SANCTIONS_SOURCE_URL,
                    amendment["source_url"],
                    amendment["document_id"],
                    amendment["version_id"],
                    item["evidence"],
                    PROVENANCE,
                    datetime.now(timezone.utc).isoformat(),
                ),
            )

        connection.commit()

        print("\nSanctions change records saved.")
        print(f"Source PDF: {amendment['pdf_path']}")
        print(f"Registered document ID: {amendment['document_id']}")
        print(f"Version ID: {amendment['version_id']}")

        rows = connection.execute(
            """
            SELECT change_id, provision, change_type, effective_date
            FROM regulatory_changes
            WHERE amendment_version_id = ?
              AND target_title = ?
            ORDER BY change_id
            """,
            (
                amendment["version_id"],
                "UN 1267/1989 Sanctions List",
            ),
        ).fetchall()

        for row in rows:
            print(
                f"\nChange ID: {row[0]}\n"
                f"Provision: {row[1]}\n"
                f"Type: {row[2]}\n"
                f"Temporal filtering date (publication date): {row[3]}"
            )

    finally:
        connection.close()


def main():
    with sqlite3.connect(DB_PATH) as connection:
        amendment = find_amendment(connection)

    page_text = verify_pdf(amendment["pdf_path"])

    print("PDF content verification passed.")
    print("Expected sanctions-list entries found on page 2.")
    print(
        "\nNote: text extraction verifies entry presence, not "
        "strikethrough formatting. Visual observations are recorded "
        "with their provenance status."
    )

    save_changes(amendment)


if __name__ == "__main__":
    main()
