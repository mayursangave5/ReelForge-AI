from __future__ import annotations

import asyncio
from typing import Any

import edge_tts

TICKS = 10_000_000


class TTSError(RuntimeError):
    pass


async def _collect(text: str, voice: str, rate: str) -> tuple[bytes, list[dict[str, Any]]]:
    communicate = edge_tts.Communicate(
        text, voice, rate=rate, boundary="WordBoundary"
    )
    chunks: list[bytes] = []
    words: list[dict[str, Any]] = []
    async for event in communicate.stream():
        if event["type"] == "audio":
            chunks.append(event["data"])
        elif event["type"] == "WordBoundary":
            start = event["offset"] / TICKS
            words.append(
                {
                    "text": event["text"],
                    "start": round(start, 3),
                    "end": round(start + event["duration"] / TICKS, 3),
                }
            )
    return b"".join(chunks), words


def synthesize(
    text: str, voice: str, rate: str = "-4%"
) -> tuple[bytes, list[dict[str, Any]]]:
    text = text.strip()
    if not text:
        raise TTSError("text is empty")
    try:
        audio, words = asyncio.run(_collect(text, voice, rate))
    except Exception as exc:
        raise TTSError(f"edge-tts failed: {exc}") from exc
    if not audio:
        raise TTSError("edge-tts returned no audio")
    return audio, words


def hindi_voices() -> list[dict[str, Any]]:
    async def fetch() -> list[dict[str, Any]]:
        voices = await edge_tts.list_voices()
        return sorted(
            (v for v in voices if v["Locale"].startswith("hi-IN")),
            key=lambda v: v["ShortName"],
        )

    try:
        return asyncio.run(fetch())
    except Exception as exc:
        raise TTSError(f"could not list voices: {exc}") from exc
