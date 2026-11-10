from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

from .config import DB_PATH, RUNS_DIR, settings
from .db import get_setting, log_error, session, set_setting
from .metadata.service import generate as generate_metadata
from .publish.service import publish as publish_videos
from .script.llm import LLM, LLMError, QuotaExhausted, get_llm
from .script.service import generate as generate_script
from .script.service import select_topic
from .trends.service import discover
from .tts.service import build_voiceover
from .video.service import render

MAX_TOPIC_ATTEMPTS = 3
MOCK_TOPIC = {
    "id": 0,
    "title": "à¤­à¤¾à¤°à¤¤ à¤•à¤¾ à¤…à¤‚à¤¤à¤°à¤¿à¤•à¥à¤· à¤•à¤šà¤°à¤¾ à¤¸à¤¾à¤« à¤•à¤°à¤¨à¥‡ à¤•à¤¾ à¤®à¤¿à¤¶à¤¨",
    "source": "mock",
    "url": "https://example.com/source",
    "score": 1.0,
    "topic_hash": "mocktopic",
    "status": "new",
}


class PipelineError(RuntimeError):
    pass


def _pick_topic(mock: bool, db_path: Path) -> dict:
    if mock:
        try:
            return select_topic(None, db_path)
        except LookupError:
            with session(db_path) as conn:
                conn.execute(
                    "INSERT OR IGNORE INTO topics "
                    "(topic_hash, title, source, url, score, status) "
                    "VALUES (?, ?, ?, ?, ?, 'new')",
                    (
                        MOCK_TOPIC["topic_hash"],
                        MOCK_TOPIC["title"],
                        MOCK_TOPIC["source"],
                        MOCK_TOPIC["url"],
                        MOCK_TOPIC["score"],
                    ),
                )
                row = conn.execute(
                    "SELECT * FROM topics WHERE topic_hash = ?", (MOCK_TOPIC["topic_hash"],)
                ).fetchone()
            return dict(row)
    return select_topic(None, db_path)


def produce(
    *,
    mock: bool = False,
    discover_trends: bool = True,
    publish_after: bool | None = None,
    llm: LLM | None = None,
    db_path: Path = DB_PATH,
) -> dict[str, Any]:
    """Run trends -> script -> voice -> render -> metadata -> (publish) once."""
    llm = llm or get_llm(force_mock=mock)
    if discover_trends and not mock:
        discover(limit=10, save=True)

    last_error: Exception | None = None
    result: dict[str, Any] | None = None
    for _ in range(MAX_TOPIC_ATTEMPTS):
        topic = _pick_topic(mock, db_path)
        try:
            script = generate_script(topic, llm, db_path=db_path)
        except QuotaExhausted:
            raise
        except (LLMError, LookupError, ValueError) as exc:
            last_error = exc
            log_error("pipeline", str(exc), {"topic": topic["title"]}, path=db_path)
            continue
        if script["verdict"] == "fail" or not script.get("script_id"):
            last_error = PipelineError(f"script rejected for: {topic['title']}")
            continue
        result = {"topic": topic, "script": script}
        break

    if result is None:
        raise PipelineError(
            f"No usable topic after {MAX_TOPIC_ATTEMPTS} attempts: {last_error}"
        )

    topic = result["topic"]
    script = result["script"]
    script_id = script["script_id"]
    voice_dir = RUNS_DIR / f"{script['run_id']}_voice{script_id}"

    voice = build_voiceover(
        script["package"],
        voice=settings.voice,
        rate=settings.tts_rate,
        script_id=script_id,
        title=topic["title"],
        out_dir=voice_dir,
    )
    video = render(Path(voice["run_dir"]), db_path=db_path)
    cloud = None
    if settings.r2_configured:
        from .storage import StorageError, upload_video

        try:
            cloud = upload_video(
                Path(video["video"]), Path(voice["run_dir"]).name, db_path
            )
        except StorageError as exc:
            log_error("storage", str(exc), {"run": Path(voice["run_dir"]).name}, path=db_path)
            cloud = {"error": str(exc)}
    metadata = generate_metadata(Path(voice["run_dir"]), llm, db_path=db_path)

    should_publish = (
        settings.auto_publish and not settings.approval_mode
        if publish_after is None
        else publish_after
    )
    publication = None
    if should_publish:
        publication = publish_videos(
            Path(voice["run_dir"]),
            ["youtube", "instagram"],
            db_path=db_path,
            confirm=True,
        )

    summary = {
        "run_id": Path(voice["run_dir"]).name,
        "topic": topic["title"],
        "script": script["script_path"],
        "video": video["video"],
        "duration_s": video["duration_s"],
        "storage": cloud,
        "metadata": metadata["metadata"],
        "publish": publication,
    }
    summary_path = Path(voice["run_dir"]) / "produce.json"
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return summary


def run_slot(
    slot: int,
    *,
    mock: bool = False,
    db_path: Path = DB_PATH,
) -> dict[str, Any]:
    """One scheduled daily run, guarded so a restart never duplicates a reel."""
    # ponytail: single-process guard; add a file lock if running multiple schedulers.
    key = f"daily:{date.today().isoformat()}:slot{slot}"
    if get_setting(key, path=db_path) == "done":
        return {"status": "skipped", "reason": "already produced today", "slot": slot}

    set_setting(key, "running", path=db_path)
    try:
        summary = produce(mock=mock, db_path=db_path)
    except Exception as exc:
        set_setting(key, "failed", path=db_path)
        log_error("schedule", str(exc), {"slot": slot}, path=db_path)
        return {"status": "failed", "slot": slot, "error": str(exc)}
    set_setting(key, "done", path=db_path)
    try:
        from .analytics import capture

        summary["analytics"] = capture(db_path=db_path)
    except Exception as exc:
        log_error("analytics", str(exc), path=db_path)
    try:
        from .storage import cleanup_expired

        summary["cleanup"] = cleanup_expired(db_path)
    except Exception as exc:
        log_error("storage", str(exc), path=db_path)
    return {"status": "done", "slot": slot, **summary}

