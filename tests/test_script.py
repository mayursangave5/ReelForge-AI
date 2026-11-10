from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from reels.db import init_db, session, topic_hash
from reels.script.llm import FREE_TIER_MODELS, LLMError, MockLLM, ensure_free_tier, parse_json
from reels.script.schema import ScriptPackage, validate_package, factcheck_verdict, VerificationResult
from reels.script.service import generate


def make_package(**overrides):
    data = {
        "title_hi": "परीक्षण शीर्षक",
        "hook_hi": "क्या आप जानते हैं यह चौंकाने वाला तथ्य?",
        "scenes": [
            {"narration_hi": "यह पहला दृश्य है जिसमें दर्शकों को एक बहुत ही दिलचस्प और चौंकाने वाली जानकारी दी जा रही है, ताकि वे अंत तक देखें।", "visual_en": "space view no text", "duration_s": 8},
            {"narration_hi": "यह दूसरा दृश्य है जिसमें इस जानकारी को और भी सरल और रोचक तरीके से उदाहरण के साथ समझाया जा रहा है।", "visual_en": "planet view no text", "duration_s": 8},
            {"narration_hi": "यह तीसरा और अंतिम दृश्य है जिसमें पूरी बात का सरल निष्कर्ष दिया जा रहा है और दर्शकों को सोचने पर मजबूर किया जा रहा है।", "visual_en": "orbit view no text", "duration_s": 9},
        ],
        "cta_hi": "ऐसी जानकारी के लिए फॉलो करें।",
        "estimated_duration_s": 25,
        "claims": [{"claim_hi": "यह एक तथ्य है।", "sources": ["https://example.com/a"], "confidence": "high"}],
    }
    data.update(overrides)
    return ScriptPackage.model_validate(data)


class ScriptTests(unittest.TestCase):
    def test_valid_package_passes(self):
        package = make_package()
        self.assertEqual(validate_package(package), [])

    def test_duration_mismatch_flagged(self):
        package = make_package(estimated_duration_s=50)
        issues = validate_package(package)
        self.assertTrue(any("does not match" in issue for issue in issues), issues)

    def test_unsourced_claim_flagged(self):
        package = make_package(claims=[])
        issues = validate_package(package)
        self.assertTrue(any("no factual claims" in issue for issue in issues))

    def test_claim_with_unknown_source_flagged(self):
        package = make_package()
        issues = validate_package(package, allowed_sources={"https://other.com/b"})
        self.assertTrue(any("not provided" in issue for issue in issues))

    def test_parse_json_strips_fences(self):
        self.assertEqual(parse_json('```json\n{"a": 1}\n```'), {"a": 1})

    def test_default_model_is_free_tier(self):
        from reels.config import Settings

        self.assertIn(Settings().gemini_model, FREE_TIER_MODELS)

    def test_paid_model_is_refused(self):
        ensure_free_tier("gemini-3.8-flash")
        with self.assertRaises(LLMError):
            ensure_free_tier("gemini-4-argon")

    def test_factcheck_verdict(self):
        pass_result = VerificationResult.model_validate({"results": [{"claim_hi": "x", "supported": True}]})
        fail_result = VerificationResult.model_validate({"results": [{"claim_hi": "x", "supported": False}]})
        self.assertEqual(factcheck_verdict(pass_result), "pass")
        self.assertEqual(factcheck_verdict(fail_result), "fail")

    def test_mock_pipeline_saves_script(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "test.db"
            init_db(db_path)
            with session(db_path) as conn:
                conn.execute(
                    "INSERT INTO topics (topic_hash, title, source, url, score) VALUES (?, ?, ?, ?, ?)",
                    (topic_hash("Mock space topic"), "Mock space topic", "test", "https://example.com/source", 0.9),
                )
            with patch("reels.script.service.RUNS_DIR", Path(tmp) / "runs"):
                result = generate(
                    {
                        "id": 1,
                        "topic_hash": topic_hash("Mock space topic"),
                        "title": "Mock space topic",
                        "url": "https://example.com/source",
                    },
                    MockLLM(),
                    db_path=db_path,
                )
            self.assertEqual(result["verdict"], "pass")
            self.assertTrue(result["saved"])
            with session(db_path) as conn:
                count = conn.execute("SELECT COUNT(*) AS n FROM scripts").fetchone()["n"]
            self.assertEqual(count, 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
