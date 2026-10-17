import unittest

from audit.openalex_fulltext_audit import assess_match, normalize_doi, summarize


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
