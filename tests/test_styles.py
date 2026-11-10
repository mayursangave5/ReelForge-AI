from __future__ import annotations

import unittest
from reels.video.styles import STYLES, list_styles, select_style


class StylesTests(unittest.TestCase):
    def test_styles_has_five_supported_styles(self):
        self.assertIn("3d_cartoon", STYLES)
        self.assertIn("2d_colorful", STYLES)
        self.assertIn("anime", STYLES)
        self.assertIn("stick_figure", STYLES)
        self.assertIn("educational_motion", STYLES)
        self.assertEqual(len(STYLES), 5)

    def test_select_style_detects_3d_cartoon(self):
        style = select_style("What would happen if a massive asteroid hit Earth?")
        self.assertEqual(style, "3d_cartoon")

    def test_select_style_detects_stick_figure(self):
        style = select_style("What if you could rewind 10 seconds anytime?")
        self.assertEqual(style, "stick_figure")

    def test_select_style_detects_educational(self):
        style = select_style("How to calculate the trajectory formula with AI algorithm?")
        self.assertEqual(style, "educational_motion")

    def test_select_style_detects_anime(self):
        style = select_style("Who is the fastest ninja in an intense battle?")
        self.assertEqual(style, "anime")

    def test_select_style_detects_2d_colorful(self):
        style = select_style("How will human civilization and cells evolve in the future?")
        self.assertEqual(style, "2d_colorful")

    def test_list_styles_returns_metadata(self):
        styles = list_styles()
        self.assertEqual(len(styles), 5)
        self.assertTrue(all("name" in s and "description" in s for s in styles))


if __name__ == "__main__":
    unittest.main()
