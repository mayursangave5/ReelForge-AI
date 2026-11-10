from __future__ import annotations

import unittest
from pathlib import Path

from reels.video.ffmpeg import (
    drawtext_chain,
    music_filter,
    scene_filter,
    wrap_caption,
)
from reels.video.images import image_url, visual_prompt


class CaptionTests(unittest.TestCase):
    def test_wrap_is_two_lines_max(self):
        text = "क्या आप जानते हैं कि अंतरिक्ष में करीब 10 हजार सैटेलाइट्स हैं"
        lines = wrap_caption(text)
        self.assertLessEqual(len(lines), 2)
        self.assertEqual(" ".join(lines), text)
        for line in lines:
            self.assertLessEqual(len(line), 32)

    def test_wrap_keeps_short_text_on_one_line(self):
        self.assertEqual(wrap_caption("नमस्ते दोस्तों"), ["नमस्ते दोस्तों"])

    def test_drawtext_chain_has_one_filter_per_caption(self):
        captions = [
            {"start": 0.1, "end": 2.5, "text": "एक"},
            {"start": 2.6, "end": 4.0, "text": "दो"},
        ]
        files = [Path("cap_01.txt"), Path("cap_02.txt")]
        chain = drawtext_chain(captions, files, Path(r"C:\Windows\Fonts\Nirmala.ttc"))
        self.assertEqual(chain.count("drawtext="), 2)
        self.assertIn("between(t\\,0.100\\,2.500)", chain)
        self.assertIn("C\\:/Windows/Fonts/Nirmala.ttc", chain)


class FilterTests(unittest.TestCase):
    def test_scene_filter_has_motion_and_fades(self):
        graph = scene_filter(9.0, 2)
        self.assertIn("zoompan", graph)
        self.assertIn("fade=t=in:st=0", graph)
        self.assertIn("fade=t=out:st=8.75", graph)
        self.assertIn("fps=30", graph)

    def test_music_filter_has_fades(self):
        graph = music_filter(57.7)
        self.assertTrue(graph.endswith("[m]"))
        self.assertIn("afade=t=out:st=55.70", graph)

    def test_image_url(self):
        prompt = visual_prompt({"visual_en": "space debris"}, "topic")
        url = image_url(prompt, 42, 1080, 1920)
        self.assertIn("width=1080&height=1920", url)
        self.assertIn("seed=42", url)
        self.assertIn("space%20debris", url)


if __name__ == "__main__":
    unittest.main()
