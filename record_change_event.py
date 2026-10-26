
import sqlite3
from pathlib import Path
from datetime import datetime, timezone

import pymupdf


BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "data" / "regulatory.db"

AMENDMENT_URL = (
    "https://rbi.org.in/scripts/NotificationUser.aspx?Mode=0&Id=13741"
)

HISTORICAL_SOURCE_URL = (
    "https://trackrbi.com/notification/13105/"
    "reserve-bank-of-india-small-finance-banks-miscellaneous-directions-2025"
)

TARGET_TITLE = (
    "Reserve Bank of India (Small Finance Banks - Miscellaneous) "
    "Directions, 2025"
)

PROVISION = (
    "Chapter IV, Section C, paragraph 37: "
    "Limits for Non-Option Derivative Contracts"
)

OLD_TEXT = (
    "The gross PV 01 of all non-option rupee derivative contracts "
    "(including rupee - foreign currency contracts) of a bank shall "
    "be within 0.25 per cent of its net worth as on the last balance "
    "sheet date. The limit shall, however, exclude the PV 01 of "
    "derivatives which are hedges for balance sheet exposures provided "
    "these hedges meet the criteria of hedge effectiveness as laid down "
    "in circular IDMC.MSRD.4801/06.01.03/2002-03 dated June 3, 2003 "
    "(as amended from time to time)."
)


def find_amendment():
    connection = sqlite3.connect(DB_PATH)

    try:
        row = connection.execute(
            """
            SELECT d.document_id, d.title, d.source_url,
                   v.version_id, v.file_path, v.publication_date,
                   v.effective_date
            FROM documents d
            JOIN document_versions v
              ON v.document_id = d.document_id
            WHERE d.source_url = ?
            ORDER BY v.version_number DESC
            LIMIT 1
            """,
            (AMENDMENT_URL,)
        ).fetchone()
    finally:
        connection.close()

    if not row:
        raise RuntimeError(
            "Amendment not found in SQLite. Check the registered source URL."
        )

    document_id, title, source_url, version_id, file_path, pub_date, eff_date = row

    pdf_path = Path(file_path)
    if not pdf_path.is_absolute():
        pdf_path = BASE_DIR / pdf_path

    if not pdf_path.exists():
        raise FileNotFoundError(f"Amendment PDF not found: {pdf_path}")

    return {
        "document_id": document_id,
        "title": title,
        "source_url": source_url,
        "version_id": version_id,
        "pdf_path": pdf_path,
        "publication_date": pub_date,
        "effective_date": eff_date,
    }


def extract_amendment_evidence(pdf_path):
    with pymupdf.open(pdf_path) as pdf:
        full_text = "\n".join(page.get_text() for page in pdf)

    required_phrases = [
        "Limits for Non-Option Derivative Contracts",
        "paragraph 37",
        "stands deleted",
        "come into effect immediately",
    ]

    missing = [
        phrase for phrase in required_phrases
        if phrase.casefold() not in full_text.casefold()
    ]

    if missing:
        raise RuntimeError(
            "Could not verify amendment evidence in PDF. "
            f"Missing phrases: {missing}"
        )

    lines = full_text.splitlines()
    evidence_lines = []

    for index, line in enumerate(lines):
        if "stands deleted" in line.casefold():
            start = max(0, index - 3)
            end = min(len(lines), index + 2)
            evidence_lines = lines[start:end]
            break

    return "\n".join(evidence_lines).strip()


def save_change(amendment, evidence):
    connection = sqlite3.connect(DB_PATH)

    try:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS regulatory_changes (
                change_id INTEGER PRIMARY KEY AUTOINCREMENT,
                target_title TEXT NOT NULL,
                provision TEXT NOT NULL,
                change_type TEXT NOT NULL,
                effective_date TEXT NOT NULL,
                old_text TEXT NOT NULL,
                new_text TEXT NOT NULL,
                historical_source_url TEXT NOT NULL,
                amendment_source_url TEXT NOT NULL,
                amendment_document_id INTEGER NOT NULL,
                amendment_version_id INTEGER NOT NULL,
                amendment_evidence TEXT NOT NULL,
                provenance_status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                UNIQUE (
                    target_title,
                    provision,
                    amendment_version_id
                )
            )
            """
        )

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
                old_text = excluded.old_text,
                new_text = excluded.new_text,
                amendment_evidence = excluded.amendment_evidence,
                historical_source_url = excluded.historical_source_url,
                provenance_status = excluded.provenance_status
            """,
            (
                TARGET_TITLE,
                PROVISION,
                "deletion",
                "2026-10-19",
                OLD_TEXT,
                "[Paragraph deleted by amendment]",
                HISTORICAL_SOURCE_URL,
                amendment["source_url"],
                amendment["document_id"],
                amendment["version_id"],
                evidence,
                "Historical wording from secondary archive; "
                "verify against an original historical RBI document",
                datetime.now(timezone.utc).isoformat(),
            ),
        )

        connection.commit()

        row = connection.execute(
            """
            SELECT change_id, target_title, provision, change_type,
                   effective_date, provenance_status
            FROM regulatory_changes
            WHERE target_title = ?
              AND provision = ?
              AND amendment_version_id = ?
            """,
            (TARGET_TITLE, PROVISION, amendment["version_id"]),
        ).fetchone()

        print("\nChange event saved successfully.")
        print(f"Change ID: {row[0]}")
        print(f"Regulation: {row[1]}")
        print(f"Provision: {row[2]}")
        print(f"Change type: {row[3]}")
        print(f"Effective date: {row[4]}")
        print(f"Historical source status: {row[5]}")

    finally:
        connection.close()


def main():
    amendment = find_amendment()
    evidence = extract_amendment_evidence(amendment["pdf_path"])

    print("Verified amendment evidence:")
    print(evidence)

    save_change(amendment, evidence)


if __name__ == "__main__":
    main()
