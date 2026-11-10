from __future__ import annotations

from pathlib import Path
from typing import Any

FONT_CANDIDATES = (
    Path(r"C:\Windows\Fonts\Nirmala.ttc"),
    Path(r"C:\Windows\Fonts\mangal.ttf"),
)


def ff_path(path: Path) -> str:
    return str(path).replace("\\", "/").replace(":", "\\:")


def subtitle_font() -> Path:
    for candidate in FONT_CANDIDATES:
        if candidate.is_file():
            return candidate
    raise FileNotFoundError("No Devanagari font found (Nirmala UI or Mangal).")


def wrap_caption(text: str, max_chars: int = 26) -> list[str]:
    lines: list[str] = []
    current = ""
    for word in text.split():
        candidate = f"{current} {word}".strip()
        if current and len(candidate) > max_chars:
            lines.append(current)
            current = word
        else:
            current = candidate
    if current:
        lines.append(current)
    if len(lines) > 2:
        words = text.split()
        best, best_diff = 1, len(text)
        for i in range(1, len(words)):
            left = " ".join(words[:i])
            diff = abs(len(left) - (len(text) - len(left)))
            if diff < best_diff:
                best, best_diff = i, diff
        lines = [" ".join(words[:best]), " ".join(words[best:])]
    return lines


def scene_filter(duration: float, index: int) -> str:
    frames = max(1, round(duration * 30))
    zoom_rate = 0.10 / frames
    drift = 18 if index % 2 else -18
    fade = min(0.25, duration / 4)
    return (
        "scale=1080:1920:force_original_aspect_ratio=increase,"
        "crop=1080:1920,"
        f"zoompan=z='min(1.12,1+{zoom_rate:.6f}*on)'"
        f":x='iw/2-(iw/zoom/2)+{drift}*on/{frames}'"
        f":y='ih/2-(ih/zoom/2)'"
        ":d=1:s=1080x1920:fps=30,"
        f"fade=t=in:st=0:d={fade:.2f},"
        f"fade=t=out:st={max(0.0, duration - fade):.2f}:d={fade:.2f},"
        "format=yuv420p"
    )


def music_filter(duration: float) -> str:
    fade_out = max(0.0, duration - 2.0)
    return (
        "[0:a]volume=0.30[a0];"
        "[1:a]volume=0.22[a1];"
        "[2:a]volume=0.16[a2];"
        "[3:a]volume=0.10[a3];"
        "[a0][a1][a2][a3]amix=inputs=4:normalize=0,"
        "lowpass=f=1200,aecho=0.8:0.7:120:0.25,"
        "tremolo=f=0.12:d=0.5,volume=0.5,"
        "afade=t=in:st=0:d=1.5,"
        f"afade=t=out:st={fade_out:.2f}:d=2[m]"
    )


def drawtext_chain(
    captions: list[dict[str, Any]],
    caption_files: list[Path],
    font: Path,
    y_offset: int = 340,
) -> str:
    filters = []
    for caption, textfile in zip(captions, caption_files):
        start = max(0.0, caption["start"])
        end = caption["end"]
        filters.append(
            f"drawtext=fontfile='{ff_path(font)}'"
            f":textfile='{ff_path(textfile)}'"
            ":fontcolor=white:fontsize=54:line_spacing=10"
            ":borderw=4:bordercolor=black@0.9"
            ":box=1:boxcolor=black@0.30:boxborderw=18"
            ":x=(w-text_w)/2:y=h-text_h-" + str(y_offset)
            + f":enable='between(t\\,{start:.3f}\\,{end:.3f})'"
        )
    return ",".join(filters)


def mix_filter() -> str:
    return (
        "[1:a]aresample=44100,volume=1.0[voice];"
        "[2:a]volume=0.45[music];"
        "[voice][music]amix=inputs=2:duration=first:dropout_transition=0,"
        "alimiter=limit=0.95[a]"
    )
