from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from reels.db import init_db, session
from reels.publish.auth import redact
from reels.publish.instagram import InstagramError, publish_reel
from reels.publish.service import idempotency_key, publish
from reels.publish.youtube import build_body

NOT_READY_YT = {
    "client_secrets": "x",
    "client_secrets_ready": False,
    "token": "x",
    "token_ready": False,
    "scopes": [],
    "authorized": False,
    "expired": None,
}
NOT_READY_IG = {"ig_user_id": False, "access_token": False, "api_version": "v21.0"}


def make_db(root: Path, with_captions: bool = True) -> tuple[Path, Path, str]:
    db_path = root / "test.db"
    init_db(db_path)
    run = root / "runs" / "20260101-000000_voice1"
    run.mkdir(parents=True)
    video = root / "output" / "reel.mp4"
    video.parent.mkdir(parents=True)
    video.write_bytes(b"video")
    with session(db_path) as conn:
        conn.execute("INSERT INTO topics (topic_hash, title) VALUES ('h', 'space')")
        conn.execute(
            "INSERT INTO scripts (topic_id, scenes_json) VALUES (1, '{}')"
        )
        conn.execute(
            "INSERT INTO videos (script_id, run_id, path) VALUES (1, ?, ?)",
            (run.name, str(video)),
        )
        if with_captions:
            conn.execute(
                "INSERT INTO captions (video_id, platform, title, caption, hashtags, tags) "
                "VALUES (1, 'instagram', NULL, ?, ?, '[]')",
                ("हिंदी कैप्शन 🚀", json.dumps(["space", "india"])),
            )
            conn.execute(
                "INSERT INTO captions (video_id, platform, title, caption, hashtags, tags) "
                "VALUES (1, 'youtube', ?, ?, ?, ?)",
                (
                    "अंतरिक्ष का कचरा साफ करेगा भारत",
                    "भारत की पहली स्पेस डेब्रिस सफाई सुविधा की पूरी जानकारी हिंदी में।",
                    json.dumps(["Shorts", "space"]),
                    json.dumps(["space news", "hindi facts"]),
                ),
            )
    return db_path, run, video.name


class PublishUnitTests(unittest.TestCase):
    def test_idempotency_key_is_stable(self):
        self.assertEqual(
            idempotency_key("20260101-000000_voice1", "youtube"),
            "20260101-000000_voice1:youtube",
        )

    def test_redact_hides_tokens(self):
        text = "fail access_token=EAA1234567890abcdef and AQ.abcdefghijklmnopqrstuvwxyz123456"
        cleaned = redact(text)
        self.assertNotIn("EAA1234567890abcdef", cleaned)
        self.assertNotIn("AQ.abcdefghijklmnopqrstuvwxyz", cleaned)
        self.assertIn("<redacted>", cleaned)

    def test_youtube_body_composes_hashtags(self):
        body = build_body(
            {
                "title": "शीर्षक",
                "caption": "विवरण",
                "hashtags": ["Shorts", "space"],
                "tags": ["a" * 200, "b" * 200, "c" * 200],
            },
            "private",
        )
        self.assertIn("#Shorts #space", body["snippet"]["description"])
        self.assertLessEqual(len(",".join(body["snippet"]["tags"])), 500)
        self.assertEqual(body["status"]["privacyStatus"], "private")

    def test_instagram_requires_https(self):
        with self.assertRaises(InstagramError):
            publish_reel("http://example.com/v.mp4", "caption", "1", "token")


class PublishServiceTests(unittest.TestCase):
    def test_dry_run_records_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path, run, _ = make_db(Path(tmp))
            with patch("reels.publish.service.youtube_status", return_value=NOT_READY_YT), patch(
                "reels.publish.service.instagram_status", return_value=NOT_READY_IG
            ):
                first = publish(run, ["youtube", "instagram"], db_path=db_path)
                second = publish(run, ["youtube", "instagram"], db_path=db_path)
            self.assertEqual([item["status"] for item in first["results"]], ["dry_run", "dry_run"])
            self.assertEqual([item["status"] for item in second["results"]], ["dry_run", "dry_run"])
            with session(db_path) as conn:
                rows = conn.execute(
                    "SELECT platform, status FROM publications ORDER BY platform"
                ).fetchall()
            self.assertEqual([(r["platform"], r["status"]) for r in rows], [
                ("instagram", "dry_run"),
                ("youtube", "dry_run"),
            ])

    def test_published_is_skipped(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path, run, _ = make_db(Path(tmp))
            with session(db_path) as conn:
                conn.execute(
                    "INSERT INTO publications (video_id, platform, remote_id, status, idempotency_key) "
                    "VALUES (1, 'youtube', 'abc', 'published', ?)",
                    (idempotency_key(run.name, "youtube"),),
                )
            with patch("reels.publish.service.youtube_status", return_value=NOT_READY_YT):
                result = publish(run, ["youtube"], db_path=db_path)
            self.assertEqual(result["results"][0]["status"], "skipped")
            self.assertEqual(result["results"][0]["remote_id"], "abc")

    def test_confirm_without_credentials_fails_without_network(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path, run, _ = make_db(Path(tmp))
            with patch("reels.publish.service.youtube_status", return_value=NOT_READY_YT), patch(
                "reels.publish.service.instagram_status", return_value=NOT_READY_IG
            ):
                result = publish(run, ["youtube", "instagram"], db_path=db_path, confirm=True)
            self.assertEqual([item["status"] for item in result["results"]], ["failed", "failed"])
            with session(db_path) as conn:
                rows = conn.execute("SELECT status, error FROM publications").fetchall()
            self.assertTrue(all(row["status"] == "failed" for row in rows))
            self.assertTrue(all(row["error"] for row in rows))

    def test_instagram_requires_public_url(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path, run, _ = make_db(Path(tmp))
            with patch("reels.publish.service.instagram_status", return_value=NOT_READY_IG):
                result = publish(run, ["instagram"], db_path=db_path)
            self.assertIn("public HTTPS --video-url required", result["results"][0]["blockers"])

    def test_missing_captions_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path, run, _ = make_db(Path(tmp), with_captions=False)
            with self.assertRaises(LookupError):
                publish(run, ["youtube"], db_path=db_path)


if __name__ == "__main__":
    unittest.main(verbosity=2)
