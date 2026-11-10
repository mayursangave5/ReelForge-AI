from __future__ import annotations

import json
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from ..config import DB_PATH, PREVIEWS_DIR, RUNS_DIR, settings
from ..db import session
from .edge import hindi_voices, synthesize
from .subtitles import build_captions, to_srt

GAP_S = 0.3
SAMPLE_TEXT = (
    "नमस्ते दोस्तों! आज हम बात करेंगे भारत के अंतरिक्ष मिशन की। "
    "यह कहानी आपको हैरान कर देगी, तो अंत तक ज़रूर देखिए।"
)


def load_script(script_id: int | None = None, db_path: Path = DB_PATH) -> dict[str, Any]:
    query = (
        "SELECT s.id, s.topic_id, s.scenes_json, t.title "
        "FROM scripts s LEFT JOIN topics t ON t.id = s.topic_id "
    )
    with session(db_path) as conn:
        if script_id is None:
            row = conn.execute(query + "ORDER BY s.id DESC LIMIT 1").fetchone()
        else:
            row = conn.execute(query + "WHERE s.id = ?", (script_id,)).fetchone()
    if row is None:
        raise LookupError(
            "No script found. Run `python -m reels script` first or pass --script-id."
        )
    return {
        "id": row["id"],
        "topic_id": row["topic_id"],
        "title": row["title"] or "",
        "package": json.loads(row["scenes_json"]),
    }


def narration_texts(package: dict[str, Any]) -> list[str]:
    texts = [scene["narration_hi"].strip() for scene in package["scenes"]]
    hook = (package.get("hook_hi") or "").strip()
    if hook and hook not in texts[0]:
        texts[0] = f"{hook} {texts[0]}"
    return texts


def _probe(path: Path) -> float:
    out = subprocess.run(
        [
            str(settings.ffprobe()),
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=nw=1:nk=1",
            str(path),
        ],
        capture_output=True,
        text=True,
        timeout=60,
        check=True,
    )
    return float(out.stdout.strip())


def _silence(path: Path, seconds: float) -> None:
    subprocess.run(
        [
            str(settings.ffmpeg()),
            "-y",
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            "anullsrc=r=24000:cl=mono",
            "-t",
            f"{seconds}",
            "-c:a",
            "libmp3lame",
            "-b:a",
            "48k",
            str(path),
        ],
        check=True,
        timeout=60,
    )


def _concat(parts: list[Path], out: Path) -> None:
    list_file = out.with_suffix(".txt")
    list_file.write_text(
        "\n".join(f"file '{part.resolve().as_posix()}'" for part in parts),
        encoding="utf-8",
    )
    try:
        subprocess.run(
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
                "-c:a",
                "libmp3lame",
                "-b:a",
                "96k",
                "-ar",
                "24000",
                "-ac",
                "1",
                str(out),
            ],
            check=True,
            timeout=300,
        )
    finally:
        list_file.unlink(missing_ok=True)


def _stamp() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def build_voiceover(
    package: dict[str, Any],
    voice: str,
    rate: str,
    script_id: int | None = None,
    title: str = "",
    out_dir: Path | None = None,
    synth: Callable[..., tuple[bytes, list[dict]]] | None = None,
    probe: Callable[[Path], float] | None = None,
    concat: Callable[[list[Path], Path], None] | None = None,
    silence: Callable[[Path, float], None] | None = None,
) -> dict[str, Any]:
    synth = synth or synthesize
    probe = probe or _probe
    concat = concat or _concat
    silence = silence or _silence

    texts = narration_texts(package)
    run_dir = Path(out_dir) if out_dir else RUNS_DIR / f"{_stamp()}_voice{script_id or ''}"
    run_dir.mkdir(parents=True, exist_ok=True)

    gap = run_dir / "gap.mp3"
    silence(gap, GAP_S)

    parts: list[Path] = []
    scenes: list[dict[str, Any]] = []
    words: list[dict[str, Any]] = []
    cursor = 0.0

    for index, text in enumerate(texts, 1):
        audio, boundaries = synth(text, voice, rate)
        scene_path = run_dir / f"scene_{index}.mp3"
        scene_path.write_bytes(audio)
        duration = probe(scene_path)
        scenes.append(
            {
                "index": index,
                "text": text,
                "file": scene_path.name,
                "start_s": round(cursor, 3),
                "duration_s": round(duration, 3),
            }
        )
        for boundary in boundaries:
            words.append(
                {
                    "text": boundary["text"],
                    "start": round(boundary["start"] + cursor, 3),
                    "end": round(boundary["end"] + cursor, 3),
                }
            )
        parts.append(scene_path)
        cursor += duration
        if index < len(texts):
            parts.append(gap)
            cursor += GAP_S

    audio_path = run_dir / "audio.mp3"
    concat(parts, audio_path)
    total = probe(audio_path)

    captions = build_captions(words)
    srt_path = run_dir / "captions.srt"
    srt_path.write_text(to_srt(captions), encoding="utf-8")

    timing = {
        "script_id": script_id,
        "topic": title,
        "voice": voice,
        "rate": rate,
        "gap_s": GAP_S,
        "total_s": round(total, 3),
        "audio": audio_path.name,
        "captions": len(captions),
        "caption_lines": captions,
        "scenes": scenes,
    }
    timing_path = run_dir / "timing.json"
    timing_path.write_text(
        json.dumps(timing, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (run_dir / "script.json").write_text(
        json.dumps(
            {"script_id": script_id, "topic": title, "package": package},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    return {
        "run_dir": str(run_dir),
        "audio": str(audio_path),
        "srt": str(srt_path),
        "timing": timing,
    }


def voice_lab(
    text: str = SAMPLE_TEXT,
    voices: list[str] | None = None,
    rate: str = "-4%",
    out_dir: Path | None = None,
    synth: Callable[..., tuple[bytes, list[dict]]] | None = None,
    probe: Callable[[Path], float] | None = None,
) -> list[dict[str, Any]]:
    synth = synth or synthesize
    probe = probe or _probe
    voices = voices or [v["ShortName"] for v in hindi_voices()]
    out_dir = Path(out_dir) if out_dir else PREVIEWS_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = _stamp()

    results: list[dict[str, Any]] = []
    for voice in voices:
        audio, boundaries = synth(text, voice, rate)
        mp3 = out_dir / f"voice_{voice}_{stamp}.mp3"
        mp3.write_bytes(audio)
        captions = build_captions(boundaries)
        srt = mp3.with_suffix(".srt")
        srt.write_text(to_srt(captions), encoding="utf-8")
        results.append(
            {
                "voice": voice,
                "audio": str(mp3),
                "srt": str(srt),
                "duration_s": round(probe(mp3), 3),
                "captions": len(captions),
            }
        )
    return results
