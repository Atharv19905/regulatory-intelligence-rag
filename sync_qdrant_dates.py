
import sqlite3
from pathlib import Path
from collections import Counter

from qdrant_client import QdrantClient, models

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "data" / "regulatory.db"
QDRANT_PATH = BASE_DIR / "data" / "qdrant"
COLLECTION_NAME = "regulatory_chunks"

TARGET_DOCUMENT_IDS = [6, 7, 8, 9, 10]
EXPECTED_COUNTS = {
    6: 93,
    7: 188,
    8: 115,
    9: 59,
    10: 56,
}


def load_dates():
    conn = sqlite3.connect(DB_PATH)
    try:
        rows = conn.execute("""
            SELECT document_id, version_id,
                   publication_date, effective_date
            FROM document_versions
            WHERE document_id IN (6, 7, 8, 9, 10)
        """).fetchall()
    finally:
        conn.close()

    dates = {row[0]: row[1:] for row in rows}

    if set(dates) != set(TARGET_DOCUMENT_IDS):
        raise RuntimeError(
            f"Expected five documents, found: {sorted(dates)}"
        )

    return dates


def main():
    dates = load_dates()

    print("Verified SQLite dates:")
    for doc_id, values in sorted(dates.items()):
        print(f"Document {doc_id}: version={values[0]}, "
              f"publication={values[1]}, effective={values[2]}")

    client = QdrantClient(path=str(QDRANT_PATH))

    try:
        if not client.collection_exists(COLLECTION_NAME):
            raise RuntimeError("Qdrant collection not found.")

        before = client.count(
            collection_name=COLLECTION_NAME,
            exact=True
        ).count

        print(f"\nCollection points before update: {before}")

        if before != 592:
            raise RuntimeError(
                f"Expected 592 points; found {before}. "
                "No updates performed."
            )

        # Read and validate all target points before changing anything.
        target_points = {}
        for doc_id in TARGET_DOCUMENT_IDS:
            points, _ = client.scroll(
                collection_name=COLLECTION_NAME,
                scroll_filter=models.Filter(
                    must=[
                        models.FieldCondition(
                            key="document_id",
                            match=models.MatchValue(value=doc_id)
                        )
                    ]
                ),
                limit=1000,
                with_payload=True,
                with_vectors=False,
            )

            expected = EXPECTED_COUNTS[doc_id]
            if len(points) != expected:
                raise RuntimeError(
                    f"Document {doc_id}: expected {expected} points, "
                    f"found {len(points)}. No updates performed."
                )

            expected_version_id = dates[doc_id][0]
            if any(
                point.payload.get("version_id") != expected_version_id
                for point in points
            ):
                raise RuntimeError(
                    f"Unexpected version_id for document {doc_id}. "
                    "No updates performed."
                )

            target_points[doc_id] = points

        print("\nPre-update validation passed.")

        # Update only the two date fields.
        for doc_id, points in target_points.items():
            _, publication_date, effective_date = dates[doc_id]

            client.set_payload(
                collection_name=COLLECTION_NAME,
                payload={
                    "publication_date": publication_date,
                    "effective_date": effective_date,
                },
                points=[point.id for point in points],
                wait=True,
            )

            print(
                f"Updated document {doc_id}: "
                f"{len(points)} points"
            )

        # Read back and verify.
        verified = 0

        for doc_id, points in target_points.items():
            _, publication_date, effective_date = dates[doc_id]

            readback, _ = client.scroll(
                collection_name=COLLECTION_NAME,
                scroll_filter=models.Filter(
                    must=[
                        models.FieldCondition(
                            key="document_id",
                            match=models.MatchValue(value=doc_id)
                        )
                    ]
                ),
                limit=1000,
                with_payload=True,
                with_vectors=False,
            )

            for point in readback:
                payload = point.payload or {}

                if payload.get("publication_date") != publication_date:
                    raise RuntimeError(
                        f"Publication date mismatch: {point.id}"
                    )

                if payload.get("effective_date") != effective_date:
                    raise RuntimeError(
                        f"Effective date mismatch: {point.id}"
                    )

                verified += 1

        after = client.count(
            collection_name=COLLECTION_NAME,
            exact=True
        ).count

        if after != before:
            raise RuntimeError(
                f"Point count changed: {before} -> {after}"
            )

        print("\n" + "=" * 55)
        print("QDRANT DATE SYNCHRONIZATION SUCCESSFUL")
        print("=" * 55)
        print(f"Points updated and verified: {verified}")
        print(f"Collection points before: {before}")
        print(f"Collection points after:  {after}")
        print("Vectors regenerated: No")
        print("Points deleted: No")
        print("Other payload fields modified: No")

    finally:
        client.close()


if __name__ == "__main__":
    main()
