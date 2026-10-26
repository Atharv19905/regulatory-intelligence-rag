

import importlib

import sqlite3

import unittest

import tempfile

from pathlib import Path

from unittest.mock import patch





class RegulatoryRAGTests(unittest.TestCase):



    @classmethod

    def setUpClass(cls):

        cls.app = importlib.import_module("search_circular")



    def setUp(self):

        self.temp_dir = tempfile.TemporaryDirectory()

        self.temp_path = Path(self.temp_dir.name)

        self.temp_db = self.temp_path / "test.db"

        self.temp_pdf = self.temp_path / "test.pdf"



        # Create a temporary two-page PDF for citation validation.



        # Create a temporary two-page PDF with real test text.

        pdf = self.app.pymupdf.open()



        page1 = pdf.new_page()

        page1.insert_text(

            (72, 72),

            "The repo rate was 5.50 per cent."

        )



        page2 = pdf.new_page()

        page2.insert_text(

            (72, 72),

            "This is a second page for page-range testing."

        )



        pdf.save(self.temp_pdf)

        pdf.close()





        # Create a temporary database with the required schema.

        connection = sqlite3.connect(self.temp_db)

        try:

            connection.execute("""

                CREATE TABLE documents (

                    document_id INTEGER PRIMARY KEY,

                    title TEXT,

                    source_url TEXT

                )

            """)



            connection.execute("""



                CREATE TABLE document_versions (

                    version_id INTEGER PRIMARY KEY,

                    document_id INTEGER,

                    version_number INTEGER,

                    publication_date TEXT,

                    file_path TEXT

                )

            """)



            connection.executemany(

                "INSERT INTO documents VALUES (?, ?, ?)",

                [

                    (

                        1,

                        "MPC Meeting Minutes",

                        "https://rbi.org.in/test-mpc",

                    ),

                    (

                        2,

                        "Sanctions Circular",

                        "https://rbi.org.in/test-sanctions",

                    ),

                    (

                        3,

                        "Future Circular",

                        "https://rbi.org.in/test-future",

                    ),

                ],

            )



            connection.executemany(

                "INSERT INTO document_versions VALUES (?, ?, ?, ?,?)",

                [

                    (1, 1, 1, "2026-10-21", str(self.temp_pdf)),

                    (2, 2, 1, "2026-10-19", str(self.temp_pdf)),

                    (3, 3, 1, "2026-10-25", str(self.temp_pdf)),

                ],

            )



            connection.commit()

        finally:

            connection.close()



    def tearDown(self):

        self.temp_dir.cleanup()



    def validate(self, candidates, as_of_date=None):

        # Patch paths so tests never touch the real project database.

        with (

            patch.object(self.app, "DB_PATH", self.temp_db),

            patch.object(self.app, "BASE_DIR", self.temp_path),

        ):

            return self.app.validate_candidate_citations(

                candidates,

                as_of_date=as_of_date,

            )



    def make_candidate(

        self,

        document_id=1,

        version_number=1,

        page_number=1,

    ):

        return {

            "payload": {

                "document_id": document_id,

                "version_number": version_number,

                "page_number": page_number,

                "text": "The repo rate was 5.50 per cent.",

            },

            "score": 0.95,

        }



    # Existing test 1

    def test_cutoff_before_mpc_publication_excludes_mpc_document(self):

        with patch.object(self.app, "DB_PATH", self.temp_db):

            ids = self.app.get_eligible_document_ids("2026-10-20")



        self.assertIn(2, ids)

        self.assertNotIn(1, ids)

        self.assertNotIn(3, ids)



    # Existing test 2

    def test_cutoff_on_publication_date_includes_mpc_document(self):

        with patch.object(self.app, "DB_PATH", self.temp_db):

            ids = self.app.get_eligible_document_ids("2026-10-21")



        self.assertIn(1, ids)



    # Existing test 3

    def test_topic_filter_accepts_mpc_passage(self):

        payload = {

            "title": "Minutes of the Monetary Policy Committee Meeting",

            "text": "The policy repo rate was increased to 5.50 per cent.",

        }



        self.assertTrue(

            self.app.topic_relevant(

                "What was the RBI repo rate according to the October 2026 MPC minutes?",

                payload,

            )

        )



    # Existing test 4

    def test_topic_filter_rejects_unrelated_sanctions_passage(self):

        payload = {

            "title": "Amendment of 03 Entries",

            "text": "The sanctions list entry address was amended.",

        }



        self.assertFalse(

            self.app.topic_relevant(

                "What was the RBI repo rate according to the October 2026 MPC minutes?",

                payload,

            )

        )



    # Existing test 5

    def test_citation_metadata_is_complete_for_retrieved_passage(self):

        payload = {

            "title": "Minutes of the Monetary Policy Committee Meeting, October 5 to 7, 2026",

            "publication_date": "2026-10-21",

            "page_number": 2,

            "source_url": "https://rbi.org.in/scripts/BS_PressReleaseDisplay.aspx?prid=63839",

            "text": "The MPC voted unanimously to increase the policy repo rate by 25 bps to 5.50 per cent.",

        }



        self.assertTrue(payload["title"].strip())

        self.assertEqual(payload["publication_date"], "2026-10-21")

        self.assertGreaterEqual(payload["page_number"], 1)

        self.assertTrue(payload["source_url"].startswith("https://"))

        self.assertIn("5.50", payload["text"])



    # Existing test 6

    def test_cutoff_validation_rejects_invalid_date(self):

        from datetime import date



        with self.assertRaises(ValueError):

            date.fromisoformat("22-10-2026")



    # New test 7

    def test_citation_validator_accepts_valid_candidate(self):

        candidate = self.make_candidate()



        result = self.validate(

            [candidate],

            as_of_date="2026-10-22",

        )



        self.assertEqual(len(result), 1)

        payload = result[0]["payload"]

        self.assertEqual(payload["document_id"], 1)

        self.assertEqual(payload["version_number"], 1)

        self.assertEqual(payload["page_number"], 1)

        self.assertEqual(payload["publication_date"], "2026-10-21")

        self.assertEqual(

            payload["source_url"],

            "https://rbi.org.in/test-mpc",

        )



    # New test 8

    def test_citation_validator_rejects_unknown_document_or_version(self):

        candidates = [

            self.make_candidate(document_id=999),

            self.make_candidate(version_number=99),

        ]



        result = self.validate(

            candidates,

            as_of_date="2026-10-22",

        )



        self.assertEqual(result, [])



    # New test 9

    def test_citation_validator_rejects_invalid_page_numbers(self):

        candidates = [

            self.make_candidate(page_number=0),

            self.make_candidate(page_number=3),

        ]



        result = self.validate(

            candidates,

            as_of_date="2026-10-22",

        )



        self.assertEqual(result, [])



    # New test 10

    def test_citation_validator_rejects_document_after_cutoff(self):

        candidate = self.make_candidate(document_id=3)



        result = self.validate(

            [candidate],

            as_of_date="2026-10-22",

        )



        self.assertEqual(result, [])





    def test_passage_verification_accepts_matching_text(self):

        passage = (

            "The MPC voted unanimously to increase the policy repo "

            "rate to 5.50 per cent."

        )

        page_text = (

            "Minutes of the meeting.\n\n"

            "The MPC voted unanimously to increase the policy repo "

            "rate to 5.50 per cent.\n\n"

            "Growth and Inflation Outlook."

        )



        self.assertTrue(

            self.app.passage_exists_on_page(passage, page_text)

        )





    def test_passage_verification_handles_line_breaks(self):

        passage = "policy repo rate to 5.50 per cent"

        page_text = "policy repo rate to 5.50\nper cent"



        self.assertTrue(

            self.app.passage_exists_on_page(passage, page_text)

        )





    def test_passage_verification_rejects_wrong_page(self):

        passage = "The policy repo rate was increased to 5.50 per cent."

        wrong_page_text = (

            "The sanctions list entry address was amended."

        )



        self.assertFalse(

            self.app.passage_exists_on_page(passage, wrong_page_text)

        )





    def test_passage_verification_rejects_empty_passage(self):

        self.assertFalse(

            self.app.passage_exists_on_page("", "Some PDF page text.")

        )





    @patch("search_circular.check_answer_grounding")

    def test_grounding_accepts_supported_answer(self, mock_check):

        mock_check.return_value = "SUPPORTED"



        from search_circular import display_answer_if_supported



        with patch("builtins.print") as mock_print:

            result = display_answer_if_supported(

                "What was the repo rate?",

                "The repo rate was 5.50%.",

                "The policy repo rate was increased to 5.50%.",

                "Test",

            )



        self.assertTrue(result)

        mock_print.assert_any_call("The repo rate was 5.50%.")



    @patch("search_circular.check_answer_grounding")

    def test_grounding_rejects_unsupported_answer(self, mock_check):

        mock_check.return_value = "UNSUPPORTED"



        from search_circular import display_answer_if_supported



        with patch("builtins.print") as mock_print:

            result = display_answer_if_supported(

                "What was the repo rate?",

                "The repo rate was 7.00%.",

                "The policy repo rate was increased to 5.50%.",

                "Test",

            )



        self.assertFalse(result)

        mock_print.assert_any_call(

            "The answer was blocked because its claims could not "

            "all be verified against the supplied evidence."

        )



    @patch("search_circular.check_answer_grounding")

    def test_grounding_rejects_uncertain_answer(self, mock_check):

        mock_check.return_value = "UNCERTAIN"



        from search_circular import display_answer_if_supported



        with patch("builtins.print") as mock_print:

            result = display_answer_if_supported(

                "What was the repo rate?",

                "The repo rate was 5.50%.",

                "",

                "Test",

            )



        self.assertFalse(result)







    def test_version_eligibility_excludes_future_version_of_same_document(self):

        connection = sqlite3.connect(self.temp_db)

        try:

            connection.execute(

                """

                INSERT INTO document_versions

                VALUES (?, ?, ?, ?, ?)

                """,

                (4, 1, 2, "2026-10-25", str(self.temp_pdf)),

            )

            connection.commit()

        finally:

            connection.close()



        with patch.object(self.app, "DB_PATH", self.temp_db):

            ids = self.app.get_eligible_version_ids("2026-10-22")



        self.assertIn(1, ids)

        self.assertNotIn(4, ids)





    @patch("search_circular.generate_answer")

    @patch("search_circular.get_relevant_change_events", return_value=[])

    @patch("search_circular.find_future_topic_documents", return_value=[])

    @patch("search_circular.validate_candidate_citations", return_value=[])

    @patch("search_circular.get_eligible_version_ids", return_value=[1, 2])

    @patch("search_circular.QdrantClient")

    @patch("search_circular.SentenceTransformer")

    def test_semantic_search_passes_eligible_versions_to_qdrant(

        self,

        mock_sentence_transformer,

        mock_qdrant_client,

        mock_eligible_versions,

        mock_validate,

        mock_future_documents,

        mock_change_events,

        mock_generate_answer,

    ):

        # Mock embedding generation.

        mock_model = mock_sentence_transformer.return_value

        mock_model.encode.return_value.tolist.return_value = [0.1, 0.2]



        # Mock Qdrant returning no passages.

        mock_client = mock_qdrant_client.return_value

        mock_client.query_points.return_value.points = []



        with patch.object(self.app, "DB_PATH", self.temp_db):

            self.app.semantic_search(

                "What was the repo rate?",

                circular=None,

                as_of_date="2026-10-22",

            )



        mock_eligible_versions.assert_called_once_with("2026-10-22")

        mock_client.query_points.assert_called_once()



        query_kwargs = mock_client.query_points.call_args.kwargs

        query_filter = query_kwargs["query_filter"]



        # Verify that the filter restricts retrieval by version_id.

        self.assertIsNotNone(query_filter)

        self.assertEqual(len(query_filter.must), 1)



        condition = query_filter.must[0]

        self.assertEqual(condition.key, "version_id")

        self.assertEqual(condition.match.any, [1, 2])



    @patch("search_circular.generate_answer")

    @patch(

        "search_circular.get_relevant_change_events",

        return_value=[

            {

                "change_id": 1,

                "target_title": "UN Sanctions List",

                "provision": "Listed entity details",

                "change_type": "amendment",

                "old_text": "Previous listing",

                "new_text": "Updated listing",

                "amendment_evidence": "Sanctions list update",

                "effective_date": "2026-10-19",

            }

        ],

    )

    @patch("search_circular.find_future_topic_documents", return_value=[])

    @patch("search_circular.validate_candidate_citations", return_value=[])

    @patch("search_circular.get_eligible_version_ids", return_value=[1, 2])

    @patch("search_circular.QdrantClient")

    @patch("search_circular.SentenceTransformer")

    def test_unrelated_change_event_does_not_generate_repo_rate_answer(

        self,

        mock_sentence_transformer,

        mock_qdrant_client,

        mock_eligible_versions,

        mock_validate,

        mock_future_documents,

        mock_change_events,

        mock_generate_answer,

    ):

        mock_model = mock_sentence_transformer.return_value

        mock_model.encode.return_value.tolist.return_value = [0.1, 0.2]



        mock_client = mock_qdrant_client.return_value

        mock_client.query_points.return_value.points = []



        with patch.object(self.app, "DB_PATH", self.temp_db):

            with patch("builtins.input", side_effect=[

                "What was the RBI repo rate?",

                "2026-10-20",

            ]):

                with patch("builtins.print") as mock_print:

                    self.app.semantic_search(

                        "What was the RBI repo rate?",

                        circular=None,

                        as_of_date="2026-10-20",

                    )



        mock_generate_answer.assert_not_called()

        mock_print.assert_any_call(

            "\nNO ANSWER: No eligible, relevant evidence was found "

            "for this question and publication cutoff."

        )



    def test_change_event_is_excluded_when_amendment_published_after_cutoff(self):

        connection = sqlite3.connect(self.temp_db)

        try:

            connection.execute("""

                CREATE TABLE regulatory_changes (

                    change_id INTEGER PRIMARY KEY,

                    target_title TEXT NOT NULL,

                    provision TEXT NOT NULL,

                    change_type TEXT NOT NULL,

                    effective_date TEXT NOT NULL,

                    old_text TEXT NOT NULL,

                    new_text TEXT NOT NULL,

                    historical_source_url TEXT NOT NULL,

                    amendment_source_url TEXT NOT NULL,

                    amendment_document_id INTEGER NOT NULL,

                    amendment_version_id INTEGER NOT NULL,

                    amendment_evidence TEXT NOT NULL,

                    provenance_status TEXT NOT NULL,

                    created_at TEXT NOT NULL

                )

            """)



            connection.execute("""

                INSERT INTO regulatory_changes VALUES (

                    1, 'Test Regulation', 'Paragraph 12', 'amended',

                    '2026-10-19', 'old requirement', 'new requirement',

                    'https://example.org/old', 'https://example.org/new',

                    3, 3, 'Test evidence', 'test provenance',

                    '2026-10-25T10:00:00+00:00'

                )

            """)

            connection.commit()

        finally:

            connection.close()



        with patch.object(self.app, "DB_PATH", self.temp_db):

            events = self.app.get_relevant_change_events(

                "What changed in Test Regulation paragraph 12?",

                as_of_date="2026-10-22",

            )



        self.assertEqual(events, [])



    def test_change_event_is_excluded_when_amendment_publication_date_is_missing(self):

        connection = sqlite3.connect(self.temp_db)

        try:

            connection.execute("""

                CREATE TABLE regulatory_changes (

                    change_id INTEGER PRIMARY KEY,

                    target_title TEXT NOT NULL,

                    provision TEXT NOT NULL,

                    change_type TEXT NOT NULL,

                    effective_date TEXT NOT NULL,

                    old_text TEXT NOT NULL,

                    new_text TEXT NOT NULL,

                    historical_source_url TEXT NOT NULL,

                    amendment_source_url TEXT NOT NULL,

                    amendment_document_id INTEGER NOT NULL,

                    amendment_version_id INTEGER NOT NULL,

                    amendment_evidence TEXT NOT NULL,

                    provenance_status TEXT NOT NULL,

                    created_at TEXT NOT NULL

                )

            """)



            connection.execute("""

                INSERT INTO regulatory_changes VALUES (

                    1, 'Test Regulation', 'Paragraph 12', 'amended',

                    '2026-10-19', 'old requirement', 'new requirement',

                    'https://example.org/old', 'https://example.org/new',

                    3, 3, 'Test evidence', 'test provenance',

                    '2026-10-25T10:00:00+00:00'

                )

            """)



            # The test setup already has version 3; remove its publication date.

            connection.execute("""

                UPDATE document_versions

                SET publication_date = NULL

                WHERE version_id = 3

            """)

            connection.commit()

        finally:

            connection.close()



        with patch.object(self.app, "DB_PATH", self.temp_db):

            events = self.app.get_relevant_change_events(

                "What changed in Test Regulation paragraph 12?",

                as_of_date="2026-10-22",

            )



        self.assertEqual(events, [])





if __name__ == "__main__":

    unittest.main(verbosity=2)
