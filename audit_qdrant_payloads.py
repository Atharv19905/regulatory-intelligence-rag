"""Read-only audit of Qdrant payload fields used by index_circular.py."""
from collections import Counter
from pathlib import Path
from qdrant_client import QdrantClient

BASE_DIR = Path(__file__).resolve().parent
QDRANT_PATH = BASE_DIR / "data" / "qdrant"
COLLECTION_NAME = "regulatory_chunks"

# Keep these names aligned with the payload written by index_circular.py.
REQUIRED_FIELDS = [
    "document_id",
    "version_id",
    "version_number",
    "title",
    "regulator",
    "source_url",
    "publication_date",
    "effective_date",
    "page_number",
    "chunk_index",
    "text",
]


def main():
    if not QDRANT_PATH.exists():
        raise SystemExit(f"Qdrant storage not found: {QDRANT_PATH}")

    client = QdrantClient(path=str(QDRANT_PATH))
    try:
        if not client.collection_exists(COLLECTION_NAME):
            raise SystemExit(f"Collection not found: {COLLECTION_NAME}")

        total = 0
        document_counts = Counter()
        missing_counts = Counter()
        payload_keys = Counter()
        examples = []
        offset = None

        while True:
            points, next_offset = client.scroll(
                collection_name=COLLECTION_NAME,
                limit=100,
                offset=offset,
                with_payload=True,
                with_vectors=False,
            )
            for point in points:
                total += 1
                payload = point.payload or {}
                document_counts[str(payload.get("document_id", "MISSING"))] += 1
                payload_keys.update(payload.keys())

                for field in REQUIRED_FIELDS:
                    value = payload.get(field)
                    if value is None or value == "":
                        missing_counts[field] += 1

                if len(examples) < 5:
                    examples.append((point.id, payload))

            if next_offset is None:
                break
            offset = next_offset

        print("=" * 60)
        print("QDRANT PAYLOAD AUDIT — READ ONLY")
        print("=" * 60)
        print(f"\nTotal points inspected: {total}")
        print("\nPoints by document ID:")
        for document_id, count in sorted(document_counts.items()):
            print(f"- Document {document_id}: {count} points")

        print("\nPayload field coverage:")
        for field in REQUIRED_FIELDS:
            present = total - missing_counts[field]
            print(f"- {field}: {present}/{total} present")

        print("\nAll payload keys found:")
        for key, count in sorted(payload_keys.items()):
            print(f"- {key}: {count}/{total} points")

        print("\nFive sample payloads:")
        for point_id, payload in examples:
            print("-" * 60)
            print(f"Point ID: {point_id}")
            for key, value in payload.items():
                if key == "text" and isinstance(value, str):
                    value = value[:150].replace("\n", " ")
                print(f"{key}: {value}")

        print("\nAudit completed. No points were changed.")
    finally:
        client.close()


if __name__ == "__main__":
    main()
