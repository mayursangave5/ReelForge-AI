from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from reels.analytics import (
    capture,
    latest,
    performance_bonus,
    performance_hints,
    summary,
)
from reels.db import init_db, session
from reels.script.service import select_topic


def yt_stats(ids):
    return {i: {"views": 100, "likes": 10, "comments": 3, "shares": None, "retention": None} for i in ids}


def ig_stats(ids):
    return {i: {"views": 50, "likes": 5, "comments": 2, "shares": 1, "retention": None} for i in ids}


class AnalyticsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "test.db"
        init_db(self.db)
        with session(self.db) as conn:
            conn.execute(
                "INSERT INTO topics (topic_hash, title, score, status) "
                "VALUES ('h1', 'space debris cleanup mission', 0.9, 'published')"
            )
            conn.execute("INSERT INTO scripts (topic_id, scenes_json, hook) VALUES (1, '{}', 'hook')")
            conn.execute(
                "INSERT INTO videos (script_id, run_id, path, status) "
                "VALUES (1, 'run1', 'v.mp4', 'published')"
            )
            conn.execute(
                "INSERT INTO publications (video_id, platform, remote_id, status, idempotency_key) "
                "VALUES (1, 'youtube', 'yt1', 'published', 'run1:youtube')"
            )
            conn.execute(
                "INSERT INTO publications (video_id, platform, remote_id, status, idempotency_key) "
                "VALUES (1, 'instagram', 'ig1', 'published', 'run1:instagram')"
            )

    def tearDown(self):
        self.tmp.cleanup()

    def test_capture_saves_and_updates_both_platforms(self):
        result = capture(
            self.db, youtube_fetch=yt_stats, instagram_fetch=ig_stats, captured_on="2026-11-10"
        )
        self.assertEqual(result["saved"], 2)
        self.assertEqual(result["blockers"], [])
        rows = {row["platform"]: row for row in latest(self.db)}
        self.assertEqual(rows["youtube"]["views"], 100)
        self.assertEqual(rows["instagram"]["shares"], 1)

        result = capture(
            self.db,
            youtube_fetch=lambda ids: {i: {"views": 120, "likes": 12, "comments": 3, "shares": None} for i in ids},
            instagram_fetch=ig_stats,
            captured_on="2026-11-11",
        )
        self.assertEqual(result["saved"], 2)
        rows = {row["platform"]: row for row in latest(self.db)}
        self.assertEqual(rows["youtube"]["views"], 120)

    def test_capture_records_platform_errors(self):
        def boom(ids):
            raise RuntimeError("no readonly scope")

        result = capture(self.db, youtube_fetch=boom, instagram_fetch=ig_stats, captured_on="2026-11-10")
        self.assertEqual(result["saved"], 1)
        self.assertIn("youtube", result["blockers"][0])
        with session(self.db) as conn:
            errors = conn.execute("SELECT stage FROM errors").fetchall()
        self.assertEqual(errors[0]["stage"], "analytics")

    def test_summary_aggregates_topic_metrics(self):
        capture(
            self.db, youtube_fetch=yt_stats, instagram_fetch=ig_stats, captured_on="2026-11-10"
        )
        rows = summary(self.db)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["views"], 150)
        self.assertEqual(rows[0]["likes"], 15)
        self.assertEqual(rows[0]["shares"], 1)
        self.assertEqual(rows[0]["engagement_pct"], 14.0)
        self.assertEqual(rows[0]["platforms"], "instagram, youtube")

    def test_hints_and_bonus_prefer_similar_topics(self):
        capture(
            self.db, youtube_fetch=yt_stats, instagram_fetch=ig_stats, captured_on="2026-11-10"
        )
        hints = performance_hints(self.db)
        self.assertEqual(hints[0]["weight"], 1.0)
        self.assertGreater(
            performance_bonus("space debris cleanup", hints),
            performance_bonus("cooking recipes", hints),
        )
        self.assertEqual(performance_bonus("cooking recipes", hints), 0.0)

    def test_select_topic_uses_performance_bonus(self):
        capture(
            self.db, youtube_fetch=yt_stats, instagram_fetch=ig_stats, captured_on="2026-11-10"
        )
        with session(self.db) as conn:
            conn.execute(
                "INSERT INTO topics (topic_hash, title, score, status) "
                "VALUES ('h2', 'cooking recipes', 0.8, 'new')"
            )
            conn.execute(
                "INSERT INTO topics (topic_hash, title, score, status) "
                "VALUES ('h3', 'space debris cleanup', 0.75, 'new')"
            )
        chosen = select_topic(None, self.db)
        self.assertEqual(chosen["title"], "space debris cleanup")


if __name__ == "__main__":
    unittest.main()
