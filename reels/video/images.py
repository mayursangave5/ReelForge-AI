from __future__ import annotations

import re
import time
import urllib.parse
from pathlib import Path

import httpx

from ..config import settings

STYLE = (
    "cinematic, dramatic lighting, vertical 9:16 composition, "
    "ultra detailed, no text, no watermark"
)
MIN_BYTES = 20_000
_RETRY = re.compile(r"after (\d+)s")


def visual_prompt(scene: dict, title: str = "") -> str:
    base = (scene.get("visual_en") or "").strip() or title.strip()
    return f"{base}, {STYLE}" if base else STYLE


def image_url(prompt: str, seed: int, width: int | None = None, height: int | None = None) -> str:
    w = width or settings.video_width
    h = height or settings.video_height
    quoted = urllib.parse.quote(prompt, safe="")
    return (
        f"https://image.pollinations.ai/prompt/{quoted}"
        f"?width={w}&height={h}&nologo=true&seed={seed}"
    )


def _retry_delay(response: httpx.Response) -> int:
    match = _RETRY.search(response.text)
    return min(70, int(match.group(1)) + 2) if match else 45


def fetch_image(prompt: str, dest: Path, seed: int, attempts: int = 3) -> bool:
    delay = 0
    for _ in range(attempts):
        if delay:
            time.sleep(delay)
        try:
            response = httpx.get(
                image_url(prompt, seed), timeout=180, follow_redirects=True
            )
        except httpx.HTTPError:
            return False
        if response.status_code == 402:
            delay = _retry_delay(response)
            continue
        if response.status_code != 200:
            return False
        if len(response.content) < MIN_BYTES or response.content[:2] != b"\xff\xd8":
            return False
        dest.write_bytes(response.content)
        return True
    return False
