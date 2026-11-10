from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pydantic import ValidationError

from reels.db import init_db, session
from reels.metadata.prompts import SYSTEM, metadata_prompt
from reels.metadata.schema import InstagramMetadata, MetadataBundle, clean_hashtags
from reels.metadata.service import generate
from reels.script.llm import MockLLM


def make_bundle(**overrides):
    data = {
        "instagram": {
            "caption": "अंतरिक्ष में बढ़ता कचरा एक बड़ी चुनौती है 🚀 आप क्या सोचते हैं?",
            "hashtags": ["हिंदी", "space", "india", "reels", "facts", "science"],
        },
        "youtube": {
            "title": "अंतरिक्ष का कचरा साफ करेगा भारत, जानिए कैसे",
            "caption": "भारत की पहली स्पेस डेब्रिस सफाई सुविधा और भविष्य की योजनाओं की पूरी जानकारी हिंदी में।",
            "hashtags": ["Shorts", "हिंदी", "space"],
            "tags": ["हिंदी Facts", "space news", "india space"],
        },
    }
    for key, value in overrides.items():
        data[key].update(value)
    return MetadataBundle.model_validate(data)


class MetadataSchemaTests(unittest.TestCase):
    def test_hashtags_normalized_and_deduped(self):
        self.assertEqual(
            clean_hashtags(["#Space", " space ", "#India", "SPACE", ""]),
            ["Space", "India"],
        )

    def test_instagram_requires_emoji(self):
        with self.assertRaises(ValidationError):
            InstagramMetadata(caption="कोई इमोजी नहीं है लेकिन कैप्शन काफी लंबा है।", hashtags=["a", "b", "c", "d", "e"])

    def test_hashtag_count_limits(self):
        with self.assertRaises(ValidationError):
            make_bundle(instagram={"hashtags": ["a", "b"]})
        with self.assertRaises(ValidationError):
            make_bundle(instagram={"hashtags": [f"tag{i}" for i in range(16)]})

    def test_youtube_title_length(self):
        with self.assertRaises(ValidationError):
            make_bundle(youtube={"title": "छोटा"})

    def test_rows_split_platforms(self):
        rows = {row["platform"]: row for row in make_bundle().as_rows()}
        self.assertIn("🚀", rows["instagram"]["caption"])
        self.assertEqual(rows["youtube"]["title"], "अंतरिक्ष का कचरा साफ करेगा भारत, जानिए कैसे")

    def test_mock_llm_returns_metadata(self):
        result = MockLLM().generate_json(SYSTEM, metadata_prompt({"scenes": []}, "space"))
        bundle = MetadataBundle.model_validate(result)
        self.assertGreaterEqual(len(bundle.instagram.hashtags), 5)


class MetadataServiceTests(unittest.TestCase):
    def _run_dir(self, root: Path) -> Path:
        run = root / "runs" / "20260101-000000_voice1"
        run.mkdir(parents=True)
        package = {
            "title_hi": "परीक्षण",
            "hook_hi": "क्या आप जानते हैं?",
            "scenes": [{"narration_hi": "यह एक परीक्षण दृश्य है।", "visual_en": "space", "duration_s": 8}],
            "cta_hi": "फॉलो करें।",
        }
        (run / "script.json").write_text(
            json.dumps({"script_id": 1, "topic": "space", "package": package}, ensure_ascii=False),
            encoding="utf-8",
        )
        (run / "timing.json").write_text(json.dumps({"total_s": 30}), encoding="utf-8")
        (run / "captions.srt").write_text("1\n00:00:00,000 --> 00:00:02,000\nनमस्ते\n", encoding="utf-8")
        return run

    def test_generate_writes_metadata_srt_and_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run = self._run_dir(root)
            db_path = root / "test.db"
            init_db(db_path)
            video_path = root / "output" / "videos" / "reel.mp4"
            video_path.parent.mkdir(parents=True)
            video_path.write_bytes(b"x")
            with session(db_path) as conn:
                conn.execute(
                    "INSERT INTO topics (topic_hash, title) VALUES ('h', 'space')"
                )
                conn.execute(
                    "INSERT INTO scripts (topic_id, scenes_json) VALUES (1, '{}')"
                )
                conn.execute(
                    "INSERT INTO videos (script_id, run_id, path) VALUES (1, ?, ?)",
                    (run.name, str(video_path)),
                )

            result = generate(run, MockLLM(), db_path=db_path)

            self.assertTrue((run / "metadata.json").is_file())
            self.assertEqual(Path(result["srt"]), video_path.with_suffix(".hi.srt"))
            self.assertTrue(Path(result["srt"]).is_file())
            with session(db_path) as conn:
                rows = conn.execute(
                    "SELECT platform, title, caption, hashtags, tags FROM captions ORDER BY platform"
                ).fetchall()
            self.assertEqual([row["platform"] for row in rows], ["instagram", "youtube"])
            self.assertIsNone(rows[0]["title"])
            hashtags = json.loads(rows[0]["hashtags"])
            self.assertIn("space", hashtags)
            self.assertTrue(all(not tag.startswith("#") for tag in hashtags))
            self.assertIn("#space", rows[0]["caption"])

            generate(run, MockLLM(), db_path=db_path)
            with session(db_path) as conn:
                count = conn.execute("SELECT COUNT(*) AS n FROM captions").fetchone()["n"]
            self.assertEqual(count, 2)

    def test_missing_video_row_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run = self._run_dir(root)
            db_path = root / "test.db"
            init_db(db_path)
            with self.assertRaises(LookupError):
                generate(run, MockLLM(), db_path=db_path)


if __name__ == "__main__":
    unittest.main(verbosity=2)
