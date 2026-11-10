from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from ..config import DB_PATH, settings
from ..db import log_error, session
from .auth import (
    AuthError,
    instagram_status,
    redact,
    require_instagram,
    youtube_credentials,
    youtube_status,
)
from .instagram import InstagramError, publish_reel
from .youtube import YouTubeError, upload

PLATFORMS = ("youtube", "instagram")


class PublishError(RuntimeError):
    pass


def idempotency_key(run_id: str, platform: str) -> str:
    return f"{run_id}:{platform}"


def load_context(voice_run: Path, db_path: Path = DB_PATH) -> dict[str, Any]:
    with session(db_path) as conn:
        video = conn.execute(
            "SELECT id, script_id, path FROM videos WHERE run_id = ?", (voice_run.name,)
        ).fetchone()
        if video is None:
            raise LookupError(
                f"No rendered video for {voice_run.name}. Run `python -m reels render` first."
            )
        captions = {
            row["platform"]: dict(row)
            for row in conn.execute(
                "SELECT platform, title, caption, hashtags, tags FROM captions WHERE video_id = ?",
                (video["id"],),
            )
        }
    if not captions:
        raise LookupError(
            f"No captions for {voice_run.name}. Run `python -m reels metadata` first."
        )
    return {
        "video_id": video["id"],
        "script_id": video["script_id"],
        "path": Path(video["path"]),
        "captions": captions,
    }


def _meta(captions: dict[str, Any], platform: str) -> dict[str, Any]:
    row = captions.get(platform)
    if row is None:
        raise PublishError(f"No {platform} metadata. Run `python -m reels metadata`.")
    return {
        "title": row["title"] or "",
        "caption": row["caption"] or "",
        "hashtags": json.loads(row["hashtags"] or "[]"),
        "tags": json.loads(row["tags"] or "[]"),
    }


def prepare(
    voice_run: Path,
    platform: str,
    db_path: Path = DB_PATH,
    video_url: str | None = None,
    allow_upload: bool = False,
) -> dict[str, Any]:
    if platform not in PLATFORMS:
        raise ValueError(f"unknown platform: {platform}")
    context = load_context(voice_run, db_path)
    if not context["path"].is_file():
        raise PublishError(f"video file is missing: {context['path']}")
    meta = _meta(context["captions"], platform)
    key = idempotency_key(voice_run.name, platform)

    if platform == "youtube":
        status = youtube_status()
        blockers = []
        if not status["client_secrets_ready"]:
            blockers.append("missing OAuth client JSON")
        if not status["token_ready"]:
            blockers.append("YouTube not authorized")
        payload = {"title": meta["title"], "caption": meta["caption"], "tags": meta["tags"]}
    else:
        status = instagram_status()
        blockers = []
        if not status["ig_user_id"]:
            blockers.append("IG_USER_ID missing")
        if not status["access_token"]:
            blockers.append("IG_ACCESS_TOKEN missing")
        if not video_url:
            from ..storage import StorageError, stored_url, upload_video

            video_url = stored_url(context["video_id"], db_path)
            if not video_url and allow_upload and not blockers and settings.r2_configured:
                try:
                    video_url = upload_video(context["path"], voice_run.name, db_path)["url"]
                except StorageError as exc:
                    log_error(
                        "storage",
                        str(exc),
                        {"run": voice_run.name, "platform": platform},
                        db_path,
                    )
        if not video_url:
            blockers.append("public HTTPS --video-url required")
        payload = {"caption": meta["caption"], "video_url": video_url}

    return {
        "platform": platform,
        "video_id": context["video_id"],
        "script_id": context["script_id"],
        "video": str(context["path"]),
        "idempotency_key": key,
        "credentials": status,
        "blockers": blockers,
        "payload": payload,
    }


def _record(
    db_path: Path,
    video_id: int,
    platform: str,
    key: str,
    status: str,
    remote_id: str | None = None,
    url: str | None = None,
    error: str | None = None,
) -> None:
    with session(db_path) as conn:
        conn.execute(
            "INSERT INTO publications "
            "(video_id, platform, remote_id, url, status, idempotency_key, error, published_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(idempotency_key) DO UPDATE SET "
            "remote_id = excluded.remote_id, url = excluded.url, status = excluded.status, "
            "error = excluded.error, published_at = excluded.published_at",
            (
                video_id,
                platform,
                remote_id,
                url,
                status,
                key,
                error,
                datetime.now().isoformat(timespec="seconds") if status == "published" else None,
            ),
        )


def _existing(db_path: Path, key: str) -> dict[str, Any] | None:
    with session(db_path) as conn:
        row = conn.execute(
            "SELECT status, remote_id, url FROM publications WHERE idempotency_key = ?", (key,)
        ).fetchone()
    return dict(row) if row else None


def _mark_published(db_path: Path, video_id: int, script_id: int | None) -> None:
    with session(db_path) as conn:
        conn.execute("UPDATE videos SET status = 'published' WHERE id = ?", (video_id,))
        if script_id:
            conn.execute(
                "UPDATE topics SET status = 'published', published_at = datetime('now') "
                "WHERE id = (SELECT topic_id FROM scripts WHERE id = ?)",
                (script_id,),
            )


def publish(
    voice_run: Path,
    platforms: tuple[str, ...] | list[str],
    db_path: Path = DB_PATH,
    confirm: bool = False,
    video_url: str | None = None,
) -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    for platform in platforms:
        plan = prepare(voice_run, platform, db_path, video_url, allow_upload=confirm)
        key = plan["idempotency_key"]
        previous = _existing(db_path, key)
        if previous and previous["status"] == "published":
            results.append(
                {
                    "platform": platform,
                    "status": "skipped",
                    "reason": "already published",
                    "remote_id": previous["remote_id"],
                    "url": previous["url"],
                }
            )
            continue

        if not confirm:
            _record(db_path, plan["video_id"], platform, key, "dry_run")
            results.append(
                {
                    "platform": platform,
                    "status": "dry_run",
                    "blockers": plan["blockers"],
                    "payload": plan["payload"],
                    "idempotency_key": key,
                }
            )
            continue

        if plan["blockers"]:
            message = "; ".join(plan["blockers"])
            _record(db_path, plan["video_id"], platform, key, "failed", error=message)
            log_error("publish", message, {"run": voice_run.name, "platform": platform}, db_path)
            results.append({"platform": platform, "status": "failed", "error": message})
            continue

        try:
            if platform == "youtube":
                creds = youtube_credentials(interactive=False)
                remote_id = upload(
                    plan["video"], plan["payload"], creds, settings.youtube_privacy
                )
                url = f"https://youtube.com/shorts/{remote_id}"
            else:
                from ..storage import verify_public

                if not verify_public(plan["payload"]["video_url"]):
                    raise PublishError(
                        "Instagram video URL is not publicly reachable (HTTPS 200 required)"
                    )
                user_id, token = require_instagram()
                remote_id, url = publish_reel(
                    plan["payload"]["video_url"], plan["payload"]["caption"], user_id, token
                )
        except (AuthError, YouTubeError, InstagramError, PublishError, OSError) as exc:
            message = redact(str(exc))
            _record(db_path, plan["video_id"], platform, key, "failed", error=message)
            log_error("publish", message, {"run": voice_run.name, "platform": platform}, db_path)
            results.append({"platform": platform, "status": "failed", "error": message})
            continue

        _record(db_path, plan["video_id"], platform, key, "published", remote_id, url)
        _mark_published(db_path, plan["video_id"], plan["script_id"])
        if platform == "instagram" and settings.r2_retention_hours <= 0:
            from ..storage import delete_for_video

            try:
                delete_for_video(plan["video_id"], db_path)
            except Exception as exc:
                log_error(
                    "storage",
                    f"R2 cleanup failed: {exc}",
                    {"run": voice_run.name, "platform": platform},
                    db_path,
                )
        results.append(
            {"platform": platform, "status": "published", "remote_id": remote_id, "url": url}
        )

    return {"run_id": voice_run.name, "confirm": confirm, "results": results}
