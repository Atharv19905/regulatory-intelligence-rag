
import json
import re
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse, parse_qs

import requests
from bs4 import BeautifulSoup

INPUT_FILE = Path(
    "data/versions/rbi_master_directions_discovered.json"
)

OUTPUT_FILE = Path(
    "data/versions/rbi_master_directions_enriched.json"
)

USER_AGENT = "RegulatoryResearchProject/1.0"
REQUEST_DELAY_SECONDS = 0.5


def get_document_id(url):
    query = parse_qs(urlparse(url).query)
    return query.get("id", [None])[0]


def parse_date(text):
    text = " ".join(text.split()).strip(" .,:;")
    formats = [
        "%B %d, %Y",
        "%b %d, %Y",
        "%b. %d, %Y",
        "%d %B %Y",
        "%d %b %Y",
    ]


    for fmt in formats:
        try:
            return datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            continue

    return None



def find_date_in_text(text):
    pattern = (
        r"\b("
        r"(?:January|February|March|April|May|June|July|August|"
        r"September|October|November|December)"
        r"\s+\d{1,2},?\s+\d{4}"
        r"|"
        r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)"
        r"\.?\s+\d{1,2},?\s+\d{4}"
        r"|"
        r"\d{1,2}\s+"
        r"(?:January|February|March|April|May|June|July|August|"
        r"September|October|November|December)"
        r"\s+\d{4}"
        r")\b"
    )

    match = re.search(pattern, text, re.IGNORECASE)
    return parse_date(match.group(0)) if match else None


def extract_dates(session, record):
    result = {
        "publication_date_extracted": None,
        "updated_as_of_date": None,
        "date_extraction_source": None,
        "date_review_status": "needs_review",
        "date_discrepancy": False,
        "date_extraction_error": None,
    }

    url = record.get("detail_url")

    if not url:
        result["date_extraction_error"] = "Missing detail URL"
        result["date_review_status"] = "parse_error"
        return result

    reference_pattern = re.compile(
        r"\bRBI/(?:"
        r"[A-Z0-9.-]+/\d{4}-\d{2,4}/\d+"
        r"|"
        r"\d{4}-\d{2,4}/\d+"
        r")\b",
        re.IGNORECASE,
    )

    def inspect_page(page_url):
        """Return an issue date and update date from an RBI page."""
        response = session.get(page_url, timeout=30)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")
        page_text = soup.get_text(" ", strip=True)

        update_dates = re.findall(
            r"Updated\s+as\s+on\s+"
            r"([A-Za-z]+\s+\d{1,2},?\s+\d{4}|"
            r"\d{1,2}\s+[A-Za-z]+\s+\d{4})",
            page_text,
            re.IGNORECASE,
        )

        updated_date = (
            find_date_in_text(update_dates[0])
            if update_dates
            else None
        )

        paragraphs = soup.find_all("p")

        for index, paragraph in enumerate(paragraphs):
            reference_text = paragraph.get_text(" ", strip=True)

            if not reference_pattern.search(reference_text):
                continue

            # Some RBI pages put the reference and issue date
            # in the same paragraph.
            cleaned_reference_text = re.sub(
                r"\(?\s*Updated\s+as\s+on\s+"
                r"(?:[A-Za-z]+\s+\d{1,2},?\s+\d{4}|"
                r"\d{1,2}\s+[A-Za-z]+\s+\d{4})"
                r"\s*\)?",
                "",
                reference_text,
                flags=re.IGNORECASE,
            )

            issue_date = find_date_in_text(cleaned_reference_text)

            if issue_date:
                return issue_date, updated_date

            # Otherwise, search the next three paragraphs.
            for following in paragraphs[index + 1:index + 4]:
                text = following.get_text(" ", strip=True)

                text = re.sub(
                    r"\(?\s*Updated\s+as\s+on\s+"
                    r"(?:[A-Za-z]+\s+\d{1,2},?\s+\d{4}|"
                    r"\d{1,2}\s+[A-Za-z]+\s+\d{4})"
                    r"\s*\)?",
                    "",
                    text,
                    flags=re.IGNORECASE,
                )

                issue_date = find_date_in_text(text)

                if issue_date:
                    return issue_date, updated_date
        return None, updated_date

    try:
        issue_date, updated_date = inspect_page(url)
        result["updated_as_of_date"] = updated_date

        if issue_date:
            result["publication_date_extracted"] = issue_date
            result["date_extraction_source"] = (
                "RBI current detail page"
            )

        # If the current page lacks the issue date, check the
        # official RBI previous-version page for this document.
        if not issue_date:
            document_id = get_document_id(url)

            if document_id:
                archive_url = (
                    "https://www.rbi.org.in/scripts/"
                    f"NotificationPreVersion.aspx?id={document_id}"
                )

                response = session.get(archive_url, timeout=30)
                response.raise_for_status()

                archive_soup = BeautifulSoup(
                    response.text, "html.parser"
                )

                archive_links = []

                for link in archive_soup.find_all("a", href=True):
                    href = link["href"]
                    label = link.get_text(" ", strip=True)

                    if "Histid=" not in href:
                        continue

                    # Resolve relative links against the official RBI site.
                    from urllib.parse import urljoin
                    archive_links.append(
                        (urljoin(archive_url, href), label)
                    )

                # Try archived versions in listing order.
                for historical_url, label in archive_links:
                    archived_issue_date, archived_update_date = (
                        inspect_page(historical_url)
                    )

                    if archived_issue_date:
                        issue_date = archived_issue_date
                        result["publication_date_extracted"] = (
                            archived_issue_date
                        )
                        result["date_extraction_source"] = (
                            "Official RBI archived version: "
                            + historical_url
                        )

                        # Preserve the current page's update date
                        # when available; otherwise retain archive metadata.
                        if not result["updated_as_of_date"]:
                            result["updated_as_of_date"] = (
                                archived_update_date
                                or find_date_in_text(label)
                            )
                        break

        existing_date = record.get("publication_date")
        extracted_date = result["publication_date_extracted"]

        if not extracted_date:
            result["date_review_status"] = "date_not_found"

        elif existing_date and existing_date != extracted_date:
            result["date_discrepancy"] = True
            result["date_review_status"] = "needs_review"

        elif existing_date:
            result["date_review_status"] = "matched"

        else:
            result["date_review_status"] = "extracted_unverified"

    except requests.RequestException as exc:
        result["date_extraction_error"] = str(exc)
        result["date_review_status"] = "fetch_error"

    except Exception as exc:
        result["date_extraction_error"] = (
            f"{type(exc).__name__}: {exc}"
        )
        result["date_review_status"] = "parse_error"

    return result



def main():
    if not INPUT_FILE.exists():
        raise FileNotFoundError(
            f"Input file not found: {INPUT_FILE}"
        )

    # Keep the original top-level metadata and records.
    data = json.loads(INPUT_FILE.read_text(encoding="utf-8"))
    records = data.get("records")

    if not isinstance(records, list):
        raise ValueError("Expected a list under the 'records' key")

    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})

    enriched_records = []
    total = len(records)

    for index, original_record in enumerate(records, start=1):
        record = dict(original_record)

        print(
            f"[{index}/{total}] "
            f"{record.get('title', 'Untitled')[:75]}"
        )

        extracted = extract_dates(session, record)

        # Add new fields without overwriting the original publication date.
        record.update(extracted)
        enriched_records.append(record)

        if index < total:
            time.sleep(REQUEST_DELAY_SECONDS)

    output_data = dict(data)
    output_data["records"] = enriched_records
    output_data["enrichment_summary"] = {
        "records_processed": total,
        "records_with_extracted_dates": sum(
            bool(r.get("publication_date_extracted"))
            for r in enriched_records
        ),
        "date_conflicts": sum(
            r.get("date_discrepancy", False)
            for r in enriched_records
        ),
        "updated_as_of_dates_found": sum(
            bool(r.get("updated_as_of_date"))
            for r in enriched_records
        ),
        "note": (
            "Original publication_date values are preserved. "
            "Extracted dates are separate and require review."
        ),
    }

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(
        json.dumps(output_data, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print("\nEnrichment complete.")
    print("Output:", OUTPUT_FILE)
    print(
        json.dumps(
            output_data["enrichment_summary"],
            indent=2,
        )
    )
    print("Original discovery JSON was not modified.")
    print("Database was not modified.")


if __name__ == "__main__":
    main()
