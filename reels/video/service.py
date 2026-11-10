from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from ..config import DB_PATH, PREVIEWS_DIR, ROOT, VIDEOS_DIR, settings
from ..db import session
from .ffmpeg import (
    drawtext_chain,
    mix_filter,
    music_filter,
    scene_filter,
    subtitle_font,
    wrap_caption,
)
from .images import fetch_image, visual_prompt
from .qc import run_qc
from .storyboard import generate_storyboard
from .styles import select_style

FALLBACK_COLORS = ("0x101a33", "0x1a1033", "0x0f2233", "0x241a10", "0x102233")


class VideoError(RuntimeError):
    pass


def _run(args: list[str], timeout: int = 900) -> None:
    subprocess.run(
        args, check=True, timeout=timeout, capture_output=True, text=True
    )


def make_music(dest: Path, duration: float) -> None:
    notes = (110.0, 164.81, 220.0, 329.63)
    cmd = [str(settings.ffmpeg()), "-y", "-v", "error"]
    for note in notes:
        cmd += ["-f", "lavfi", "-i", f"sine=frequency={note}:duration={duration:.3f}"]
    cmd += ["-filter_complex", music_filter(duration), "-map", "[m]"]
    cmd += ["-c:a", "libmp3lame", "-b:a", "96k", str(dest)]
    _run(cmd)


def fallback_image(dest: Path, index: int) -> None:
    color = FALLBACK_COLORS[(index - 1) % len(FALLBACK_COLORS)]
    _run(
        [
            str(settings.ffmpeg()),
            "-y",
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            f"color=c={color}:s=1080x1920",
            "-frames:v",
            "1",
            "-vf",
            "noise=alls=8:allf=t+u,vignette=PI/4",
            str(dest),
        ]
    )


def render_scene(image: Path, duration: float, index: int, dest: Path) -> None:
    _run(
        [
            str(settings.ffmpeg()),
            "-y",
            "-v",
            "error",
            "-loop",
            "1",
            "-framerate",
            "30",
            "-i",
            str(image),
            "-t",
            f"{duration:.3f}",
            "-vf",
            scene_filter(duration, index),
            "-an",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "20",
            str(dest),
        ]
    )


def concat_segments(segments: list[Path], dest: Path) -> None:
    list_file = dest.with_suffix(".txt")
    list_file.write_text(
        "\n".join(f"file '{seg.resolve().as_posix()}'" for seg in segments),
        encoding="utf-8",
    )
    try:
        _run(
            [
                str(settings.ffmpeg()),
                "-y",
                "-v",
                "error",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(list_file),
                "-c",
                "copy",
                str(dest),
            ]
        )
    finally:
        list_file.unlink(missing_ok=True)


def finalize(
    visuals: Path,
    voice: Path,
    music: Path,
    captions: list[dict[str, Any]],
    caption_files: list[Path],
    total: float,
    dest: Path,
) -> None:
    font = subtitle_font()
    chain = drawtext_chain(captions, caption_files, font)
    graph = f"[0:v]{chain}[v];{mix_filter()}"
    _run(
        [
            str(settings.ffmpeg()),
            "-y",
            "-v",
            "error",
            "-i",
            str(visuals),
            "-i",
            str(voice),
            "-i",
            str(music),
            "-filter_complex",
            graph,
            "-map",
            "[v]",
            "-map",
            "[a]",
            "-t",
            f"{total:.3f}",
            "-c:v",
            "libx264",
            "-preset",
            "medium",
            "-crf",
            "20",
            "-pix_fmt",
            "yuv420p",
            "-r",
            "30",
            "-c:a",
            "aac",
            "-b:a",
            "160k",
            "-movflags",
            "+faststart",
            str(dest),
        ]
    )


def render_remotion(
    timeline_data: dict[str, Any],
    dest: Path,
    composition: str = "Reel",
    timeout: int = 900,
) -> None:
    anim_dir = ROOT / "animation"
    props_json = json.dumps(timeline_data, ensure_ascii=False)
    # Write to a props file to avoid Windows command line character limits
    props_file = anim_dir / "out" / f"props_{dest.stem}.json"
    props_file.parent.mkdir(parents=True, exist_ok=True)
    props_file.write_text(props_json, encoding="utf-8")

    npx_cmd = "npx.cmd" if sys.platform == "win32" else "npx"
    cmd = [
        npx_cmd,
        "remotion",
        "render",
        "src/index.ts",
        composition,
        str(dest.resolve()),
        f"--props={props_file.resolve()}",
        "--concurrency=2",
        "--gl=angle",
    ]
    try:
        res = subprocess.run(
            cmd,
            cwd=anim_dir,
            check=True,
            timeout=timeout,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as exc:
        raise VideoError(f"Remotion render failed: {exc.stderr or exc.stdout}") from exc
    finally:
        props_file.unlink(missing_ok=True)


def render(
    voice_run: Path,
    out_path: Path | None = None,
    db_path: Path = DB_PATH,
    style: str | None = None,
    engine: str = "remotion",
) -> dict[str, Any]:
    voice_run = Path(voice_run)
    timing_path = voice_run / "timing.json"
    snapshot_path = voice_run / "script.json"
    if not timing_path.is_file() or not snapshot_path.is_file():
        raise VideoError(f"{voice_run} is not a voiceover run (missing timing.json).")

    timing = json.loads(timing_path.read_text(encoding="utf-8"))
    snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    package = snapshot["package"]
    script_id = snapshot.get("script_id")
    topic = timing.get("topic") or package.get("title_hi") or package.get("title", "")
    chosen_style = style or select_style(topic)
    captions = timing.get("caption_lines") or []
    if not captions:
        raise VideoError(
            "timing.json has no caption_lines. Re-run `python -m reels voice`."
        )

    total = float(timing["total_s"])
    dest = Path(out_path) if out_path else VIDEOS_DIR / f"reel_{voice_run.name}.mp4"
    dest.parent.mkdir(parents=True, exist_ok=True)

    # 1. Generate Storyboard
    storyboard = generate_storyboard(package, timing, style=chosen_style)
    storyboard_file = voice_run / "storyboard.json"
    storyboard_file.write_text(json.dumps(storyboard, ensure_ascii=False, indent=2), encoding="utf-8")

    remotion_success = False
    if engine == "remotion":
        try:
            # Build Remotion timeline props
            timeline_props = {
                "title": topic,
                "topic": topic,
                "style": chosen_style,
                "fps": 30,
                "width": settings.video_width,
                "height": settings.video_height,
                "totalDurationFrames": storyboard["totalDurationFrames"],
                "shots": storyboard["shots"],
                "captions": storyboard["captions"],
                "audio": {
                    "voiceUrl": str((voice_run / "audio.mp3").resolve().as_posix()),
                },
            }
            # Add music if exists
            music_file = voice_run / "music.mp3"
            if not music_file.exists():
                make_music(music_file, total)
            timeline_props["audio"]["musicUrl"] = str(music_file.resolve().as_posix())

            composition_name = "AsteroidImpact" if "asteroid" in topic.lower() else "Reel"
            render_remotion(timeline_props, dest, composition=composition_name)
            remotion_success = dest.exists() and dest.stat().st_size > 50_000
        except Exception:
            remotion_success = False

    # Fallback to FFmpeg pipeline if Remotion was not requested or failed
    segments: list[Path] = []
    fetched = cached = 0
    music = voice_run / "music.mp3"
    if not remotion_success:
        if not music.exists():
            make_music(music, total)

        for scene in timing["scenes"]:
            index = int(scene["index"])
            duration = float(scene["duration_s"])
            image = voice_run / f"scene_{index}.jpg"
            if image.exists():
                cached += 1
            else:
                prompt = visual_prompt(package["scenes"][index - 1], timing.get("topic", ""))
                seed = abs(hash((voice_run.name, index))) % 1_000_000
                if fetch_image(prompt, image, seed):
                    fetched += 1
                else:
                    fallback_image(image, index)
            segment = voice_run / f"segment_{index}.mp4"
            render_scene(image, duration, index, segment)
            segments.append(segment)

        visuals = voice_run / "visuals.mp4"
        concat_segments(segments, visuals)

        caption_files: list[Path] = []
        for index, caption in enumerate(captions, 1):
            path = voice_run / f"cap_{index:02d}.txt"
            path.write_text("\n".join(wrap_caption(caption["text"])), encoding="utf-8")
            caption_files.append(path)

        finalize(
            visuals,
            voice_run / "audio.mp3",
            music,
            captions,
            caption_files,
            total,
            dest,
        )

    # Generate Thumbnail
    thumbnail = PREVIEWS_DIR / f"{dest.stem}_thumb.jpg"
    thumbnail.parent.mkdir(parents=True, exist_ok=True)
    _run(
        [
            str(settings.ffmpeg()),
            "-y",
            "-v",
            "error",
            "-ss",
            "2",
            "-i",
            str(dest),
            "-frames:v",
            "1",
            "-q:v",
            "3",
            str(thumbnail),
        ]
    )

    # Automated Quality Control
    qc_result = run_qc(dest)
    qc_score = qc_result["score"]
    qc_json = json.dumps(qc_result, ensure_ascii=False)

    with session(db_path) as conn:
        conn.execute(
            "INSERT INTO videos (script_id, run_id, path, duration_s, width, height, style, quality_score, quality_report_json, status) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'rendered') "
            "ON CONFLICT(run_id) DO UPDATE SET path = excluded.path, "
            "duration_s = excluded.duration_s, style = excluded.style, "
            "quality_score = excluded.quality_score, quality_report_json = excluded.quality_report_json, status = 'rendered'",
            (
                script_id,
                voice_run.name,
                str(dest),
                total,
                settings.video_width,
                settings.video_height,
                chosen_style,
                qc_score,
                qc_json,
            ),
        )

    return {
        "video": str(dest),
        "duration_s": total,
        "scenes": len(storyboard["shots"]) if remotion_success else len(segments),
        "style": chosen_style,
        "engine": "remotion" if remotion_success else "ffmpeg",
        "quality_score": qc_score,
        "quality_report": qc_result,
        "images_fetched": fetched,
        "images_cached": cached,
        "images_fallback": (len(segments) - fetched - cached) if segments else 0,
        "music": str(music),
        "thumbnail": str(thumbnail),
        "size_mb": round(dest.stat().st_size / (1024**2), 1),
    }
