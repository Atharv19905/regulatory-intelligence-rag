
import json
import time
from pathlib import Path

import requests

QUEUE_FILE = Path("data/versions/discovered_regulations.json")
RAW_DIR = Path("data/raw")
RAW_DIR.mkdir(parents=True, exist_ok=True)

with QUEUE_FILE.open("r", encoding="utf-8") as file:
    records = json.load(file)

# Pick the first discovered circular with a PDF URL.
record = next(
    (item for item in records if item.get("pdf_urls")),
    None
)

if not record:
    raise SystemExit("No circular PDF URLs found in the queue.")

pdf_url = record["pdf_urls"][0]
reference = record.get("reference_number", "unknown")
safe_reference = "".join(
    char if char.isalnum() or char in "-_" else "_"
    for char in reference
)
output_file = RAW_DIR / f"{safe_reference}.pdf"

print("Circular:", reference)
print("Downloading from:", pdf_url)

headers = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "application/pdf,*/*",
}

try:
    response = requests.get(
        pdf_url,
        headers=headers,
        timeout=45,
    )
    print("HTTP status:", response.status_code)
    print("Content-Type:", response.headers.get("Content-Type"))
    response.raise_for_status()

    content = response.content

    # A PDF normally begins with the %PDF- signature.
    if not content.startswith(b"%PDF-"):
        print("The response is not a PDF.")
        print("Response preview:", content[:200].decode("utf-8", errors="replace"))
        raise SystemExit(
            "Download stopped safely. No HTML or verification page was saved as a PDF."
        )

    # Basic integrity check using PyMuPDF.
    import fitz

    with fitz.open(stream=content, filetype="pdf") as document:
        print("PDF pages:", len(document))
        if len(document) == 0:
            raise SystemExit("PDF has no pages.")

    output_file.write_bytes(content)
    print("Saved valid PDF to:", output_file)

except requests.RequestException as error:
    print("Download request failed:", error)
    raise SystemExit(1)
