from __future__ import annotations

import re
from typing import Literal
from urllib.parse import urlparse

from pydantic import BaseModel, Field, field_validator

_URL = re.compile(r"^https?://", re.IGNORECASE)


class Claim(BaseModel):
    claim_hi: str = Field(min_length=5)
    sources: list[str] = Field(default_factory=list)
    confidence: Literal["high", "medium", "low"] = "medium"

    @field_validator("sources")
    @classmethod
    def _valid_urls(cls, values: list[str]) -> list[str]:
        for value in values:
            if not _URL.match(value):
                raise ValueError(f"invalid source URL: {value}")
        return values


class Scene(BaseModel):
    narration_hi: str = Field(min_length=5)
    visual_en: str = Field(min_length=10)
    text_hi: str = ""
    duration_s: float = Field(ge=3, le=12)


class ScriptPackage(BaseModel):
    title_hi: str = Field(min_length=3)
    hook_hi: str = Field(min_length=5)
    scenes: list[Scene] = Field(min_length=3, max_length=8)
    cta_hi: str = ""
    estimated_duration_s: float = Field(ge=25, le=65)
    claims: list[Claim] = Field(default_factory=list)


class ClaimCheck(BaseModel):
    claim_hi: str
    supported: bool
    reason_hi: str = ""


class VerificationResult(BaseModel):
    results: list[ClaimCheck] = Field(default_factory=list)


def word_count(text: str) -> int:
    return len(text.split())


def script_words(package: ScriptPackage) -> int:
    parts = [package.hook_hi, package.cta_hi]
    parts.extend(scene.narration_hi for scene in package.scenes)
    return sum(word_count(part) for part in parts)


def validate_package(
    package: ScriptPackage, allowed_sources: set[str] | None = None
) -> list[str]:
    issues: list[str] = []

    total = sum(scene.duration_s for scene in package.scenes)
    if abs(total - package.estimated_duration_s) > 5:
        issues.append(
            f"estimated_duration_s {package.estimated_duration_s} does not match scene total {total:.1f}"
        )
    if not 25 <= total <= 65:
        issues.append(f"total scene duration {total:.1f}s is outside 25-65s")

    words = script_words(package)
    if not 70 <= words <= 180:
        issues.append(f"narration has {words} words; expected 70-180")

    if word_count(package.hook_hi) > 20:
        issues.append("hook is longer than 20 words")

    for index, scene in enumerate(package.scenes, 1):
        if word_count(scene.narration_hi) < 5:
            issues.append(f"scene {index} narration is too short")

    if allowed_sources is not None:
        for claim in package.claims:
            if not claim.sources:
                issues.append(f"claim has no source: {claim.claim_hi[:40]}")
            for source in claim.sources:
                if source not in allowed_sources:
                    issues.append(f"claim cites a source not provided: {source}")

    if not package.claims:
        issues.append("no factual claims with sources were returned")

    return issues


def factcheck_verdict(verification: VerificationResult) -> str:
    if not verification.results:
        return "warn"
    if any(not check.supported for check in verification.results):
        return "fail"
    return "pass"


def domain(url: str) -> str:
    return urlparse(url).netloc.lower()
