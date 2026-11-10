from __future__ import annotations

import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from reels.trends.dedupe import is_duplicate, jaccard, tokens
from reels.trends.scorer import score
from reels.trends.sources import allowed_script, clean_text, parse_date


class TrendTests(unittest.TestCase):
    def test_tokens_match_hindi_and_english(self):
        self.assertIn("isro", tokens("ISRO launches new satellite"))
        self.assertIn("विज्ञान", tokens("विज्ञान की नई खोज"))

    def test_near_duplicate_detected(self):
        a = "ISRO launches new satellite for weather monitoring"
        b = "ISRO launches a new satellite for weather monitoring today"
        self.assertGreater(jaccard(a, b), 0.7)
        self.assertTrue(is_duplicate(b, [a]))

    def test_different_topics_not_duplicate(self):
        self.assertFalse(is_duplicate("ISRO satellite launch", ["Virat Kohli century"]))

    def test_hindi_title_is_allowed_other_indic_script_rejected(self):
        self.assertTrue(allowed_script("विज्ञान की नई खोज"))
        self.assertTrue(allowed_script("New AI model from India"))
        self.assertFalse(allowed_script("മലയാളം വാർത്ത"))

    def test_science_outranks_cricket_score(self):
        now = datetime.now(timezone.utc) - timedelta(hours=2)
        science = score("New ISRO science mission discovers water on the moon", "google_news", now, {})
        cricket = score("India cricket match score today highlights", "google_news", now, {})
        self.assertGreater(science, cricket)

    def test_parse_date_rfc_and_iso(self):
        self.assertIsNotNone(parse_date("Sun, 08 Nov 2026 15:04:27 GMT"))
        self.assertIsNotNone(parse_date("2026-11-08T15:04:27Z"))
        self.assertIsNone(parse_date("not a date"))

    def test_clean_text_strips_html(self):
        self.assertEqual(clean_text("<b>Hello</b>&amp; world"), "Hello & world")


if __name__ == "__main__":
    unittest.main(verbosity=2)
