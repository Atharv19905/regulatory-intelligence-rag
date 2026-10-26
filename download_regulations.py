
import hashlib
import time
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from metadata_db import initialize_database, register_document

RBI_INDEX = (
    "https://www.rbi.org.in/scripts/"
    "bs_circularindexdisplay.aspx/Scripts/BS_CircularIndexDisplay.aspx"
)

RAW_DIR = Path("data/raw")
RAW_DIR.mkdir(parents=True, exist_ok=True)

session = requests.Session()
session.headers.update({
    "User-Agent": "RegulatoryIntelligenceStudentProject/1.0"
})


def is_rbi_url(url):
    host = (urlparse(url).hostname or "").lower()
    return host == "rbi.org.in" or host.endswith(".rbi.org.in")


def discover_pdf_links(page_url):
    response = session.get(page_url, timeout=30)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    discovered = []

    for anchor in soup.find_all("a", href=True):
        pdf_url = urljoin(page_url, anchor["href"])

        if not is_rbi_url(pdf_url):
            continue

        if urlparse(pdf_url).path.lower().endswith(".pdf"):
            title = anchor.get_text(" ", strip=True)
            discovered.append((pdf_url, title or "RBI circular"))

    return discovered


def download_and_register(pdf_url, title):
    response = session.get(pdf_url, timeout=60)
    response.raise_for_status()

    content = response.content

    print("HTTP status:", response.status_code)
    print("Content-Type:", response.headers.get("Content-Type"))
    print("Final URL:", response.url)
    print("First 100 bytes:", repr(content[:100]))

    if not content.startswith(b"%PDF-"):
        print(f"Skipped: response is not a PDF: {pdf_url}")
        html_path = RAW_DIR / "download_error.html"
        html_path.write_bytes(content)

        print("Saved HTML response to:", html_path)
        print("Response preview:")
        print(content[:500].decode("utf-8", errors="replace"))
        return

    file_hash = hashlib.sha256(content).hexdigest()
    file_path = RAW_DIR / f"{file_hash[:16]}.pdf"

    # Reuse an identical local file if it already exists.
    if not file_path.exists():
        file_path.write_bytes(content)
        print(f"Downloaded: {file_path.name}")
    else:
        print(f"Already downloaded: {file_path.name}")

    register_document(
        source_url=pdf_url,
        title=title,
        regulator="RBI",
        file_path=file_path,
        publication_date=None,
        effective_date=None
    )


def main():
    initialize_database()

    try:
        pdf_links = discover_pdf_links(RBI_INDEX)
    except requests.RequestException as error:
        print(f"Could not read RBI index: {error}")
        return

    print(f"PDF links found on index page: {len(pdf_links)}")

    for pdf_url, title in pdf_links:
        try:
            download_and_register(pdf_url, title)
        except requests.RequestException as error:
            print(f"Download failed: {pdf_url}")
            print(error)

        # Be considerate to the source website.
        time.sleep(1)

    print("Ingestion run finished.")


if __name__ == "__main__":
    main()
