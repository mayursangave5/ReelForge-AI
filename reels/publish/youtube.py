from __future__ import annotations

from pathlib import Path
from typing import Any

from .auth import redact


class YouTubeError(RuntimeError):
    pass


def build_body(meta: dict[str, Any], privacy: str) -> dict[str, Any]:
    hashtags = [f"#{tag}" for tag in meta.get("hashtags", [])]
    description = meta["caption"].strip()
    if hashtags:
        description = f"{description}\n\n{' '.join(hashtags)}"
    tags = list(meta.get("tags", []))
    while len(",".join(tags)) > 500 and tags:
        tags.pop()
    return {
        "snippet": {
            "title": meta["title"].strip(),
            "description": description,
            "tags": tags,
            "categoryId": "28",
        },
        "status": {
            "privacyStatus": privacy,
            "selfDeclaredMadeForKids": False,
        },
    }


def upload(
    video: Path,
    meta: dict[str, Any],
    credentials: Any,
    privacy: str = "private",
) -> str:
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
    from googleapiclient.http import MediaFileUpload

    body = build_body(meta, privacy)
    try:
        service = build("youtube", "v3", credentials=credentials, cache_discovery=False)
        request = service.videos().insert(
            part="snippet,status",
            body=body,
            media_body=MediaFileUpload(
                str(video), mimetype="video/mp4", resumable=True, chunksize=8 * 1024 * 1024
            ),
        )
        response = None
        while response is None:
            _, response = request.next_chunk()
        video_id = response.get("id")
        if not video_id:
            raise YouTubeError("YouTube upload finished without a video id.")
        return video_id
    except HttpError as exc:
        raise YouTubeError(redact(f"YouTube API error: {exc}")) from exc
