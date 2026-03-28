import unittest

from backend.domains import enumerate_candidate_urls
from backend.normalize import normalize_query


class QueryHelperTests(unittest.TestCase):
    def test_normalize_query_supports_nested_object(self) -> None:
        normalized = normalize_query(
            {
                "query": "embroidered denim underground brands",
                "profile": {"style": ["avant-garde", "DIY"]},
                "notes": {"avoid": ["mass market"]},
            }
        )

        self.assertEqual(normalized.query_text, "embroidered denim underground brands")
        self.assertEqual(normalized.profile, {"style": ["avant-garde", "DIY"]})
        self.assertIn("embroidered", normalized.keywords)
        self.assertIn("denim", normalized.keywords)

    def test_enumerate_candidate_urls_from_keyword_pairs(self) -> None:
        urls = enumerate_candidate_urls(["flower", "origami"], ("com", "org"), limit=8)

        self.assertIn("https://flowerorigami.com", urls)
        self.assertIn("https://flower-origami.org", urls)
        self.assertIn("https://origamiflower.com", urls)
        self.assertLessEqual(len(urls), 8)


if __name__ == "__main__":
    unittest.main()
