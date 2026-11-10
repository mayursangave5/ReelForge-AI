from __future__ import annotations

from typing import Any

MAX_CHARS = 42
MAX_SECONDS = 4.0
_SENTENCE_END = ("।", "?", "!", ".")


def build_captions(
    words: list[dict[str, Any]],
    max_chars: int = MAX_CHARS,
    max_seconds: float = MAX_SECONDS,
) -> list[dict[str, Any]]:
    captions: list[list[dict[str, Any]]] = []
    current: list[dict[str, Any]] = []

    for word in words:
        text = str(word["text"]).strip()
        if not text:
            continue
        item = {"text": text, "start": word["start"], "end": word["end"]}
        candidate = current + [item]
        length = len(" ".join(w["text"] for w in candidate))
        span = candidate[-1]["end"] - candidate[0]["start"]
        if current and (length > max_chars or span > max_seconds):
            captions.append(current)
            current = [item]
        else:
            current = candidate
        if text.endswith(_SENTENCE_END) and len(current) > 1:
            captions.append(current)
            current = []

    if current:
        captions.append(current)

    return [
        {
            "start": group[0]["start"],
            "end": group[-1]["end"],
            "text": " ".join(w["text"] for w in group),
        }
        for group in captions
    ]


def format_time(seconds: float) -> str:
    total_ms = max(0, round(seconds * 1000))
    hours, rem = divmod(total_ms, 3_600_000)
    minutes, rem = divmod(rem, 60_000)
    secs, millis = divmod(rem, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def to_srt(captions: list[dict[str, Any]]) -> str:
    blocks = [
        f"{index}\n{format_time(c['start'])} --> {format_time(c['end'])}\n{c['text']}"
        for index, c in enumerate(captions, 1)
    ]
    return "\n\n".join(blocks) + ("\n" if blocks else "")
