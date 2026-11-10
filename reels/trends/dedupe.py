from __future__ import annotations

import re

from ..db import session, topic_hash

STOPWORDS = {
    "the", "a", "an", "of", "in", "on", "for", "to", "and", "with", "is", "are",
    "how", "why", "what", "new", "india", "indian", "this", "that", "from", "by",
    "भारत", "के", "की", "का", "में", "से", "और", "को", "पर", "है", "हैं", "नई",
    "नया", "क्या", "कैसे", "क्यों", "यह", "वह", "एक",
}

_TOKEN = re.compile(r"[0-9A-Za-z\u0900-\u097F]+")


def tokens(text: str) -> set[str]:
    return {
        token
        for token in _TOKEN.findall(text.lower())
        if len(token) > 1 and token not in STOPWORDS
    }


def jaccard(a: str, b: str) -> float:
    left, right = tokens(a), tokens(b)
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def is_duplicate(title: str, existing: list[str], threshold: float = 0.75) -> bool:
    for other in existing:
        if topic_hash(title) == topic_hash(other):
            return True
        if jaccard(title, other) >= threshold:
            return True
    return False


def recent_titles(days: int = 90) -> list[str]:
    with session() as conn:
        rows = conn.execute(
            "SELECT title FROM topics WHERE created_at >= datetime('now', ?)",
            (f"-{int(days)} days",),
        ).fetchall()
    return [row["title"] for row in rows]
