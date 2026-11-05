
from pathlib import Path
from qdrant_client import QdrantClient

BASE_DIR = Path(__file__).resolve().parent
QDRANT_PATH = BASE_DIR / "data" / "qdrant"
COLLECTION_NAME = "regulatory_chunks"


def main():
    if not QDRANT_PATH.exists():
        print(f"Qdrant storage not found: {QDRANT_PATH}")
        return

    client = QdrantClient(path=str(QDRANT_PATH))

    try:
        print("=" * 55)
        print("READ-ONLY QDRANT INSPECTION")
        print("=" * 55)

        collections = client.get_collections().collections
        names = [collection.name for collection in collections]

        print(f"\nCollections found: {names}")

        if COLLECTION_NAME not in names:
            print(f"\nCollection '{COLLECTION_NAME}' not found.")
            return

        info = client.get_collection(COLLECTION_NAME)

        print(f"\nCollection: {COLLECTION_NAME}")
        print(f"Points count: {info.points_count}")
        print(f"Indexed vectors count: {info.indexed_vectors_count}")
        print(f"Status: {info.status}")
        print(f"Vector configuration: {info.config.params.vectors}")

        result, next_offset = client.scroll(
            collection_name=COLLECTION_NAME,
            limit=3,
            with_payload=True,
            with_vectors=False
        )

        print("\nSample indexed points:")
        for point in result:
            payload = point.payload or {}
            print("-" * 55)
            print(f"Point ID: {point.id}")
            print(f"Document ID: {payload.get('document_id')}")
            print(f"Version ID: {payload.get('version_id')}")
            print(f"Title: {payload.get('title')}")
            print(f"Page: {payload.get('page')}")
            print(f"Publication date: {payload.get('publication_date')}")
            print(f"URL: {payload.get('url')}")

        print("\nInspection completed. No points were changed.")

    finally:
        client.close()


if __name__ == "__main__":
    main()
