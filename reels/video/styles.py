from __future__ import annotations

import re
from typing import Any

STYLES = {
    "3d_cartoon": {
        "name": "Cinematic 3D Cartoon",
        "description": "Zack D. Films & Kurzgesagt 3D inspired: 3D celestial bodies, dramatic lighting, perspective fly-throughs, and particle VFX.",
        "best_for": "Catastrophes, space, cosmic events, what-if scenarios, dynamic physical interactions",
        "keywords": ["asteroid", "earth", "space", "planet", "collision", "explosion", "impact", "ocean", "sun", "moon", "gravity"],
    },
    "2d_colorful": {
        "name": "Colorful Vector 2D",
        "description": "Kurzgesagt aesthetic: vibrant flat vectors, rich saturated palettes, geometric characters, and fluid motion.",
        "best_for": "Biology, nature, human history, future tech, philosophy, civilization",
        "keywords": ["biology", "human", "body", "future", "cells", "virus", "civilization", "evolution", "climate"],
    },
    "anime": {
        "name": "Anime-Inspired Action",
        "description": "Dynamic speed lines, dramatic perspective, stylized impact frames, and intense kinetic action.",
        "best_for": "Martial arts, extreme speeds, battles, superpowers, intense confrontations",
        "keywords": ["speed", "power", "fight", "superpower", "ninja", "energy", "fastest", "strength"],
    },
    "stick_figure": {
        "name": "Stick-Figure Storytelling",
        "description": "What-If dusk-lit stick figure style: Pip rig, practical lamp/window lighting, room perspective, and grounded props.",
        "best_for": "Everyday superpowers, relatable dilemmas, thought experiments, comedic twists",
        "keywords": ["rewind", "pause", "copy", "paste", "invisibility", "money", "sleep", "luck", "what if you"],
    },
    "educational_motion": {
        "name": "Educational Motion Graphics",
        "description": "3Blue1Brown & Infographics Show style: animated coordinate grids, function graphs, schematics, and floating metrics.",
        "best_for": "Mathematics, economics, algorithm explainers, engineering, statistics",
        "keywords": ["math", "algorithm", "formula", "percent", "data", "economy", "finance", "physics", "code", "ai"],
    },
}


def select_style(topic: str, context: str = "") -> str:
    """Automatically select the best animation style based on topic and context."""
    text = f"{topic} {context}".lower()

    scores: dict[str, int] = {k: 0 for k in STYLES}

    for style_key, style_data in STYLES.items():
        for kw in style_data["keywords"]:
            if re.search(r"\b" + re.escape(kw) + r"\b", text):
                scores[style_key] += 3
            elif kw in text:
                scores[style_key] += 1

    # Special rules
    if "asteroid" in text or "meteor" in text or "hit earth" in text:
        return "3d_cartoon"
    if "rewind" in text or "copy paste" in text or "pause time" in text:
        return "stick_figure"
    if "calculate" in text or "formula" in text or "graph" in text:
        return "educational_motion"

    best_style = max(scores, key=lambda k: scores[k])
    return best_style if scores[best_style] > 0 else "3d_cartoon"


def list_styles() -> list[dict[str, Any]]:
    return [{"key": k, **v} for k, v in STYLES.items()]
