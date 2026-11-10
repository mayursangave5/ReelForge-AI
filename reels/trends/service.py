from __future__ import annotations

import re
from datetime import datetime

import httpx

from ..db import log_error, session, topic_hash
from .dedupe import is_duplicate, recent_titles
from .scorer import score
from .sources import USER_AGENT, FETCHERS, TrendItem, allowed_script, clean_text

LOW_VALUE_SUBSTR = (
    "विद्यालय", "स्कूल", "मेला", "प्रदर्शनी", "प्रतियोगिता", "परीक्षा",
    "छात्र", "निरीक्षण", "गिरफ्तार", "पुलिस", "अपराध", "कांड", "मामला दर्ज",
    "भर्ती", "आवेदन", "पूजा", "धार्मिक", "मंदिर", "त्योहार", "परंपरा",
    "पर्दाफाश", "एपिसोड", "फिल्म", "मूवी", "सीरीज", "मनोरंजन",
    "बॉलीवुड", "बॉक्स ऑफिस", "मैच", "क्रिकेट", "चुनाव", "मौसम", "निवेशक",
    "अमावस्या", "राशिफल", "पंचांग", "मुहूर्त", "ग्राहक", "ऑफर", "बजट में",
    "science fair",
)

LOW_VALUE_WORDS = re.compile(
    r"\b(vs|tv|live|match|episode|watch|trailer|movie|series|school|exam|fair|"
    r"arrested|crime|police|investor|nse|vacancy|recruitment|deal|buy|price|review)\b"
)


def _low_value(title: str) -> bool:
    lowered = title.lower()
    return any(word in lowered for word in LOW_VALUE_SUBSTR) or bool(
        LOW_VALUE_WORDS.search(lowered)
    )


def collect(timeout: float = 25.0) -> tuple[list[TrendItem], list[str]]:
    items: list[TrendItem] = []
    errors: list[str] = []
    with httpx.Client(
        headers={"User-Agent": USER_AGENT},
        follow_redirects=True,
        timeout=timeout,
    ) as client:
        for fetcher in FETCHERS:
            try:
                items.extend(fetcher(client))
            except Exception as exc:
                message = f"{fetcher.__name__}: {exc}"
                errors.append(message)
                log_error("trends", message)
    return items, errors


def rank(items: list[TrendItem], known: list[str]) -> list[dict]:
    ranked: list[dict] = []
    accepted: list[str] = []
    for item in items:
        title = clean_text(item.title)
        if len(title) < 12 or not allowed_script(title) or _low_value(title):
            continue
        if is_duplicate(title, known) or is_duplicate(title, accepted):
            continue
        accepted.append(title)
        ranked.append(
            {
                "title": title,
                "source": item.source,
                "url": item.url,
                "score": score(title, item.source, item.published_at, item.hint),
                "topic_hash": topic_hash(title),
                "published_at": item.published_at.isoformat() if item.published_at else None,
            }
        )
    ranked.sort(key=lambda row: row["score"], reverse=True)
    return ranked


def save_topics(rows: list[dict]) -> None:
    with session() as conn:
        for row in rows:
            conn.execute(
                "INSERT INTO topics (topic_hash, title, source, url, score, status) "
                "VALUES (?, ?, ?, ?, ?, 'new') "
                "ON CONFLICT(topic_hash) DO UPDATE SET score = excluded.score, url = excluded.url",
                (row["topic_hash"], row["title"], row["source"], row["url"], row["score"]),
            )


def discover(limit: int = 10, save: bool = True, allow_known: bool = False) -> tuple[list[dict], list[str]]:
    items, errors = collect()
    known = [] if allow_known else recent_titles()
    ranked = rank(items, known)
    top = ranked[:limit]
    if save and top:
        save_topics(top)
    return top, errors
