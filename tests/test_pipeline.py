from __future__ import annotations

import json
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from reels.db import get_setting, init_db
from reels.pipeline import produce, run_slot

TOPIC = {"id": 1, "title": "à¤…à¤‚à¤¤à¤°à¤¿à¤•à¥à¤· à¤•à¤šà¤°à¤¾", "topic_hash": "abc123", "status": "new"}


class ProduceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.db = self.root / "test.db"
        init_db(self.db)
        self.run_dir = self.root / "runs" / "RID_voice7"
        self.run_dir.mkdir(parents=True)

    def tearDown(self):
        self.tmp.cleanup()

    def _produce(self, **overrides):
        calls = {"publish": None}
        defaults = dict(
            discover=lambda **kw: ([], []),
            select_topic=lambda *a, **kw: TOPIC,
            generate_script=lambda *a, **kw: {
                "run_id": "RID",
                "script_id": 7,
                "script_path": "script.json",
                "verdict": "pass",
                "package": {"scenes": []},
            },
            build_voiceover=lambda *a, **kw: {"run_dir": str(self.run_dir)},
            render=lambda *a, **kw: {"video": "reel.mp4", "duration_s": 45.0},
            generate_metadata=lambda *a, **kw: {"metadata": "metadata.json"},
            publish_videos=lambda *a, **kw: {"results": [{"platform": "youtube", "status": "published"}]},
        )
        defaults.update(overrides)
        stack = [patch(f"reels.pipeline.{name}", new=value) for name, value in defaults.items()]
        for patcher in stack:
            patcher.start()
            self.addCleanup(patcher.stop)
        return produce(llm=object(), db_path=self.db, **self.kw_extra)

    @property
    def kw_extra(self):
        return getattr(self, "_extra", {})

    def test_produce_runs_pipeline_without_publishing(self):
        self._extra = {"publish_after": False}
        result = self._produce()
        self.assertEqual(result["run_id"], "RID_voice7")
        self.assertEqual(result["duration_s"], 45.0)
        self.assertIsNone(result["publish"])
        saved = json.loads((self.run_dir / "produce.json").read_text(encoding="utf-8"))
        self.assertEqual(saved["video"], "reel.mp4")

    def test_produce_publishes_when_forced(self):
        self._extra = {"publish_after": True}
        result = self._produce()
        self.assertEqual(result["publish"]["results"][0]["status"], "published")

    def test_produce_skips_rejected_topic(self):
        attempts = iter(
            [
                {"run_id": "R1", "script_id": None, "verdict": "fail", "package": {}},
                {
                    "run_id": "RID",
                    "script_id": 7,
                    "script_path": "script.json",
                    "verdict": "pass",
                    "package": {"scenes": []},
                },
            ]
        )
        self._extra = {"publish_after": False}
        result = self._produce(generate_script=lambda *a, **kw: next(attempts))
        self.assertEqual(result["run_id"], "RID_voice7")


class RunSlotTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "test.db"
        init_db(self.db)

    def tearDown(self):
        self.tmp.cleanup()

    def test_second_run_same_slot_is_skipped(self):
        with patch("reels.pipeline.produce", return_value={"run_id": "x"}) as fake:
            first = run_slot(0, db_path=self.db)
            second = run_slot(0, db_path=self.db)
        self.assertEqual(first["status"], "done")
        self.assertEqual(second["status"], "skipped")
        self.assertEqual(fake.call_count, 1)
        key = f"daily:{date.today().isoformat()}:slot0"
        self.assertEqual(get_setting(key, path=self.db), "done")

    def test_failure_is_recorded_not_marked_done(self):
        with patch("reels.pipeline.produce", side_effect=RuntimeError("boom")):
            result = run_slot(1, db_path=self.db)
        self.assertEqual(result["status"], "failed")
        key = f"daily:{date.today().isoformat()}:slot1"
        self.assertEqual(get_setting(key, path=self.db), "failed")


if __name__ == "__main__":
    unittest.main()


