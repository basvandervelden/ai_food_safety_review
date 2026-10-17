import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

from audit.openalex_fulltext_audit import (
    assess_match, normalize_doi, resolve, search_by_title, summarize
)


class TestBibliographicMatching(unittest.TestCase):
    def setUp(self):
        self.paper = {
            "title": "Predicting Listeria monocytogenes virulence potential using whole genome sequencing and machine learning",
            "year": 2024,
            "authors": ["Gmeiner, A. et al."],
            "doi": ""
        }
        self.work = {
            "id": "https://openalex.org/W123",
            "display_name": self.paper["title"],
            "publication_year": 2024,
            "authorships": [{"author": {"display_name": "Anna Gmeiner"}}],
        }

    def test_doi_normalization(self):
        self.assertEqual(normalize_doi("https://doi.org/10.1234/ABC"), "10.1234/abc")

    def test_exact_title(self):
        accepted, method, _ = assess_match(self.paper, self.work)
        self.assertTrue(accepted)
        self.assertEqual(method, "exact_title")

    def test_wrong_author_is_not_automatically_matched(self):
        self.work["authorships"][0]["author"]["display_name"] = "Jane Doe"
        self.assertFalse(assess_match(self.paper, self.work)[0])

    def test_wrong_year_is_not_automatically_matched(self):
        self.work["publication_year"] = 2020
        self.assertFalse(assess_match(self.paper, self.work)[0])

    def test_exact_doi_match(self):
        self.paper["doi"] = "10.1234/ABC"
        self.work["doi"] = "https://doi.org/10.1234/abc"
        self.assertTrue(assess_match(self.paper, self.work, by_doi=True)[0])

    @patch("audit.openalex_fulltext_audit.api_json")
    def test_questions_in_titles_are_safe_for_openalex(self, mock_api):
        mock_api.return_value = {"results": []}
        for title in (
            "Is my food safe? – AI-based classification of lentil flour",
            "nEmesis: Which restaurants should you avoid today?",
            "Example* wildcard? term"
        ):
            with self.subTest(title=title):
                search_by_title(title, "unused-key")
                url = mock_api.call_args.args[0]
                term = parse_qs(urlsplit(url).query)["search.title"][0]
                self.assertNotIn("?", term)
                self.assertNotIn("*", term)
                self.assertIn(" ", term)

    @patch("audit.openalex_fulltext_audit.search_by_title")
    def test_bad_title_query_is_unknown_not_abort_or_non_oa(self, search):
        search.side_effect = RuntimeError("OpenAlex HTTP 400: bad wildcard query")
        paper = {**self.paper, "doi": ""}
        work, status, score, note = resolve(paper, "unused-key")
        self.assertIsNone(work)
        self.assertEqual(status, "lookup_error")
        self.assertIn("HTTP 400", note)

    def test_unresolved_papers_are_not_recorded_as_non_oa(self):
        rows = [
            {"source_group": "original_review", "match_status": "matched", "is_open_access": True,
             "has_openalex_pdf": False, "has_openalex_xml": True},
            {"source_group": "post_review_sample", "match_status": "unresolved", "is_open_access": "",
             "has_openalex_pdf": "", "has_openalex_xml": ""},
        ]
        counts = summarize(rows)
        self.assertEqual((counts["matched"], counts["unresolved"], counts["oa"], counts["xml"]), (1, 1, 1, 1))


if __name__ == "__main__":
    unittest.main()
