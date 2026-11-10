from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from reels.tts.service import build_voiceover, narration_texts
from reels.tts.subtitles import build_captions, format_time, to_srt


def words(spec):
    return [
        {"text": text, "start": start, "end": end} for text, start, end in spec
    ]


class SubtitleTests(unittest.TestCase):
    def test_format_time(self):
        self.assertEqual(format_time(0.1), "00:00:00,100")
        self.assertEqual(format_time(3725.5), "01:02:05,500")
        self.assertEqual(format_time(-1), "00:00:00,000")

    def test_captions_respect_limits_and_keep_all_words(self):
        tokens = [(f"शब्द{i}", i * 0.3, i * 0.3 + 0.25) for i in range(20)]
        captions = build_captions(words(tokens))
        self.assertGreater(len(captions), 1)
        for caption in captions:
            self.assertLessEqual(len(caption["text"]), 42)
            self.assertLessEqual(caption["end"] - caption["start"], 4.0)
        joined = " ".join(c["text"] for c in captions)
        self.assertEqual(joined, " ".join(t[0] for t in tokens))

    def test_caption_breaks_at_sentence_end(self):
        tokens = [
            ("यह", 0.0, 0.3),
            ("एक", 0.3, 0.6),
            ("वाक्य", 0.6, 1.0),
            ("है।", 1.0, 1.4),
            ("अगला", 1.6, 2.0),
        ]
        captions = build_captions(words(tokens))
        self.assertEqual(len(captions), 2)
        self.assertTrue(captions[0]["text"].endswith("है।"))
        self.assertEqual(captions[1]["text"], "अगला")

    def test_srt_format(self):
        captions = [{"start": 0.1, "end": 2.5, "text": "नमस्ते दोस्तों"}]
        srt = to_srt(captions)
        self.assertIn("1\n00:00:00,100 --> 00:00:02,500\nनमस्ते दोस्तों", srt)


class VoiceoverTests(unittest.TestCase):
    def package(self):
        return {
            "hook_hi": "क्या आप जानते हैं?",
            "scenes": [
                {"narration_hi": "पहला दृश्य यहाँ है।", "visual_en": "space scene"},
                {"narration_hi": "दूसरा दृश्य यहाँ है।", "visual_en": "earth scene"},
            ],
        }

    def test_narration_texts_prepends_hook_once(self):
        texts = narration_texts(self.package())
        self.assertTrue(texts[0].startswith("क्या आप जानते हैं?"))
        self.assertEqual(texts[1], "दूसरा दृश्य यहाँ है।")

        containing = self.package()
        containing["scenes"][0]["narration_hi"] = (
            "क्या आप जानते हैं? पहला दृश्य यहाँ है।"
        )
        self.assertEqual(
            narration_texts(containing)[0], "क्या आप जानते हैं? पहला दृश्य यहाँ है।"
        )

    def test_offsets_follow_scene_durations_and_gap(self):
        durations = {"scene_1.mp3": 1.0, "scene_2.mp3": 2.0, "audio.mp3": 3.3}

        def fake_synth(text, voice, rate):
            return b"audio", words(
                [("नमस्ते", 0.1, 0.5), ("दोस्तों", 0.6, 0.9)]
            )

        def fake_probe(path):
            return durations[path.name]

        def fake_concat(parts, out):
            out.write_bytes(b"joined")

        def fake_silence(path, seconds):
            path.write_bytes(b"silence")

        with tempfile.TemporaryDirectory() as tmp:
            result = build_voiceover(
                self.package(),
                voice="hi-IN-MadhurNeural",
                rate="-4%",
                script_id=7,
                title="टेस्ट",
                out_dir=Path(tmp) / "run",
                synth=fake_synth,
                probe=fake_probe,
                concat=fake_concat,
                silence=fake_silence,
            )
            timing = result["timing"]
            self.assertEqual(timing["total_s"], 3.3)
            self.assertEqual(timing["scenes"][1]["start_s"], 1.3)
            self.assertTrue(Path(result["srt"]).exists())
            self.assertTrue(Path(result["audio"]).exists())
            snapshot = json.loads(
                (Path(result["run_dir"]) / "script.json").read_text(encoding="utf-8")
            )
            self.assertEqual(snapshot["script_id"], 7)

            srt = Path(result["srt"]).read_text(encoding="utf-8")
            self.assertIn("00:00:00,100", srt)
            self.assertIn("00:00:02,200", srt)


if __name__ == "__main__":
    unittest.main()
