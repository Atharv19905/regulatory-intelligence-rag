
import sqlite3
import uuid
from pathlib import Path

import pymupdf
from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient, models

DB_PATH = "data/regulatory.db"
QDRANT_PATH = "data/qdrant"
COLLECTION_NAME = "regulatory_chunks"
MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"

CHUNK_SIZE = 650
CHUNK_OVERLAP = 100


# 1. Read all registered document versions from SQLite
with sqlite3.connect(DB_PATH) as connection:
    connection.row_factory = sqlite3.Row

    rows = connection.execute("""
        SELECT
            d.document_id,
            d.title,
            d.regulator,
            d.source_url,
            v.version_id,
            v.version_number,
            v.file_path,
            v.publication_date,
            v.effective_date
        FROM documents AS d
        JOIN document_versions AS v
            ON d.document_id = v.document_id
        ORDER BY d.document_id, v.version_number
    """).fetchall()

if not rows:
    raise SystemExit(
        "No registered document versions found in the database."
    )

print(f"Found {len(rows)} registered document version(s).")


# 2. Load the embedding model
print("Loading embedding model; the first run may take time...")
model = SentenceTransformer(MODEL_NAME)

# 3. Open or create the local Qdrant collection
client = QdrantClient(path=QDRANT_PATH)

if not client.collection_exists(COLLECTION_NAME):
    client.create_collection(
        collection_name=COLLECTION_NAME,
        vectors_config=models.VectorParams(
            size=model.get_embedding_dimension(),
            distance=models.Distance.COSINE
        )
    )
    print(f"Created collection: {COLLECTION_NAME}")
else:
    print(f"Using existing collection: {COLLECTION_NAME}")


# 4. Process each registered version separately
total_indexed = 0

try:
    for row in rows:
        document_id = row["document_id"]
        version_id = row["version_id"]
        pdf_path = Path(row["file_path"])

        print(
            f"\nProcessing: {row['title']}\n"
            f"Document ID: {document_id} | "
            f"Version: {row['version_number']}"
        )

        if not pdf_path.is_file():
            print(f"Skipping: PDF not found at {pdf_path}")
            continue

        chunks = []

        # Extract and chunk text page by page
        with pymupdf.open(str(pdf_path)) as pdf:
            for page_number, page in enumerate(pdf, start=1):
                text = page.get_text("text").strip()
                start = 0

                while start < len(text):
                    chunk_text = text[
                        start:start + CHUNK_SIZE
                    ].strip()

                    if chunk_text:
                        chunks.append({
                            "text": chunk_text,
                            "page_number": page_number,
                            "chunk_index": len(chunks)
                        })

                    if start + CHUNK_SIZE >= len(text):
                        break

                    start += CHUNK_SIZE - CHUNK_OVERLAP

        if not chunks:
            print("Skipping: no text extracted from this PDF.")
            continue

        print(f"Extracted {len(chunks)} text chunks.")

        # Generate embeddings for this version
        embeddings = model.encode(
            [chunk["text"] for chunk in chunks],
            show_progress_bar=True,
            normalize_embeddings=True
        )

        points = []

        for i, chunk in enumerate(chunks):
            # Stable IDs prevent duplicate points when re-running.
            unique_key = (
                f"{document_id}:{version_id}:"
                f"{chunk['page_number']}:{chunk['chunk_index']}"
            )

            point_id = str(
                uuid.uuid5(uuid.NAMESPACE_URL, unique_key)
            )

            points.append(
                models.PointStruct(
                    id=point_id,
                    vector=embeddings[i].tolist(),
                    payload={
                        "document_id": document_id,
                        "version_id": version_id,
                        "version_number": row["version_number"],
                        "title": row["title"],
                        "regulator": row["regulator"],
                        "source_url": row["source_url"],
                        "publication_date": row["publication_date"],
                        "effective_date": row["effective_date"],
                        "page_number": chunk["page_number"],
                        "chunk_index": chunk["chunk_index"],
                        "text": chunk["text"]
                    }
                )
            )

        # Delete only this document version's old chunks.
        # Other documents and versions remain untouched.
        client.delete(
            collection_name=COLLECTION_NAME,
            points_selector=models.FilterSelector(
                filter=models.Filter(
                    must=[
                        models.FieldCondition(
                            key="document_id",
                            match=models.MatchValue(
                                value=document_id
                            )
                        ),
                        models.FieldCondition(
                            key="version_id",
                            match=models.MatchValue(
                                value=version_id
                            )
                        )
                    ]
                )
            ),
            wait=True
        )

        # Insert the refreshed chunks for this version
        client.upsert(
            collection_name=COLLECTION_NAME,
            points=points,
            wait=True
        )

        total_indexed += len(points)

        print(f"Indexed {len(points)} chunks successfully.")

    print("\nIndexing finished.")
    print(f"Chunks indexed during this run: {total_indexed}")
    print(f"Collection: {COLLECTION_NAME}")
    print(f"Local Qdrant path: {QDRANT_PATH}")

finally:
    client.close()
