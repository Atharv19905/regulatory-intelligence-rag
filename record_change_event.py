
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
    required_phrases = [
        "Limits for Non-Option Derivative Contracts",
        "paragraph 37",
        "stands deleted",
        "come into effect immediately",
    ]

    page_texts = []

    with pymupdf.open(pdf_path) as pdf:
        for page_number, page in enumerate(pdf, start=1):
            page_texts.append({
                "page_number": page_number,
                "text": page.get_text()
            })

    full_text = "\n".join(
        page["text"] for page in page_texts
    )

    missing = [
        phrase for phrase in required_phrases
        if phrase.casefold() not in full_text.casefold()
    ]

    if missing:
        raise RuntimeError(
            "Could not verify amendment evidence in PDF. "
            f"Missing phrases: {missing}"
        )

    for page in page_texts:
        lines = page["text"].splitlines()

        for index, line in enumerate(lines):
            if "stands deleted" in line.casefold():
                start = max(0, index - 3)
                end = min(len(lines), index + 3)

                excerpt = "\n".join(lines[start:end]).strip()

                return (
                    f"[PDF page {page['page_number']}]\n"
                    f"{excerpt}"
                )

    raise RuntimeError(
        "Required deletion evidence was found in the PDF, "
        "but its page could not be identified."
    )

def build_sfb_comparison_report(updated_pdf_path, amendment_evidence):
    """
    Compare the archived historical paragraph with the updated
    RBI consolidated document and amendment evidence.

    This is a candidate deletion assessment, not independent
    verification of the historical RBI wording.
    """

    updated_pages = []

    with pymupdf.open(updated_pdf_path) as pdf:
        for page_number, page in enumerate(pdf, start=1):
            updated_pages.append({
                "page_number": page_number,
                "text": page.get_text()
            })

    updated_text = "\n".join(
        page["text"] for page in updated_pages
    )

    historical_normalized = " ".join(OLD_TEXT.casefold().split())
    updated_normalized = " ".join(updated_text.casefold().split())

    historical_text_present = (
        historical_normalized in updated_normalized
    )

    heading_present_in_body = any(
        "Limits for Non-Option Derivative Contracts".casefold()
        in page["text"].casefold()
        for page in updated_pages
        if page["page_number"] != 2
    )

    amendment_confirms_deletion = (
        "stands deleted" in amendment_evidence.casefold()
    )

    if (
        not historical_text_present
        and not heading_present_in_body
        and amendment_confirms_deletion
    ):
        status = "candidate_deletion"
    else:
        status = "requires_manual_review"

    return {
        "target_title": TARGET_TITLE,
        "provision": PROVISION,
        "status": status,
        "historical_text": OLD_TEXT,
        "historical_source": HISTORICAL_SOURCE_URL,
        "historical_source_status": "secondary_source_unverified",
        "updated_pdf": str(updated_pdf_path),
        "updated_pdf_date": "2026-10-19",
        "historical_text_present_in_updated_pdf": historical_text_present,
        "provision_heading_present_in_updated_body": heading_present_in_body,
        "amendment_evidence": amendment_evidence,
        "amendment_confirms_deletion": amendment_confirms_deletion,
        "requires_historical_source_verification": True,
    }

def build_comparison_report(old_pdf_path, new_pdf_path):
    from compare_versions import extract_pdf_pages, compare_pages

    old_pages = extract_pdf_pages(old_pdf_path)
    new_pages = extract_pdf_pages(new_pdf_path)

    differences = compare_pages(old_pages, new_pages)

    return {
        "old_pdf": str(old_pdf_path),
        "new_pdf": str(new_pdf_path),
        "status": (
            "identical"
            if differences["identical"]
            else "differences_found"
        ),
        "added": differences["added"],
        "removed": differences["removed"],
        "modified": differences["modified"],
    }

def save_change(amendment, evidence, report):
    if report["status"] != "candidate_deletion":
        raise ValueError("Comparison is not eligible for event recording.")

    if not report["amendment_confirms_deletion"]:
        raise ValueError("Amendment deletion evidence is missing.")

    if not report["requires_historical_source_verification"]:
        raise ValueError(
            "Expected explicit historical-source verification status."
        )

    # Keep the existing save_change() implementation below.
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

def validate_sfb_comparison_report(report):
    """Allow final event recording only after source verification."""

    if report.get("status") != "candidate_deletion":
        raise ValueError("Comparison is not eligible for event recording.")

    if not report.get("amendment_confirms_deletion"):
        raise ValueError("Official amendment deletion evidence is missing.")

    if report.get("historical_source_status") != "verified":
        raise ValueError(
            "Historical wording is unverified. "
            "Do not record this as a confirmed regulatory change."
        )

    return True

def build_sfb_candidate_event(report, amendment):
    """Create a retrieval-ready candidate without saving it to the database."""

    validate_sfb_comparison_report_candidate(report)

    return {
        "target_title": report["target_title"],
        "provision": report["provision"],
        "change_type": "candidate_deletion",
        "effective_date": amendment.get("effective_date"),
        "publication_date": amendment.get("publication_date"),
        "amendment_source_url": amendment["source_url"],
        "amendment_evidence": report["amendment_evidence"],
        "provenance_status": (
            "UNVERIFIED CANDIDATE: historical wording comes from "
            "a secondary source; do not present as a confirmed change."
        ),
        "requires_historical_source_verification": True,
    }


def validate_sfb_comparison_report_candidate(report):
    if report.get("status") != "candidate_deletion":
        raise ValueError("Report is not a deletion candidate.")

    if not report.get("amendment_confirms_deletion"):
        raise ValueError("Official amendment evidence is missing.")

    return True

def main():
    amendment = find_amendment()

    evidence = extract_amendment_evidence(
        amendment["pdf_path"]
    )

    report = build_sfb_comparison_report(
        BASE_DIR / "data" / "raw" / "204MD.pdf",
        evidence
    )

    print("\n========== SFB COMPARISON REPORT ==========")

    for key, value in report.items():
        print(f"\n{key}:\n{value}")

    if report["status"] != "candidate_deletion":
        raise RuntimeError(
            "Comparison requires manual review. "
            "No change event was recorded."
        )

    print(
        "\nCandidate deletion identified. "
        "Historical source verification is still required."
    )


if __name__ == "__main__":
    main()
