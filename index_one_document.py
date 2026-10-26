
import sqlite3
import uuid
from pathlib import Path

import pymupdf
from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient, models

DB_PATH = "data/regulatory.db"
QDRANT_PATH = "data/qdrant"
COLLECTION = "regulatory_chunks"
MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"

TARGET_URL = (
    "https://www.rbi.org.in/scripts/"
    "bs_circularindexdisplay.aspx/Scripts/"
    "BS_CircularIndexDisplay.aspx?Id=13740"
)

CHUNK_SIZE = 650
CHUNK_OVERLAP = 100


def main():
    # Find only the target document version.
    with sqlite3.connect(DB_PATH) as connection:
        connection.row_factory = sqlite3.Row
        row = connection.execute(
            """
            SELECT d.document_id, d.title, d.regulator,
                   d.source_url, v.version_id, v.version_number,
                   v.file_path, v.publication_date, v.effective_date
            FROM documents d
            JOIN document_versions v
              ON d.document_id = v.document_id
            WHERE d.source_url = ?
            ORDER BY v.version_number DESC
            LIMIT 1
            """,
            (TARGET_URL,),
        ).fetchone()

    if row is None:
        raise SystemExit("Target document was not found in SQLite.")

    pdf_path = Path(row["file_path"])
    if not pdf_path.is_file():
        raise SystemExit(f"PDF not found: {pdf_path}")

    print(f"Document: {row['title']}")
    print(f"Document ID: {row['document_id']}")
    print(f"Version ID: {row['version_id']}")
    print(f"PDF: {pdf_path}")

    chunks = []
    with pymupdf.open(str(pdf_path)) as pdf:
        for page_number, page in enumerate(pdf, start=1):
            page_text = page.get_text("text").strip()
            start = 0

            while start < len(page_text):
                chunk_text = page_text[
                    start:start + CHUNK_SIZE
                ].strip()

                if chunk_text:
                    chunks.append({
                        "text": chunk_text,
                        "page_number": page_number,
                        "chunk_index": len(chunks),
                    })

                if start + CHUNK_SIZE >= len(page_text):
                    break
                start += CHUNK_SIZE - CHUNK_OVERLAP

    if not chunks:
        raise SystemExit("No text extracted; Qdrant was not changed.")

    print(f"Extracted {len(chunks)} chunks.")
    print("Loading embedding model...")
    model = SentenceTransformer(MODEL_NAME)

    client = QdrantClient(path=QDRANT_PATH)
    try:
        if not client.collection_exists(COLLECTION):
            raise SystemExit(
                f"Qdrant collection '{COLLECTION}' does not exist."
            )

        info = client.get_collection(COLLECTION)
        if info.config.params.vectors.size != model.get_embedding_dimension():
            raise SystemExit("Embedding dimension mismatch; stopped.")

        embeddings = model.encode(
            [chunk["text"] for chunk in chunks],
            show_progress_bar=True,
            normalize_embeddings=True,
        )

        points = []
        for i, chunk in enumerate(chunks):
            key = (
                f"{row['document_id']}:{row['version_id']}:"
                f"{chunk['page_number']}:{chunk['chunk_index']}"
            )
            points.append(models.PointStruct(
                id=str(uuid.uuid5(uuid.NAMESPACE_URL, key)),
                vector=embeddings[i].tolist(),
                payload={
                    "document_id": row["document_id"],
                    "version_id": row["version_id"],
                    "version_number": row["version_number"],
                    "title": row["title"],
                    "regulator": row["regulator"],
                    "source_url": row["source_url"],
                    "publication_date": row["publication_date"],
                    "effective_date": row["effective_date"],
                    "page_number": chunk["page_number"],
                    "chunk_index": chunk["chunk_index"],
                    "text": chunk["text"],
                },
            ))

        # Replace only this document version's points.
        client.delete(
            collection_name=COLLECTION,
            points_selector=models.FilterSelector(
                filter=models.Filter(
                    must=[
                        models.FieldCondition(
                            key="document_id",
                            match=models.MatchValue(
                                value=row["document_id"]
                            ),
                        ),
                        models.FieldCondition(
                            key="version_id",
                            match=models.MatchValue(
                                value=row["version_id"]
                            ),
                        ),
                    ],
                ),
            ),
            wait=True,
        )

        client.upsert(
            collection_name=COLLECTION,
            points=points,
            wait=True,
        )

        print(f"Indexed {len(points)} chunks for this version.")
        print("Other document/version points were not targeted.")

    finally:
        client.close()


if __name__ == "__main__":
    main()
