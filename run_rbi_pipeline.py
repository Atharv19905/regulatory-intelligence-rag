"""Safe RBI Master Directions workflow.

Supports:
- --discover: refresh the RBI discovery manifest.
- --download-ids: download and register selected PDFs (network permitting).
- --register-local: register an already-downloaded local PDF for one RBI ID.
- --compare: compare the two latest versions of a registered document.

This script does not index Qdrant. Use the dedicated indexing workflow only
when registration has been checked and indexing is explicitly intended.
"""

import argparse
import hashlib
import json
import os
import re
import time
from pathlib import Path
from urllib.parse import urlparse

import requests

from discover_rbi_master_directions import discover_master_directions
from metadata_db import initialize_database, register_document
from compare_versions import get_versions, compare_versions, print_comparison

BASE_DIR = Path(__file__).resolve().parent
MANIFEST = BASE_DIR / "data" / "versions" / "rbi_master_directions_discovered.json"
RAW_DIR = BASE_DIR / "data" / "raw"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 Chrome/120.0 Safari/537.36",
    "Referer": "https://www.rbi.org.in/",
}


def load_manifest():
    if not MANIFEST.is_file():
        raise FileNotFoundError(
            f"Discovery manifest not found: {MANIFEST}. Run discovery first."
        )
    payload = json.loads(MANIFEST.read_text(encoding="utf-8"))
    records = payload.get("records", [])
    if not isinstance(records, list):
        raise ValueError("Manifest format error: 'records' must be a list.")
    return records


def records_by_id():
    result = {}
    for record in load_manifest():
        detail_url = record.get("detail_url", "")
        match = re.search(r"[?&]id=(\d+)", detail_url, re.I)
        if match:
            result[match.group(1)] = record
    return result


def validate_rbi_url(url):
    parsed = urlparse(url or "")
    host = (parsed.hostname or "").lower()
    if parsed.scheme != "https" or not (host == "rbi.org.in" or host.endswith(".rbi.org.in")):
        raise ValueError(f"Refusing non-RBI or non-HTTPS URL: {url}")


def validate_pdf_file(file_path):
    path = Path(file_path).expanduser()
    if not path.is_absolute():
        path = (BASE_DIR / path).resolve()
    if not path.is_file():
        raise FileNotFoundError(f"Local PDF not found: {path}")
    if path.stat().st_size < 8:
        raise ValueError(f"File is too small to be a valid PDF: {path}")
    with path.open("rb") as file:
        signature = file.read(5)
    if signature != b"%PDF-":
        raise ValueError(f"File does not have a PDF signature: {path}")
    return path


def sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as file:
        for block in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def register_local(record_id, local_pdf):
    by_id = records_by_id()
    record = by_id.get(str(record_id))
    if record is None:
        raise ValueError(f"RBI ID {record_id} was not found in the discovery manifest.")

    detail_url = record.get("detail_url")
    if not detail_url:
        raise ValueError(f"Manifest record {record_id} has no official detail URL.")
    validate_rbi_url(detail_url)

    pdf_path = validate_pdf_file(local_pdf)
    digest = sha256_file(pdf_path)
    initialize_database()

    # The current manifest entry for 13729 marks its date as coming from a
    # neighbouring listing row. Do not store that as a verified publication date.
    date_source = record.get("publication_date_source")
    publication_date = record.get("publication_date") if date_source in ("detail_page", "document_header", "verified_official_page") else None

    print(f"RBI ID: {record_id}")
    print(f"Title: {record.get('title', 'Untitled RBI document')}")
    print(f"Local PDF: {pdf_path}")
    print(f"Size: {pdf_path.stat().st_size:,} bytes")
    print(f"SHA-256: {digest}")
    print(f"Publication date stored: {publication_date!r}")
    if record.get("publication_date") and publication_date is None:
        print("NOTE: Manifest date is not from a verified date source; storing NULL instead.")

    register_document(
        source_url=detail_url,
        title=record.get("title", "Untitled RBI Master Direction"),
        regulator="RBI",
        file_path=pdf_path,
        publication_date=publication_date,
        effective_date=None,
    )
    print("Local PDF registration step completed. This script did not modify Qdrant.")


def download_selected(record_ids):
    by_id = records_by_id()
    missing = sorted(set(map(str, record_ids)) - set(by_id))
    if missing:
        raise ValueError("IDs not found in latest discovery manifest: " + ", ".join(missing))

    initialize_database()
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    session.headers.update(HEADERS)

    for record_id in map(str, record_ids):
        record = by_id[record_id]
        pdf_url = record.get("pdf_url")
        detail_url = record.get("detail_url")
        if not pdf_url or not detail_url:
            print(f"SKIP {record_id}: missing PDF or detail URL; review manifest.")
            continue
        validate_rbi_url(pdf_url)
        validate_rbi_url(detail_url)
        if not urlparse(pdf_url).path.lower().endswith(".pdf"):
            print(f"SKIP {record_id}: manifest URL is not a direct PDF URL.")
            continue

        try:
            response = session.get(pdf_url, timeout=60)
            response.raise_for_status()
        except requests.RequestException as error:
            print(f"DOWNLOAD FAILED {record_id}: {error}")
            print("You can download this PDF in a browser and use --register-local.")
            continue

        content = response.content
        if not content.startswith(b"%PDF-"):
            print(f"SKIP {record_id}: RBI returned non-PDF content; not registered.")
            print("HTTP:", response.status_code, "Content-Type:", response.headers.get("Content-Type"))
            continue

        digest = hashlib.sha256(content).hexdigest()
        file_path = RAW_DIR / f"rbi_master_{record_id}_{digest[:16]}.pdf"
        if not file_path.exists():
            file_path.write_bytes(content)

        date_source = record.get("publication_date_source")
        publication_date = record.get("publication_date") if date_source in ("detail_page", "document_header", "verified_official_page") else None
        register_document(
            source_url=detail_url,
            title=record.get("title", "Untitled RBI Master Direction"),
            regulator="RBI",
            file_path=file_path,
            publication_date=publication_date,
            effective_date=None,
        )
        print(f"Processed RBI Master Direction ID {record_id}: {record.get('title')}")
        time.sleep(1)


def compare_latest(document_id):
    versions = get_versions(document_id)
    if len(versions) < 2:
        print(f"Document {document_id} has {len(versions)} registered version(s); need at least 2 to compare.")
        return
    old_version = versions[-2]["version_number"]
    new_version = versions[-1]["version_number"]
    result = compare_versions(document_id, old_version, new_version)
    print_comparison(result)
    print("\nInterpretation: textual differences are not automatically legally verified amendments.")


def main():
    os.chdir(BASE_DIR)
    parser = argparse.ArgumentParser(description="Safe RBI Master Directions workflow")
    parser.add_argument("--discover", action="store_true", help="Refresh RBI discovery manifest")
    parser.add_argument("--download-ids", nargs="+", help="Download and register selected RBI IDs")
    parser.add_argument("--register-local", nargs=2, metavar=("RBI_ID", "PDF_PATH"), help="Register an already-downloaded local PDF for one RBI ID")
    parser.add_argument("--compare", type=int, metavar="DOCUMENT_ID", help="Compare the two latest registered versions")
    args = parser.parse_args()

    if not any((args.discover, args.download_ids, args.register_local, args.compare is not None)):
        parser.print_help()
        return
    if args.discover:
        discover_master_directions()
        print("Discovery complete. Review the manifest before selecting IDs.")
    if args.register_local:
        record_id, pdf_path = args.register_local
        register_local(record_id, pdf_path)
    if args.download_ids:
        download_selected(args.download_ids)
    if args.compare is not None:
        compare_latest(args.compare)


if __name__ == "__main__":
    main()
