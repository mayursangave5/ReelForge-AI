from __future__ import annotations

import unittest
from reels.video.storyboard import generate_storyboard


class StoryboardTests(unittest.TestCase):
    def test_generate_storyboard_expands_scenes_into_multiple_shots(self):
        package = {
            "title": "What Would Happen If an Asteroid Hit Earth?",
            "scenes": [
                {"narration": "A massive asteroid approaches Earth.", "duration_s": 8.0, "visual_en": "Asteroid in space"},
                {"narration": "It enters the atmosphere in a fireball.", "duration_s": 9.0, "visual_en": "Atmospheric fireball"},
                {"narration": "Impact causes immense destruction.", "duration_s": 10.0, "visual_en": "Ground zero crater"},
                {"narration": "Planetary defense can save us.", "duration_s": 9.0, "visual_en": "DART mission"},
            ],
        }
        timing = {
            "topic": "Asteroid Impact",
            "total_s": 36.0,
            "scenes": package["scenes"],
            "caption_lines": [
                {"text": "A massive asteroid approaches Earth", "start": 0.5, "end": 4.0},
            ],
        }

        storyboard = generate_storyboard(package, timing, style="3d_cartoon", fps=30)
        self.assertEqual(storyboard["style"], "3d_cartoon")
        self.assertGreaterEqual(storyboard["shotCount"], 10)
        self.assertEqual(len(storyboard["shots"]), storyboard["shotCount"])
        self.assertEqual(storyboard["totalDurationFrames"], 36 * 30)

        # Check shot properties
        for shot in storyboard["shots"]:
            self.assertIn("id", shot)
            self.assertIn("startFrame", shot)
            self.assertIn("durationFrames", shot)
            self.assertIn("camera", shot)
            self.assertIn("background", shot)


if __name__ == "__main__":
    unittest.main()
