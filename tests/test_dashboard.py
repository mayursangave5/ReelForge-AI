from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from reels.dashboard import (
    _approvals_tab,
    error_log,
    generated_videos,
    pending_approvals,
    published_videos,
    reject_video,
    resolve_video_path,
    today_topics,
    upload_history,
)
from reels.db import init_db, session


class _FakeStreamlit:
    """Records component calls so we can assert what reaches the UI."""

    def __init__(self, calls: list) -> None:
        self.calls = calls

    def __getattr__(self, name):
        def record(*args, **kwargs):
            self.calls.append((name, args, kwargs))
            if name == "columns":
                count = args[0] if isinstance(args[0], int) else len(args[0])
                return tuple(_FakeStreamlit(self.calls) for _ in range(count))
            if name == "button":
                return False
            if name == "multiselect":
                return kwargs.get("default", [])
            if name == "text_input":
                return kwargs.get("value", "")
            return None

        return record


class DashboardDataTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "test.db"
        init_db(self.db)
        with session(self.db) as conn:
            conn.execute(
                "INSERT INTO topics (topic_hash, title, score, status) VALUES ('h1', 'space', 3.5, 'scripted')"
            )
            conn.execute(
                "INSERT INTO scripts (topic_id, scenes_json) VALUES (1, '{}')"
            )
            conn.execute(
                "INSERT INTO videos (script_id, run_id, path, duration_s, status) "
                "VALUES (1, 'run_ok', 'v1.mp4', 42.0, 'rendered')"
            )
            conn.execute(
                "INSERT INTO videos (script_id, run_id, path, duration_s, status) "
                "VALUES (1, 'run_live', 'v2.mp4', 40.0, 'published')"
            )
            conn.execute(
                "INSERT INTO publications (video_id, platform, remote_id, url, status, "
                "idempotency_key, published_at) "
                "VALUES (2, 'youtube', 'yt1', 'https://youtu.be/yt1', 'published', "
                "'run_live:youtube', '2026-11-10T12:00:00')"
            )
            conn.execute(
                "INSERT INTO errors (stage, message) VALUES ('publish', 'quota')"
            )

    def tearDown(self):
        self.tmp.cleanup()

    def test_today_topics_returns_recent_topic(self):
        rows = today_topics(self.db)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["title"], "space")

    def test_pending_shows_only_rendered(self):
        rows = pending_approvals(self.db)
        self.assertEqual([row["run_id"] for row in rows], ["run_ok"])
        self.assertEqual(rows[0]["title"], "space")

    def test_published_and_history(self):
        published = published_videos(self.db)
        self.assertEqual(published[0]["url"], "https://youtu.be/yt1")
        history = upload_history(self.db)
        self.assertEqual(history[0]["platform"], "youtube")
        self.assertEqual(generated_videos(self.db)[0]["run_id"], "run_live")

    def test_errors_and_reject(self):
        self.assertEqual(error_log(self.db)[0]["message"], "quota")
        reject_video(1, self.db)
        self.assertEqual(pending_approvals(self.db), [])
        self.assertEqual(generated_videos(self.db)[-1]["status"], "rejected")

    def test_resolve_video_path_keeps_absolute_and_resolves_relative(self):
        absolute = Path(self.tmp.name) / "reel.mp4"
        self.assertEqual(resolve_video_path(str(absolute)), absolute)
        self.assertEqual(resolve_video_path("reel.mp4").name, "reel.mp4")
        self.assertTrue(resolve_video_path("reel.mp4").is_absolute())

    def test_approvals_tab_passes_mp4_to_video_player(self):
        video = Path(self.tmp.name) / "reel_run_ok.mp4"
        video.write_bytes(b"fake")
        row = {
            "id": 1,
            "run_id": "run_ok",
            "path": str(video),
            "duration_s": 42.0,
            "created_at": "2026-11-10T12:00:00",
            "title": "space",
            "hook": "look up",
        }
        calls: list = []
        with patch("reels.dashboard.st", _FakeStreamlit(calls)), patch(
            "reels.dashboard.pending_approvals", return_value=[row]
        ):
            _approvals_tab()

        players = [call for call in calls if call[0] == "video"]
        self.assertEqual(len(players), 1)
        self.assertEqual(players[0][1][0], str(video))
        self.assertFalse(players[0][2].get("autoplay", False))
        self.assertFalse(any(call[0] == "error" for call in calls))

    def test_approvals_tab_renders_one_player_per_video(self):
        first = Path(self.tmp.name) / "reel_a.mp4"
        second = Path(self.tmp.name) / "reel_b.mp4"
        first.write_bytes(b"a")
        second.write_bytes(b"b")
        rows = [
            {"id": 1, "run_id": "a", "path": str(first), "duration_s": 30.0,
             "created_at": "", "title": "a", "hook": ""},
            {"id": 2, "run_id": "b", "path": str(second), "duration_s": 31.0,
             "created_at": "", "title": "b", "hook": ""},
        ]
        calls: list = []
        with patch("reels.dashboard.st", _FakeStreamlit(calls)), patch(
            "reels.dashboard.pending_approvals", return_value=rows
        ):
            _approvals_tab()

        rendered = [call[1][0] for call in calls if call[0] == "video"]
        self.assertEqual(rendered, [str(first), str(second)])

    def test_approvals_tab_reports_missing_video(self):
        missing = Path(self.tmp.name) / "gone.mp4"
        row = {"id": 1, "run_id": "gone", "path": str(missing), "duration_s": 30.0,
               "created_at": "", "title": "gone", "hook": ""}
        calls: list = []
        with patch("reels.dashboard.st", _FakeStreamlit(calls)), patch(
            "reels.dashboard.pending_approvals", return_value=[row]
        ):
            _approvals_tab()

        self.assertFalse(any(call[0] == "video" for call in calls))
        errors = [call[1][0] for call in calls if call[0] == "error"]
        self.assertEqual(len(errors), 1)
        self.assertIn(str(missing), errors[0])

    def test_approvals_tab_shows_existing_r2_url(self):
        video = Path(self.tmp.name) / "reel_r2.mp4"
        video.write_bytes(b"r2")
        row = {"id": 10, "run_id": "r2_run", "path": str(video), "duration_s": 30.0,
               "created_at": "", "title": "r2 title", "hook": "r2 hook"}
        calls: list = []
        with patch("reels.dashboard.st", _FakeStreamlit(calls)), patch(
            "reels.dashboard.pending_approvals", return_value=[row]
        ), patch(
            "reels.storage.stored_url", return_value="https://pub-r2.example.com/reels/r2_run.mp4"
        ):
            _approvals_tab()

        successes = [call[1][0] for call in calls if call[0] == "success"]
        self.assertTrue(any("https://pub-r2.example.com/reels/r2_run.mp4" in s for s in successes))
        # Ensure manual URL text input was NOT rendered
        text_inputs = [call for call in calls if call[0] == "text_input"]
        self.assertEqual(len(text_inputs), 0)

    def test_approvals_tab_shows_unconfigured_r2_warning(self):
        from unittest.mock import PropertyMock
        from reels.config import settings

        video = Path(self.tmp.name) / "reel_unconfigured.mp4"
        video.write_bytes(b"unconfigured")
        row = {"id": 11, "run_id": "no_r2", "path": str(video), "duration_s": 30.0,
               "created_at": "", "title": "no r2", "hook": "no r2"}
        calls: list = []
        with patch("reels.dashboard.st", _FakeStreamlit(calls)), patch(
            "reels.dashboard.pending_approvals", return_value=[row]
        ), patch(
            "reels.storage.stored_url", return_value=None
        ), patch.object(
            type(settings), "r2_configured", new_callable=PropertyMock, return_value=False
        ):
            _approvals_tab()

        warnings = [call[1][0] for call in calls if call[0] == "warning"]
        self.assertTrue(any("Cloudflare R2 is not configured" in w for w in warnings))


if __name__ == "__main__":
    unittest.main()
