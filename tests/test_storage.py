from __future__ import annotations

import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from reels.db import init_db, session
from reels.publish.service import publish
from reels.storage import (
    R2Storage,
    StorageError,
    cleanup_expired,
    stored_url,
    upload_video,
    verify_public,
)

READY_IG = {"ig_user_id": True, "access_token": True, "api_version": "v21.0"}


class FakeClient:
    def __init__(self, failures: int = 0):
        self.uploads: dict[str, bytes] = {}
        self.deleted: list[str] = []
        self.failures = failures

    def upload_file(self, path, bucket, key, ExtraArgs=None):
        if self.failures:
            self.failures -= 1
            raise RuntimeError("network hiccup")
        self.uploads[key] = Path(path).read_bytes()

    def delete_object(self, Bucket, Key):
        self.deleted.append(Key)


def head_ok(url, **kwargs):
    return SimpleNamespace(
        status_code=200,
        headers={"content-type": "video/mp4", "content-length": "5"},
    )


def head_404(url, **kwargs):
    return SimpleNamespace(status_code=404, headers={})


def make_db(root: Path) -> tuple[Path, Path]:
    db_path = root / "test.db"
    init_db(db_path)
    run = root / "runs" / "RID_voice7"
    run.mkdir(parents=True)
    video = root / "reel.mp4"
    video.write_bytes(b"video")
    with session(db_path) as conn:
        conn.execute("INSERT INTO topics (topic_hash, title) VALUES ('h', 'space')")
        conn.execute("INSERT INTO scripts (topic_id, scenes_json) VALUES (1, '{}')")
        conn.execute(
            "INSERT INTO videos (script_id, run_id, path) VALUES (1, ?, ?)",
            (run.name, str(video)),
        )
        conn.execute(
            "INSERT INTO captions (video_id, platform, caption, hashtags, tags) "
            "VALUES (1, 'instagram', 'कैप्शन', '[]', '[]')"
        )
        conn.execute(
            "INSERT INTO captions (video_id, platform, title, caption, hashtags, tags) "
            "VALUES (1, 'youtube', 'title', 'caption', '[]', '[]')"
        )
    return db_path, run


def fake_storage(client: FakeClient | None = None, **kwargs) -> R2Storage:
    return R2Storage(
        client=client or FakeClient(),
        bucket="videos",
        public_base_url="https://cdn.example.com",
        prefix="reels",
    )


class R2StorageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.file = self.root / "clip.mp4"
        self.file.write_bytes(b"video")
        self.db, self.run = make_db(self.root)

    def tearDown(self):
        self.tmp.cleanup()

    def test_upload_retries_network_errors(self):
        client = FakeClient(failures=1)
        storage = fake_storage(client)
        url = storage.upload(self.file, attempts=3, sleep=lambda _: None)
        self.assertEqual(url, "https://cdn.example.com/reels/clip.mp4")
        self.assertEqual(client.uploads["reels/clip.mp4"], b"video")

    def test_upload_gives_up_after_attempts(self):
        storage = fake_storage(FakeClient(failures=5))
        with self.assertRaises(StorageError):
            storage.upload(self.file, attempts=2, sleep=lambda _: None)

    def test_verify_checks_public_url(self):
        calls = {"n": 0}

        def head(url, **kwargs):
            calls["n"] += 1
            return head_404(url) if calls["n"] == 1 else head_ok(url)

        storage = fake_storage()
        self.assertTrue(storage.verify("https://cdn.example.com/x.mp4", head=head, sleep=lambda _: None))
        self.assertFalse(storage.verify("https://cdn.example.com/x.mp4", head=head_404))
        self.assertFalse(verify_public("http://insecure/x.mp4"))

    def test_upload_video_records_url_and_requires_reachability(self):
        storage = fake_storage()
        storage.verify = lambda url, **kw: True
        result = upload_video(self.file, self.run.name, self.db, storage=storage)
        self.assertTrue(result["verified"])
        self.assertEqual(stored_url(1, self.db), result["url"])
        with session(self.db) as conn:
            row = conn.execute("SELECT key, status FROM cloud_uploads").fetchone()
        self.assertEqual((row["key"], row["status"]), ("reels/RID_voice7.mp4", "uploaded"))

        offline = fake_storage()
        offline.verify = lambda url, **kw: False
        with self.assertRaises(StorageError):
            upload_video(self.file, self.run.name, self.db, storage=offline)

    def test_cleanup_deletes_only_expired_published_uploads(self):
        with session(self.db) as conn:
            conn.execute(
                "INSERT INTO cloud_uploads (video_id, key, url, uploaded_at) "
                "VALUES (1, 'reels/old.mp4', 'https://cdn/old.mp4', '2020-01-01 00:00:00')"
            )
            conn.execute(
                "INSERT INTO publications (video_id, platform, status, idempotency_key) "
                "VALUES (1, 'instagram', 'published', 'k1')"
            )
            conn.execute(
                "INSERT INTO videos (script_id, run_id, path) VALUES (1, 'RID2', 'b.mp4')"
            )
            conn.execute(
                "INSERT INTO cloud_uploads (video_id, key, url, uploaded_at) "
                "VALUES (2, 'reels/pending.mp4', 'https://cdn/pending.mp4', '2020-01-01 00:00:00')"
            )
            conn.execute(
                "INSERT INTO publications (video_id, platform, status, idempotency_key) "
                "VALUES (2, 'instagram', 'failed', 'k2')"
            )
        client = FakeClient()
        result = cleanup_expired(
            self.db, retention_hours=24, storage=fake_storage(client), now=datetime(2026, 1, 1)
        )
        self.assertEqual(result["deleted"], 1)
        self.assertEqual(client.deleted, ["reels/old.mp4"])
        with session(self.db) as conn:
            statuses = {
                row["key"]: row["status"]
                for row in conn.execute("SELECT key, status FROM cloud_uploads")
            }
        self.assertEqual(statuses["reels/old.mp4"], "deleted")
        self.assertEqual(statuses["reels/pending.mp4"], "uploaded")

    def test_publish_uses_stored_r2_url_for_instagram(self):
        storage = fake_storage()
        storage.verify = lambda url, **kw: True
        url = upload_video(self.file, self.run.name, self.db, storage=storage)["url"]
        with patch("reels.publish.service.instagram_status", return_value=READY_IG), patch(
            "reels.storage.verify_public", return_value=True
        ), patch(
            "reels.publish.service.require_instagram", return_value=("1", "token")
        ), patch(
            "reels.publish.service.publish_reel", return_value=("m1", "https://instagram/p/1")
        ) as reel:
            result = publish(self.run, ["instagram"], db_path=self.db, confirm=True)
        self.assertEqual(result["results"][0]["status"], "published")
        reel.assert_called_once_with(url, "कैप्शन", "1", "token")

    def test_publish_uploads_on_demand_when_r2_configured(self):
        with patch(
            "reels.publish.service.settings",
            SimpleNamespace(r2_configured=True, r2_retention_hours=24),
        ), patch(
            "reels.storage.upload_video", return_value={"url": "https://cdn/auto.mp4"}
        ) as uploader, patch(
            "reels.storage.verify_public", return_value=True
        ), patch(
            "reels.publish.service.instagram_status", return_value=READY_IG
        ), patch(
            "reels.publish.service.require_instagram", return_value=("1", "token")
        ), patch(
            "reels.publish.service.publish_reel", return_value=("m1", "https://instagram/p/1")
        ) as reel:
            result = publish(self.run, ["instagram"], db_path=self.db, confirm=True)
        self.assertEqual(result["results"][0]["status"], "published")
        uploader.assert_called_once()
        reel.assert_called_once_with("https://cdn/auto.mp4", "कैप्शन", "1", "token")

    def test_dry_run_still_reports_missing_url(self):
        with patch("reels.publish.service.instagram_status", return_value=READY_IG):
            result = publish(self.run, ["instagram"], db_path=self.db)
        self.assertIn("public HTTPS --video-url required", result["results"][0]["blockers"])


if __name__ == "__main__":
    unittest.main()
