import argparse
import sqlite3
import uuid
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pymupdf
from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient, models

DB_PATH = "data/regulatory.db"
QDRANT_PATH = "data/qdrant"
COLLECTION = "regulatory_chunks"
MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"

CHUNK_SIZE = 650
CHUNK_OVERLAP = 100


def source_url_has_rbi_id(source_url, rbi_id):
    """Match the RBI ID as a query parameter, not as an arbitrary substring."""
    if not source_url:
        return False

    parsed = urlparse(source_url)
    query = parse_qs(parsed.query)

    for key, values in query.items():
        if key.lower() in {"id", "documentid", "docid"}:
            if str(rbi_id) in [str(value).strip() for value in values]:
                return True

    # Some RBI URLs may encode the ID in the path rather than the query.
    return parsed.path.rstrip("/").endswith(str(rbi_id))


def find_document_version(rbi_id):
    with sqlite3.connect(DB_PATH) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            """
            SELECT d.document_id, d.title, d.regulator, d.source_url,
                   v.version_id, v.version_number, v.file_path,
                   v.publication_date, v.effective_date
            FROM documents d
            JOIN document_versions v
              ON d.document_id = v.document_id
            ORDER BY d.document_id, v.version_number DESC
            """
        ).fetchall()

    matches = [row for row in rows
               if source_url_has_rbi_id(row["source_url"], rbi_id)]

    if not matches:
        raise SystemExit(
            f"RBI ID {rbi_id} was not found in SQLite. "
            "No Qdrant changes were made."
        )

    document_ids = {row["document_id"] for row in matches}
    if len(document_ids) != 1:
        raise SystemExit(
            f"Multiple SQLite documents match RBI ID {rbi_id}. "
            "No Qdrant changes were made."
        )

    # Use the latest registered version for the uniquely matched document.
    matches.sort(key=lambda row: row["version_number"], reverse=True)
    return matches[0]


def extract_chunks(pdf_path):
    chunks = []

    with pymupdf.open(str(pdf_path)) as pdf:
        for page_number, page in enumerate(pdf, start=1):
            page_text = page.get_text("text").strip()
            start = 0

            while start < len(page_text):
                chunk_text = page_text[start:start + CHUNK_SIZE].strip()

                if chunk_text:
                    chunks.append({
                        "text": chunk_text,
                        "page_number": page_number,
                        "chunk_index": len(chunks),
                    })

                if start + CHUNK_SIZE >= len(page_text):
                    break

                start += CHUNK_SIZE - CHUNK_OVERLAP

    return chunks


def count_version_points(client, document_id, version_id):
    result = client.count(
        collection_name=COLLECTION,
        count_filter=models.Filter(
            must=[
                models.FieldCondition(
                    key="document_id",
                    match=models.MatchValue(value=document_id),
                ),
                models.FieldCondition(
                    key="version_id",
                    match=models.MatchValue(value=version_id),
                ),
            ]
        ),
        exact=True,
    )
    return result.count


def main():
    parser = argparse.ArgumentParser(
        description="Index one registered RBI Master Direction version."
    )
    parser.add_argument(
        "rbi_id",
        help="RBI Master Direction ID, for example 13705",
    )
    args = parser.parse_args()
    rbi_id = str(args.rbi_id).strip()

    if not rbi_id.isdigit():
        raise SystemExit("RBI ID must contain digits only.")

    row = find_document_version(rbi_id)
    pdf_path = Path(row["file_path"])

    if not pdf_path.is_file():
        raise SystemExit(f"Registered PDF does not exist: {pdf_path}")

    with pdf_path.open("rb") as pdf_file:
        if pdf_file.read(5) != b"%PDF-":
            raise SystemExit(
                f"Registered file is not a valid PDF: {pdf_path}"
            )

    print(f"RBI Master Direction ID: {rbi_id}")
    print(f"Document: {row['title']}")
    print(f"SQLite document_id: {row['document_id']}")
    print(f"Version ID: {row['version_id']}")
    print(f"Version number: {row['version_number']}")
    print(f"PDF: {pdf_path}")
    print(f"Publication date: {row['publication_date']}")
    print(f"Effective date: {row['effective_date']}")

    chunks = extract_chunks(pdf_path)
    if not chunks:
        raise SystemExit(
            "No text extracted; Qdrant was not changed. "
            "The PDF may require OCR."
        )

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
        vector_config = info.config.params.vectors

        if isinstance(vector_config, dict):
            vector_sizes = {
                config.size for config in vector_config.values()
            }
            if model.get_embedding_dimension() not in vector_sizes:
                raise SystemExit(
                    "Embedding dimension mismatch; Qdrant was not changed."
                )
        elif vector_config.size != model.get_embedding_dimension():
            raise SystemExit(
                "Embedding dimension mismatch; Qdrant was not changed."
            )

        before_count = count_version_points(
            client, row["document_id"], row["version_id"]
        )
        print(f"Existing points for this version: {before_count}")

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

        # Deterministic IDs make retries idempotent. No delete is performed.
        client.upsert(
            collection_name=COLLECTION,
            points=points,
            wait=True,
        )

        after_count = count_version_points(
            client, row["document_id"], row["version_id"]
        )

        print(f"Upserted {len(points)} deterministic points.")
        print(f"Qdrant points for this document version: {after_count}")

        if after_count != len(points):
            raise SystemExit(
                "Verification mismatch. Stop and inspect Qdrant; "
                "no other document versions were targeted."
            )

        print(
            "SUCCESS: only this document version was indexed; "
            "no delete or bulk re-index was performed."
        )

    finally:
        client.close()


if __name__ == "__main__":
    main()
