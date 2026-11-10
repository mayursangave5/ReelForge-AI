from __future__ import annotations

import math
import re
from datetime import datetime, timezone

SOURCE_WEIGHT = {
    "google_trends": 0.55,
    "google_news": 0.50,
    "reddit": 0.45,
    "youtube": 0.50,
}

POSITIVE = {
    "ai": 0.12, "artificial intelligence": 0.15, "science": 0.15, "space": 0.15,
    "technology": 0.12, "tech": 0.10, "mystery": 0.15, "fact": 0.10,
    "psychology": 0.10, "discovery": 0.10, "robot": 0.10, "quantum": 0.10,
    "isro": 0.12, "nasa": 0.10, "health": 0.05, "history": 0.08,
    "विज्ञान": 0.15, "तकनीक": 0.12, "अंतरिक्ष": 0.15, "रहस्य": 0.15,
    "तथ्य": 0.10, "मनोविज्ञान": 0.10, "खोज": 0.10, "एआई": 0.12,
    "इसरो": 0.12, "नासा": 0.10, "स्वास्थ्य": 0.05, "इतिहास": 0.08,
}

NEGATIVE = {
    "match": -0.18, "score": -0.15, "cricket": -0.15, "election": -0.15,
    "stock": -0.20, "sensex": -0.20, "gold rate": -0.15, "weather": -0.15,
    "box office": -0.20, "bollywood": -0.10, "obituary": -0.15,
    "nse": -0.15, "investor": -0.12, "school": -0.15, "exam": -0.15,
    "arrested": -0.15, "crime": -0.12, "police": -0.10,
    "मैच": -0.18, "चुनाव": -0.15, "शेयर": -0.20, "मौसम": -0.15,
    "क्रिकेट": -0.15, "बॉलीवुड": -0.10, "बॉक्स ऑफिस": -0.20,
    "निवेशक": -0.12, "स्कूल": -0.15, "विद्यालय": -0.15, "मेला": -0.15,
    "प्रदर्शनी": -0.15, "प्रतियोगिता": -0.15, "परीक्षा": -0.15,
    "छात्र": -0.15, "गिरफ्तार": -0.15, "पुलिस": -0.10, "अपराध": -0.12,
}

_TRAFFIC = re.compile(r"([\d,]+)")


def _keyword_delta(text: str) -> float:
    lowered = text.lower()
    delta = sum(weight for word, weight in POSITIVE.items() if word in lowered)
    delta += sum(weight for word, weight in NEGATIVE.items() if word in lowered)
    return max(-0.25, min(0.25, delta))


def _recency(published_at: datetime | None) -> float:
    if published_at is None:
        return 0.0
    age = datetime.now(timezone.utc) - published_at
    if age.total_seconds() <= 24 * 3600:
        return 0.12
    if age.total_seconds() <= 72 * 3600:
        return 0.05
    return 0.0


def _traffic(hint: dict) -> float:
    match = _TRAFFIC.search(str(hint.get("traffic", "")))
    if not match:
        return 0.0
    value = int(match.group(1).replace(",", ""))
    return min(0.12, math.log10(value + 1) * 0.04)


def score(title: str, source: str, published_at: datetime | None, hint: dict | None = None) -> float:
    hint = hint or {}
    total = SOURCE_WEIGHT.get(source, 0.40)
    total += _recency(published_at)
    total += _traffic(hint)
    total += _keyword_delta(title)
    if 25 <= len(title) <= 90:
        total += 0.05
    return round(max(0.0, min(1.0, total)), 3)
