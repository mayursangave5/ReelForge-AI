from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .styles import select_style


def generate_storyboard(
    package: dict[str, Any],
    timing: dict[str, Any],
    style: str | None = None,
    fps: int = 30,
) -> dict[str, Any]:
    """Generates a detailed 12-20 shot storyboard from script and audio timing data."""
    topic = timing.get("topic") or package.get("title_hi") or package.get("title", "")
    chosen_style = style or select_style(topic)
    scenes = timing.get("scenes") or package.get("scenes", [])
    total_duration_s = float(timing.get("total_s", 45.0))
    total_frames = int(round(total_duration_s * fps))

    shots: list[dict[str, Any]] = []
    current_frame = 0

    # Expand 4-6 broad script scenes into 12-16 dynamic shot cuts (every 2.5-3.5s)
    shot_index = 1
    for s_idx, scene in enumerate(scenes, 1):
        scene_duration_s = float(scene.get("duration_s", 7.0))
        narration = scene.get("narration_hi") or scene.get("narration", "")
        visual_desc = scene.get("visual_en") or scene.get("visual", topic)

        # Break each scene into 2-3 distinct camera cuts
        sub_shots_count = max(2, min(4, round(scene_duration_s / 3.0)))
        sub_dur_s = scene_duration_s / sub_shots_count

        for sub_i in range(sub_shots_count):
            sub_frames = int(round(sub_dur_s * fps))
            # Determine background and camera motion dynamically
            if "asteroid" in topic.lower() or chosen_style == "3d_cartoon":
                if shot_index in (1, 2):
                    bg = "deep_space"
                    cam = {"zoom": 1.25, "panY": -30, "durationFrames": sub_frames}
                elif shot_index in (3, 4):
                    bg = "earth_orbit"
                    cam = {"zoom": 1.15, "panX": 25, "durationFrames": sub_frames}
                elif shot_index in (5, 6):
                    bg = "city"
                    cam = {"zoom": 1.2, "shake": 4, "durationFrames": sub_frames}
                elif shot_index in (7, 8, 9):
                    bg = "impact_crater"
                    cam = {"zoom": 1.35, "shake": 15, "durationFrames": sub_frames}
                elif shot_index in (10, 11):
                    bg = "science"
                    cam = {"zoom": 1.05, "durationFrames": sub_frames}
                else:
                    bg = "earth_orbit"
                    cam = {"zoom": 1.2, "durationFrames": sub_frames}
            else:
                bg = "environment"
                cam = {"zoom": 1.0 + 0.15 * (shot_index % 3), "durationFrames": sub_frames}

            shots.append({
                "id": f"S{shot_index}",
                "index": shot_index,
                "sceneIndex": s_idx,
                "subIndex": sub_i + 1,
                "startFrame": current_frame,
                "durationFrames": sub_frames,
                "startSeconds": round(current_frame / fps, 3),
                "durationSeconds": round(sub_dur_s, 3),
                "narration": narration if sub_i == 0 else "",
                "visualPrompt": f"{visual_desc} (Shot {shot_index})",
                "background": bg,
                "camera": cam,
                "style": chosen_style,
            })
            current_frame += sub_frames
            shot_index += 1

    # Adjust last shot to match total frames
    if shots:
        diff = total_frames - sum(s["durationFrames"] for s in shots)
        shots[-1]["durationFrames"] = max(30, shots[-1]["durationFrames"] + diff)

    captions_data: list[dict[str, Any]] = []
    caption_lines = timing.get("caption_lines") or []
    for line in caption_lines:
        line_start = float(line.get("start", 0))
        line_end = float(line.get("end", 0))
        text = line.get("text", "")
        words = text.split()
        if not words:
            continue
        word_dur = max(0.12, (line_end - line_start) / len(words))
        for w_i, w in enumerate(words):
            w_start = line_start + w_i * word_dur
            w_end = min(line_end, w_start + word_dur)
            captions_data.append({
                "word": w,
                "start": round(w_start, 3),
                "end": round(w_end, 3),
            })

    storyboard = {
        "title": topic,
        "style": chosen_style,
        "fps": fps,
        "totalDurationSeconds": total_duration_s,
        "totalDurationFrames": total_frames,
        "shotCount": len(shots),
        "shots": shots,
        "captions": captions_data,
    }
    return storyboard
