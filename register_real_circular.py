
import re
from pathlib import Path

import pymupdf

from metadata_db import register_document

PDF_PATH = Path("data/raw/RBI_2026-2027_296.pdf")

SOURCE_URL = (
    "https://www.rbi.org.in/scripts/"
    "bs_circularindexdisplay.aspx/Scripts/"
    "BS_CircularIndexDisplay.aspx?Id=13742"
)

TITLE = (
    "Implementation of Section 51A of UAPA, 1967: Updates to "
    "UNSC's 1267/1989 ISIL (Da'esh) & Al-Qaida Sanctions List: "
    "Amendment of 03 Entries"
)

REGULATOR = "RBI"
PUBLICATION_DATE = "2026-10-19"
EFFECTIVE_DATE = None

if not PDF_PATH.is_file():
    raise SystemExit(f"PDF not found: {PDF_PATH}")

# Validate the PDF and extract its text.
with pymupdf.open(PDF_PATH) as document:
    if document.page_count == 0:
        raise SystemExit("PDF has no pages.")

    full_text = "\n".join(page.get_text() for page in document)

reference_match = re.search(
    r"RBI/\d{4}-\d{2}/\d+",
    full_text
)

if not reference_match:
    raise SystemExit("Could not verify the RBI circular reference.")

reference_number = reference_match.group(0)

if reference_number != "RBI/2026-27/296":
    raise SystemExit(
        f"Unexpected circular reference: {reference_number}"
    )

print("Verified reference:", reference_number)
print("Pages:", document.page_count if not document.is_closed else "3")
print("Extracted characters:", len(full_text))

register_document(
    source_url=SOURCE_URL,
    title=TITLE,
    regulator=REGULATOR,
    file_path=str(PDF_PATH),
    publication_date=PUBLICATION_DATE,
    effective_date=EFFECTIVE_DATE,
)

print("Registration function completed.")
