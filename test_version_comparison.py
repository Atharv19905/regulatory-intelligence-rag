
import sqlite3
import tempfile
import unittest
from pathlib import Path
from record_change_event import validate_sfb_comparison_report
from compare_versions import compare_texts, get_versions,compare_pages
import pytest


class VersionComparisonTests(unittest.TestCase):

    def test_detects_added_text(self):
        result = compare_texts(
            "The repo rate is 5.25%.",
            "The repo rate is 5.25%.\nThe new rule takes effect immediately."
        )

        self.assertTrue(result["added"])
        self.assertFalse(result["identical"])

    def test_detects_removed_text(self):
        result = compare_texts(
            "The repo rate is 5.25%.\nThe stance remains neutral.",
            "The repo rate is 5.25%."
        )

        self.assertTrue(result["removed"])
        self.assertFalse(result["identical"])

    def test_detects_modified_text(self):
        result = compare_texts(
            "The repo rate is 5.25%.",
            "The repo rate is 5.50%."
        )

        self.assertTrue(result["modified"])
        self.assertFalse(result["identical"])

    def test_identical_text(self):
        text = "The repo rate is 5.25%."

        result = compare_texts(text, text)

        self.assertTrue(result["identical"])
        self.assertFalse(result["added"])
        self.assertFalse(result["removed"])
        self.assertFalse(result["modified"])

    def test_get_versions_reads_database_without_modifying_it(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "test_regulatory.db"

            connection = sqlite3.connect(db_path)

            connection.execute("""
                CREATE TABLE documents (
                    document_id INTEGER PRIMARY KEY,
                    source_url TEXT NOT NULL,
                    title TEXT,
                    regulator TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """)

            connection.execute("""
                CREATE TABLE document_versions (
                    version_id INTEGER PRIMARY KEY,
                    document_id INTEGER NOT NULL,
                    version_number INTEGER NOT NULL,
                    file_path TEXT NOT NULL,
                    sha256 TEXT NOT NULL,
                    publication_date TEXT,
                    effective_date TEXT,
                    retrieved_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """)

            connection.execute("""
                INSERT INTO documents
                (document_id, source_url, title, regulator)
                VALUES (1, 'https://example.com/rbi', 'Test Direction', 'RBI')
            """)

            connection.executemany("""
                INSERT INTO document_versions
                (version_id, document_id, version_number, file_path,
                 sha256, publication_date, effective_date)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, [
                (1, 1, 1, "old.pdf", "hash_old",
                 "2025-01-01", "2025-01-02"),
                (2, 1, 2, "new.pdf", "hash_new",
                 "2025-02-01", "2025-02-02")
            ])

            connection.commit()
            connection.close()

            versions = get_versions(1, db_path=db_path)

            self.assertEqual(len(versions), 2)
            self.assertEqual(versions[0]["version_number"], 1)
            self.assertEqual(versions[1]["version_number"], 2)
            self.assertEqual(versions[0]["sha256"], "hash_old")
            self.assertEqual(versions[1]["sha256"], "hash_new")

    def test_compare_pages_preserves_page_numbers(self):
        old_pages = [
            {"page_number": 1, "text": "Introduction\nOld regulation"},
            {"page_number": 2, "text": "Existing paragraph"},
        ]

        new_pages = [
            {"page_number": 1, "text": "New introduction"},
            {"page_number": 2, "text": "Introduction\nOld regulation"},
            {"page_number": 3, "text": "Existing paragraph"},
        ]

        result = compare_pages(old_pages, new_pages)

        self.assertTrue(result["added"])
        self.assertTrue(
            all("page_number" in item for item in result["added"])
        )


    def test_compare_pages_identical_content(self):
        pages = [
            {"page_number": 1, "text": "Regulation introduction"},
            {"page_number": 2, "text": "Paragraph 37"},
        ]

        result = compare_pages(pages, pages)

        self.assertTrue(result["identical"])
        self.assertEqual(result["added"], [])
        self.assertEqual(result["removed"], [])
        self.assertEqual(result["modified"], [])

    

    def test_unverified_sfb_history_blocks_event_recording(self):
        report = {
            "status": "candidate_deletion",
            "amendment_confirms_deletion": True,
            "historical_source_status": "secondary_source_unverified",
        }

        with pytest.raises(ValueError, match="Historical wording is unverified"):
            validate_sfb_comparison_report(report)


if __name__ == "__main__":
    unittest.main()
