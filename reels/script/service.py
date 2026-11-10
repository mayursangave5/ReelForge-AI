from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from pydantic import ValidationError

from ..db import DB_PATH, log_error, session
from ..config import RUNS_DIR
from .article import MIN_SOURCE_CHARS, resolve_article
from .llm import LLM, LLMError
from .prompts import SYSTEM, VERIFY_SYSTEM, generation_prompt, verify_prompt
from .schema import (
    ScriptPackage,
    VerificationResult,
    factcheck_verdict,
    validate_package,
)

MOCK_ARTICLE = (
    "भारत अंतरिक्ष कचरे को साफ करने के लिए नई तकनीक विकसित कर रहा है। "
    "पृथ्वी की कक्षा में लाखों टुकड़े मौजूद हैं जो उपग्रहों के लिए खतरा हैं। "
    "स्वच्छ अंतरिक्ष भविष्य की अंतरिक्ष यात्राओं के लिए आवश्यक है।"
)


def select_topic(topic_id: int | None = None, db_path: Path = DB_PATH) -> dict:
    with session(db_path) as conn:
        if topic_id is not None:
            row = conn.execute("SELECT * FROM topics WHERE id = ?", (topic_id,)).fetchone()
            if row is None:
                raise LookupError(f"No topic with id {topic_id}.")
            return dict(row)
        rows = conn.execute(
            "SELECT * FROM topics WHERE status = 'new' ORDER BY score DESC, id DESC LIMIT 30"
        ).fetchall()
    if not rows:
        raise LookupError("No topic available. Run `python -m reels trends` first.")

    from ..analytics import performance_bonus, performance_hints

    hints = performance_hints(db_path)
    if not hints:
        return dict(rows[0])
    return dict(
        max(rows, key=lambda row: row["score"] + performance_bonus(row["title"], hints))
    )


def generate(
    topic: dict,
    llm: LLM,
    db_path: Path = DB_PATH,
    run_id: str | None = None,
) -> dict:
    if llm.is_mock:
        article, source_url = MOCK_ARTICLE, "https://example.com/source"
    else:
        article, source_url = resolve_article(topic.get("url", ""), topic["title"])
        if len(article) < MIN_SOURCE_CHARS:
            raise ValueError(
                "Could not fetch enough source text (need "
                f"{MIN_SOURCE_CHARS}+ chars). No LLM call made. Try another topic."
            )
    source_url = source_url or topic.get("url", "")
    allowed_sources = {source_url} if source_url else set()
    prompt = generation_prompt(topic["title"], source_url, article)

    package: ScriptPackage | None = None
    issues: list[str] = []
    for attempt in range(2):
        payload = llm.generate_json(SYSTEM, prompt if attempt == 0 else f"{prompt}\n\nपिछला आउटपुट अमान्य था: {issues}")
        try:
            package = ScriptPackage.model_validate(payload)
        except ValidationError as exc:
            issues = [str(exc)]
            continue
        issues = validate_package(package, allowed_sources)
        if not issues:
            break

    if package is None or issues:
        log_error("script", "validation failed", {"topic": topic["title"], "issues": issues}, db_path)
        raise ValueError("Script validation failed: " + "; ".join(issues[:3]))

    verification = VerificationResult.model_validate(
        llm.generate_json(VERIFY_SYSTEM, verify_prompt([c.claim_hi for c in package.claims], article))
    )
    verdict = factcheck_verdict(verification)
    verified = {check.claim_hi for check in verification.results}
    if any(claim.claim_hi not in verified for claim in package.claims):
        verdict = "fail"

    run_id = run_id or datetime.now().strftime("%Y%m%d-%H%M%S") + f"_{topic['topic_hash'][:6]}"
    run_dir = RUNS_DIR / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    script_path = run_dir / "script.json"
    script_path.write_text(
        json.dumps(
            {
                "topic": topic,
                "package": package.model_dump(),
                "verification": verification.model_dump(),
                "verdict": verdict,
                "model": llm.name,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    if verdict == "fail":
        with session(db_path) as conn:
            conn.execute("UPDATE topics SET status = 'factcheck_failed' WHERE id = ?", (topic["id"],))
        return {
            "run_id": run_id,
            "script_path": str(script_path),
            "script_id": None,
            "verdict": verdict,
            "package": package.model_dump(),
            "verification": verification.model_dump(),
            "saved": False,
        }

    with session(db_path) as conn:
        cursor = conn.execute(
            "INSERT INTO scripts (topic_id, language, hook, scenes_json, model) VALUES (?, ?, ?, ?, ?)",
            (
                topic["id"],
                "hi",
                package.hook_hi,
                json.dumps(package.model_dump(), ensure_ascii=False),
                llm.name,
            ),
        )
        script_id = cursor.lastrowid
        conn.execute("UPDATE topics SET status = 'scripted' WHERE id = ?", (topic["id"],))

    return {
        "run_id": run_id,
        "script_path": str(script_path),
        "script_id": script_id,
        "verdict": verdict,
        "package": package.model_dump(),
        "verification": verification.model_dump(),
        "saved": True,
    }
