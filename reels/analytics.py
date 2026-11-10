from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any, Callable

from .config import DB_PATH, settings
from .db import log_error, session
from .trends.dedupe import jaccard

PlatformFetch = Callable[[list[str]], dict[str, dict[str, Any]]]


def _published(db_path: Path) -> list[dict[str, Any]]:
    with session(db_path) as conn:
        return [
            dict(row)
            for row in conn.execute(
                "SELECT p.remote_id, p.platform, p.video_id FROM publications p "
                "WHERE p.status = 'published' AND p.remote_id IS NOT NULL"
            )
        ]


def _youtube_fetch(ids: list[str]) -> dict[str, dict[str, Any]]:
    from googleapiclient.discovery import build

    from .publish.auth import youtube_credentials

    creds = youtube_credentials(interactive=False)
    service = build("youtube", "v3", credentials=creds, cache_discovery=False)
    stats: dict[str, dict[str, Any]] = {}
    for start in range(0, len(ids), 50):
        chunk = ids[start : start + 50]
        response = (
            service.videos().list(part="statistics", id=",".join(chunk)).execute()
        )
        for item in response.get("items", []):
            raw = item.get("statistics", {})
            stats[item["id"]] = {
                "views": int(raw.get("viewCount", 0)),
                "likes": int(raw.get("likeCount", 0)),
                "comments": int(raw.get("commentCount", 0)),
                "shares": None,
                "retention": None,
                "raw": raw,
            }
    return stats


def _instagram_fetch(media_ids: list[str]) -> dict[str, dict[str, Any]]:
    import httpx

    from .publish.auth import require_instagram

    user_id, token = require_instagram()
    base = f"https://graph.facebook.com/{settings.ig_api_version}"
    stats: dict[str, dict[str, Any]] = {}
    with httpx.Client(timeout=60.0) as client:
        for media_id in media_ids:
            response = client.get(
                f"{base}/{media_id}/insights",
                params={
                    "metric": "views,likes,comments,shares,saved",
                    "access_token": token,
                },
            )
            try:
                payload = response.json()
            except ValueError:
                payload = {"error": {"message": response.text[:200]}}
            if response.is_error or "error" in payload:
                message = payload.get("error", {}).get("message", response.text[:200])
                raise RuntimeError(f"Instagram insights: {message}")
            values = {
                item["name"]: (item.get("values") or [{}])[0].get("value", 0)
                for item in payload.get("data", [])
            }
            stats[media_id] = {
                "views": int(values.get("views") or values.get("plays") or 0),
                "likes": int(values.get("likes") or 0),
                "comments": int(values.get("comments") or 0),
                "shares": int(values.get("shares") or 0),
                "retention": None,
                "raw": values,
            }
    return stats


def _upsert(
    db_path: Path,
    video_id: int,
    platform: str,
    stats: dict[str, Any],
    captured_on: str,
) -> None:
    with session(db_path) as conn:
        conn.execute(
            "INSERT INTO analytics "
            "(video_id, platform, captured_on, views, likes, comments, shares, retention, raw_json) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(video_id, platform, captured_on) DO UPDATE SET "
            "views = excluded.views, likes = excluded.likes, comments = excluded.comments, "
            "shares = excluded.shares, retention = excluded.retention, "
            "raw_json = excluded.raw_json",
            (
                video_id,
                platform,
                captured_on,
                stats.get("views"),
                stats.get("likes"),
                stats.get("comments"),
                stats.get("shares"),
                stats.get("retention"),
                json.dumps(stats.get("raw"), ensure_ascii=False),
            ),
        )


def capture(
    db_path: Path = DB_PATH,
    youtube_fetch: PlatformFetch | None = None,
    instagram_fetch: PlatformFetch | None = None,
    captured_on: str | None = None,
) -> dict[str, Any]:
    """Store today's views/likes/comments/shares for published videos."""
    youtube_fetch = youtube_fetch or _youtube_fetch
    instagram_fetch = instagram_fetch or _instagram_fetch
    captured = date.today().isoformat() if captured_on is None else captured_on
    rows = _published(db_path)
    blockers: list[str] = []
    saved = 0

    for platform, fetch in (("youtube", youtube_fetch), ("instagram", instagram_fetch)):
        items = [row for row in rows if row["platform"] == platform]
        if not items:
            continue
        try:
            stats = fetch([row["remote_id"] for row in items])
        except Exception as exc:
            message = f"{platform}: {exc}"
            blockers.append(message)
            log_error("analytics", message, path=db_path)
            continue
        for row in items:
            found = stats.get(row["remote_id"])
            if found:
                _upsert(db_path, row["video_id"], platform, found, captured)
                saved += 1

    return {"captured_on": captured, "saved": saved, "blockers": blockers}


def latest(db_path: Path = DB_PATH) -> list[dict[str, Any]]:
    with session(db_path) as conn:
        return [
            dict(row)
            for row in conn.execute(
                "SELECT a.video_id, a.platform, a.views, a.likes, a.comments, "
                "a.shares, a.retention, a.captured_on, v.run_id, t.title, s.hook "
                "FROM analytics a "
                "JOIN (SELECT video_id, platform, MAX(captured_on) AS mx FROM analytics "
                "      GROUP BY video_id, platform) m "
                "  ON m.video_id = a.video_id AND m.platform = a.platform "
                " AND m.mx = a.captured_on "
                "JOIN videos v ON v.id = a.video_id "
                "LEFT JOIN scripts s ON s.id = v.script_id "
                "LEFT JOIN topics t ON t.id = s.topic_id "
                "ORDER BY a.views DESC"
            )
        ]


def summary(db_path: Path = DB_PATH, limit: int = 20) -> list[dict[str, Any]]:
    groups: dict[str, dict[str, Any]] = {}
    for row in latest(db_path):
        key = row["title"] or row["run_id"]
        item = groups.setdefault(
            key,
            {
                "title": key,
                "hook": row["hook"] or "",
                "platforms": set(),
                "views": 0,
                "likes": 0,
                "comments": 0,
                "shares": 0,
                "videos": set(),
            },
        )
        item["platforms"].add(row["platform"])
        item["videos"].add(row["video_id"])
        for metric in ("views", "likes", "comments", "shares"):
            item[metric] += row[metric] or 0

    rows: list[dict[str, Any]] = []
    for item in groups.values():
        interactions = item["likes"] + item["comments"] + item["shares"]
        views = item["views"]
        rows.append(
            {
                "title": item["title"],
                "hook": item["hook"],
                "platforms": ", ".join(sorted(item["platforms"])),
                "videos": len(item["videos"]),
                "views": views,
                "likes": item["likes"],
                "comments": item["comments"],
                "shares": item["shares"],
                "engagement_pct": round(interactions / views * 100, 2) if views else 0.0,
            }
        )
    rows.sort(key=lambda row: (row["views"], row["engagement_pct"]), reverse=True)
    return rows[:limit]


def performance_hints(db_path: Path = DB_PATH, limit: int = 5) -> list[dict[str, Any]]:
    rows = summary(db_path, limit=limit)
    top = max((row["views"] for row in rows), default=0)
    if top <= 0:
        return []
    return [
        {"title": row["title"], "weight": row["views"] / top}
        for row in rows
        if row["views"] > 0
    ]


def performance_bonus(
    title: str, hints: list[dict[str, Any]], max_bonus: float = 0.15
) -> float:
    if not hints:
        return 0.0
    similarity = max(jaccard(title, hint["title"]) * hint["weight"] for hint in hints)
    return round(max_bonus * similarity, 3)
