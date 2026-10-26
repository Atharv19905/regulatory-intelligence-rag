
from pathlib import Path
import pymupdf

BASE_DIR = Path(__file__).resolve().parent
PDF_PATH = BASE_DIR / "data" / "raw" / "RBI_2026-2027_296.pdf"

if not PDF_PATH.exists():
    raise SystemExit(f"PDF not found: {PDF_PATH}")

with pymupdf.open(PDF_PATH) as document:
    for page_number, page in enumerate(document, start=1):
        print(f"\n{'=' * 60}")
        print(f"PAGE {page_number}")
        print("=" * 60)

        # Inspect text spans and font metadata.
        page_data = page.get_text("dict")

        for block in page_data.get("blocks", []):
            if block.get("type") != 0:
                continue

            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    text = span.get("text", "").strip()

                    if not text:
                        continue

                    print(
                        f"TEXT: {text[:160]!r}\n"
                        f"  Font: {span.get('font')}\n"
                        f"  Flags: {span.get('flags')}\n"
                        f"  Size: {span.get('size')}\n"
                        f"  Box: {span.get('bbox')}\n"
                    )

        # Inspect drawn lines and shapes that might indicate
        # underlining or strikethrough.
        drawings = page.get_drawings()
        print(f"\nDrawing objects found: {len(drawings)}")

        for drawing_number, drawing in enumerate(drawings, start=1):
            rect = drawing.get("rect")
            items = drawing.get("items", [])

            print(
                f"\nDrawing {drawing_number}: "
                f"box={rect}, "
                f"color={drawing.get('color')}, "
                f"fill={drawing.get('fill')}"
            )

            for item in items:
                if item[0] == "l":
                    start, end = item[1], item[2]
                    print(f"  Line: {start} -> {end}")

                elif item[0] == "re":
                    print(f"  Rectangle: {item[1]}")

print("\nFormatting inspection finished.")
