
from pathlib import Path
import pymupdf

BASE_DIR = Path(__file__).resolve().parent
PDF_PATH = BASE_DIR / "data" / "raw" / "RBI_2026-2027_296.pdf"
OUTPUT_DIR = BASE_DIR / "data" / "extracted" / "page_images"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

with pymupdf.open(PDF_PATH) as document:
    for page_index in range(min(3, len(document))):
        page = document[page_index]

        pixmap = page.get_pixmap(
            matrix=pymupdf.Matrix(2, 2),
            alpha=False
        )

        output_path = OUTPUT_DIR / f"page_{page_index + 1}.png"
        pixmap.save(output_path)

        print(f"Saved: {output_path}")

print("Rendering finished.")
