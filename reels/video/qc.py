from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from typing import Any

from ..config import settings


class QualityControlError(RuntimeError):
    pass


def probe_video(path: Path) -> dict[str, Any]:
    """Inspects video and audio stream metadata using ffprobe."""
    ffprobe = str(settings.ffprobe())
    cmd = [
        ffprobe,
        "-v",
        "error",
        "-show_entries",
        "format=duration,size,bit_rate:stream=index,codec_type,codec_name,width,height,r_frame_rate,duration",
        "-of",
        "json",
        str(path),
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    if res.returncode != 0:
        raise QualityControlError(f"ffprobe failed: {res.stderr}")
    return json.loads(res.stdout or "{}")


def detect_black_frames(path: Path, max_black_duration: float = 0.5) -> list[dict[str, float]]:
    """Detects black frames using FFmpeg blackdetect."""
    ffmpeg = str(settings.ffmpeg())
    cmd = [
        ffmpeg,
        "-v",
        "info",
        "-i",
        str(path),
        "-vf",
        "blackdetect=d=0.3:pix_th=0.10",
        "-an",
        "-f",
        "null",
        "-",
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, timeout=90)
    output = res.stderr or ""
    black_intervals = []
    for match in re.finditer(r"black_start:([0-9.]+)\s+black_end:([0-9.]+)\s+black_duration:([0-9.]+)", output):
        start = float(match.group(1))
        end = float(match.group(2))
        dur = float(match.group(3))
        if dur >= max_black_duration:
            black_intervals.append({"start": start, "end": end, "duration": dur})
    return black_intervals


def detect_frozen_frames(path: Path, max_freeze_duration: float = 3.0) -> list[dict[str, float]]:
    """Detects frozen frames (slideshow detection) using FFmpeg freezedetect."""
    ffmpeg = str(settings.ffmpeg())
    cmd = [
        ffmpeg,
        "-v",
        "info",
        "-i",
        str(path),
        "-vf",
        "freezedetect=n=0.003:d=2.0",
        "-an",
        "-f",
        "null",
        "-",
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, timeout=90)
    output = res.stderr or ""
    freeze_intervals = []
    for match in re.finditer(r"lavfi.freezedetect.freeze_start:\s*([0-9.]+)", output):
        start = float(match.group(1))
        freeze_intervals.append({"start": start, "duration": 2.0})
    return freeze_intervals


def detect_audio_levels(path: Path) -> dict[str, float]:
    """Detects audio volume levels using FFmpeg volumedetect."""
    ffmpeg = str(settings.ffmpeg())
    cmd = [
        ffmpeg,
        "-v",
        "info",
        "-i",
        str(path),
        "-af",
        "volumedetect",
        "-vn",
        "-f",
        "null",
        "-",
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    output = res.stderr or ""
    mean_match = re.search(r"mean_volume:\s*(-?[0-9.]+)\s*dB", output)
    max_match = re.search(r"max_volume:\s*(-?[0-9.]+)\s*dB", output)
    mean_vol = float(mean_match.group(1)) if mean_match else -99.0
    max_vol = float(max_match.group(1)) if max_match else -99.0
    return {"mean_volume_db": mean_vol, "max_volume_db": max_vol}


def run_qc(video_path: Path, expected_min_dur: float = 30.0, expected_max_dur: float = 65.0) -> dict[str, Any]:
    """Runs automated quality control and produces a QC score and report."""
    video_path = Path(video_path)
    if not video_path.exists():
        return {
            "score": 0.0,
            "passed": False,
            "status": "failed",
            "critical_failures": ["Video file does not exist"],
            "warnings": [],
            "metrics": {},
        }

    probe = probe_video(video_path)
    streams = probe.get("streams", [])
    format_info = probe.get("format", {})

    v_stream = next((s for s in streams if s.get("codec_type") == "video"), None)
    a_stream = next((s for s in streams if s.get("codec_type") == "audio"), None)

    critical_failures: list[str] = []
    warnings: list[str] = []
    score = 0.0

    # 1. Video Stream Checks
    if not v_stream:
        critical_failures.append("Missing video stream")
    else:
        width = int(v_stream.get("width", 0))
        height = int(v_stream.get("height", 0))
        duration = float(v_stream.get("duration") or format_info.get("duration") or 0.0)

        # Resolution (1080x1920)
        if width == 1080 and height == 1920:
            score += 20.0
        elif height > width and round(height / width, 2) == 1.78:
            score += 15.0
            warnings.append(f"Vertical resolution is {width}x{height} instead of standard 1080x1920")
        else:
            critical_failures.append(f"Invalid resolution/aspect ratio: {width}x{height} (not vertical 9:16)")

        # Duration
        if expected_min_dur <= duration <= expected_max_dur:
            score += 20.0
        elif duration > 0:
            score += 10.0
            warnings.append(f"Duration {duration:.1f}s outside target [{expected_min_dur}-{expected_max_dur}s]")
        else:
            critical_failures.append("Video duration is zero or undetectable")

    # 2. Audio Stream Checks
    if not a_stream:
        critical_failures.append("Missing audio stream")
    else:
        audio_levels = detect_audio_levels(video_path)
        mean_vol = audio_levels["mean_volume_db"]
        max_vol = audio_levels["max_volume_db"]

        if max_vol > -90.0 and mean_vol > -60.0:
            score += 20.0
        else:
            critical_failures.append(f"Audio is silent or corrupted (mean: {mean_vol}dB, max: {max_vol}dB)")

    # 3. Black Frame Detection
    black_intervals = detect_black_frames(video_path)
    if not black_intervals:
        score += 15.0
    else:
        warnings.append(f"Detected {len(black_intervals)} black screen interval(s)")
        score += max(0.0, 15.0 - len(black_intervals) * 5.0)

    # 4. Movement / Freeze Detection (Slideshow check)
    frozen_intervals = detect_frozen_frames(video_path)
    if not frozen_intervals:
        score += 25.0
    elif len(frozen_intervals) <= 1:
        score += 15.0
        warnings.append("Minor static pause detected")
    else:
        warnings.append(f"Detected {len(frozen_intervals)} extended static periods - ensure full animation")
        score += 5.0

    passed = len(critical_failures) == 0 and score >= 75.0

    return {
        "score": round(score, 1),
        "passed": passed,
        "status": "passed" if passed else "failed",
        "critical_failures": critical_failures,
        "warnings": warnings,
        "metrics": {
            "width": v_stream.get("width") if v_stream else 0,
            "height": v_stream.get("height") if v_stream else 0,
            "duration_s": float(v_stream.get("duration") or format_info.get("duration") or 0.0),
            "video_codec": v_stream.get("codec_name") if v_stream else None,
            "audio_codec": a_stream.get("codec_name") if a_stream else None,
            "black_intervals": len(black_intervals),
            "frozen_intervals": len(frozen_intervals),
        },
    }
