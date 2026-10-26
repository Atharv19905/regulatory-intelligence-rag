
import fitz
from pathlib import Path

# Folder containing original PDF documents
input_folder = Path("data/raw")

# Folder for extracted text
output_folder = Path("data/extracted")
output_folder.mkdir(parents=True, exist_ok=True)

pdf_files = list(input_folder.glob("*.pdf"))

if not pdf_files:
    print("No PDF files found in data/raw.")
    print("Please add at least one regulatory PDF.")
else:
    for pdf_file in pdf_files:
        print(f"\nProcessing: {pdf_file.name}")

        try:
            document = fitz.open(pdf_file)
            extracted_pages = []

            for page_number, page in enumerate(document, start=1):
                page_text = page.get_text("text")

                extracted_pages.append(
                    f"\n--- Page {page_number} ---\n{page_text}"
                )

            output_file = output_folder / f"{pdf_file.stem}.txt"
            output_file.write_text(
                "\n".join(extracted_pages),
                encoding="utf-8"
            )

            print(f"Pages extracted: {len(document)}")
            print(f"Text saved to: {output_file}")

            document.close()

        except Exception as error:
            print(f"Failed to process {pdf_file.name}: {error}")

    print("\nPDF extraction finished.")
