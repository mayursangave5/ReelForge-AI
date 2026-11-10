from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from ..config import DB_PATH
from ..db import session
from ..script.llm import LLM
from .prompts import SYSTEM, metadata_prompt
from .schema import MetadataBundle


def _load_context(voice_run: Path, db_path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    snapshot_path = voice_run / "script.json"
    if not snapshot_path.is_file():
        raise LookupError(f"{voice_run} has no script.json; run the voice phase first.")
    snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))

    with session(db_path) as conn:
        row = conn.execute(
            "SELECT id, path FROM videos WHERE run_id = ?", (voice_run.name,)
        ).fetchone()
    if row is None:
        raise LookupError(
            f"No rendered video for {voice_run.name}. Run `python -m reels render` first."
        )
    return snapshot, {"id": row["id"], "path": row["path"]}


def generate(
    voice_run: Path,
    llm: LLM,
    db_path: Path = DB_PATH,
) -> dict[str, Any]:
    voice_run = Path(voice_run)
    snapshot, video = _load_context(voice_run, db_path)
    package = snapshot["package"]
    topic = snapshot.get("topic", "")

    raw = llm.generate_json(SYSTEM, metadata_prompt(package, topic))
    bundle = MetadataBundle.model_validate(raw)

    metadata_path = voice_run / "metadata.json"
    metadata_path.write_text(
        json.dumps(
            {
                "video_id": video["id"],
                "model": llm.name,
                "generated_at": datetime.now().isoformat(timespec="seconds"),
                **bundle.model_dump(),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    srt_source = voice_run / "captions.srt"
    srt_copy: Path | None = None
    if srt_source.is_file():
        srt_copy = Path(video["path"]).with_suffix(".hi.srt")
        srt_copy.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(srt_source, srt_copy)

    with session(db_path) as conn:
        for row in bundle.as_rows():
            conn.execute(
                "INSERT INTO captions (video_id, platform, title, caption, hashtags, tags) "
                "VALUES (?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(video_id, platform) DO UPDATE SET "
                "title = excluded.title, caption = excluded.caption, "
                "hashtags = excluded.hashtags, tags = excluded.tags",
                (
                    video["id"],
                    row["platform"],
                    row["title"],
                    row["caption"],
                    json.dumps(row["hashtags"], ensure_ascii=False),
                    json.dumps(row["tags"], ensure_ascii=False),
                ),
            )

    return {
        "video_id": video["id"],
        "video": video["path"],
        "metadata": str(metadata_path),
        "srt": str(srt_copy) if srt_copy else None,
        "instagram": bundle.instagram,
        "youtube": bundle.youtube,
    }
