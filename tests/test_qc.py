from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

from reels.video.qc import run_qc


class QualityControlTests(unittest.TestCase):
    def test_run_qc_handles_missing_file(self):
        res = run_qc(Path("non_existent_file.mp4"))
        self.assertFalse(res["passed"])
        self.assertEqual(res["score"], 0.0)
        self.assertIn("Video file does not exist", res["critical_failures"])

    @patch("reels.video.qc.probe_video")
    @patch("reels.video.qc.detect_audio_levels")
    @patch("reels.video.qc.detect_black_frames")
    @patch("reels.video.qc.detect_frozen_frames")
    def test_run_qc_scores_valid_video(
        self, mock_freeze, mock_black, mock_audio, mock_probe
    ):
        # Create a dummy file
        dummy_path = Path("tests/__pycache__/dummy.mp4")
        dummy_path.parent.mkdir(parents=True, exist_ok=True)
        dummy_path.write_bytes(b"dummy")

        mock_probe.return_value = {
            "streams": [
                {"codec_type": "video", "codec_name": "h264", "width": 1080, "height": 1920, "duration": "48.0"},
                {"codec_type": "audio", "codec_name": "aac", "duration": "48.0"},
            ],
            "format": {"duration": "48.0"},
        }
        mock_audio.return_value = {"mean_volume_db": -22.0, "max_volume_db": -1.2}
        mock_black.return_value = []
        mock_freeze.return_value = []

        try:
            res = run_qc(dummy_path, expected_min_dur=30.0, expected_max_dur=60.0)
            self.assertTrue(res["passed"])
            self.assertGreaterEqual(res["score"], 85.0)
            self.assertEqual(len(res["critical_failures"]), 0)
        finally:
            dummy_path.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
