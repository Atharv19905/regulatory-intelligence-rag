import unittest
from search_circular import get_relevant_change_events


class SFBCandidateRetrievalTests(unittest.TestCase):

    def test_sfb_candidate_is_retrieved_and_labelled(self):
        candidate = {
            "target_title": (
                "Reserve Bank of India (Small Finance Banks - Miscellaneous) "
                "Directions, 2025"
            ),
            "provision": "Chapter IV, Section C, paragraph 37",
            "change_type": "candidate_deletion",
            "publication_date": "2026-10-19",
            "effective_date": None,
            "amendment_source_url": "https://rbi.org.in/scripts/NotificationUser.aspx?Mode=0&Id=13741",
            "amendment_evidence": "Paragraph 37 stands deleted.",
            "provenance_status": "UNVERIFIED CANDIDATE",
        }

        results = get_relevant_change_events(
            "What happened to paragraph 37 of the Small Finance Banks Directions?",
            candidate_event=candidate,
        )

        candidate_results = [
            event for event in results
            if event.get("is_unverified_candidate")
        ]

        self.assertEqual(len(candidate_results), 1)
        self.assertTrue(
            candidate_results[0]["requires_historical_source_verification"]
        )
        self.assertEqual(
            candidate_results[0]["change_type"],
            "candidate_deletion",
        )


if __name__ == "__main__":
    unittest.main()