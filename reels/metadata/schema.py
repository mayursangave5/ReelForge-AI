from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel, Field, field_validator

_SPACE = re.compile(r"\s+")
_DROP = re.compile(r"[#,\u200b]")
_EMOJI = re.compile("[\U0001F000-\U0001FAFF\u2600-\u27BF\u2B00-\u2BFF]")


def _as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [part for part in re.split(r"[,\n]", value) if part.strip()]
    return [str(item) for item in value]


def clean_hashtags(value: Any) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in _as_list(value):
        tag = _SPACE.sub("", _DROP.sub("", item)).strip()
        if not tag:
            continue
        key = tag.casefold()
        if key in seen:
            continue
        seen.add(key)
        result.append(tag)
    return result


def clean_tags(value: Any) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in _as_list(value):
        tag = _SPACE.sub(" ", _DROP.sub("", item)).strip()
        if not tag:
            continue
        key = tag.casefold()
        if key in seen:
            continue
        seen.add(key)
        result.append(tag)
    return result


def _check_count(name: str, values: list[str], low: int, high: int) -> list[str]:
    if not low <= len(values) <= high:
        raise ValueError(f"{name} must contain {low}-{high} items, got {len(values)}")
    for item in values:
        if len(item) > 30:
            raise ValueError(f"{name} item is too long: {item[:40]}")
    return values


class InstagramMetadata(BaseModel):
    caption: str = Field(min_length=30, max_length=2200)
    hashtags: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)

    @field_validator("hashtags", mode="before")
    @classmethod
    def _hashtags(cls, value: Any) -> list[str]:
        return clean_hashtags(value)

    @field_validator("hashtags")
    @classmethod
    def _hashtag_count(cls, value: list[str]) -> list[str]:
        return _check_count("instagram hashtags", value, 5, 15)

    @field_validator("caption")
    @classmethod
    def _emoji(cls, value: str) -> str:
        if not _EMOJI.search(value):
            raise ValueError("instagram caption needs at least one emoji")
        return value.strip()

    @property
    def full_caption(self) -> str:
        return "\n\n".join(
            [self.caption.strip(), " ".join(f"#{tag}" for tag in self.hashtags)]
        ).strip()


class YouTubeMetadata(BaseModel):
    title: str = Field(min_length=10, max_length=100)
    caption: str = Field(min_length=50, max_length=4900)
    hashtags: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)

    @field_validator("hashtags", mode="before")
    @classmethod
    def _hashtags(cls, value: Any) -> list[str]:
        return clean_hashtags(value)

    @field_validator("hashtags")
    @classmethod
    def _hashtag_count(cls, value: list[str]) -> list[str]:
        return _check_count("youtube hashtags", value, 3, 8)

    @field_validator("tags", mode="before")
    @classmethod
    def _tags(cls, value: Any) -> list[str]:
        return clean_tags(value)

    @field_validator("tags")
    @classmethod
    def _tag_count(cls, value: list[str]) -> list[str]:
        tags = _check_count("youtube tags", value, 3, 15)
        if len(",".join(tags)) > 500:
            raise ValueError("youtube tags exceed the 500 character limit")
        return tags

    @field_validator("title", "caption")
    @classmethod
    def _strip(cls, value: str) -> str:
        return value.strip()


class MetadataBundle(BaseModel):
    instagram: InstagramMetadata
    youtube: YouTubeMetadata

    def as_rows(self) -> list[dict[str, Any]]:
        return [
            {
                "platform": "instagram",
                "title": None,
                "caption": self.instagram.full_caption,
                "hashtags": self.instagram.hashtags,
                "tags": self.instagram.tags,
            },
            {
                "platform": "youtube",
                "title": self.youtube.title,
                "caption": self.youtube.caption,
                "hashtags": self.youtube.hashtags,
                "tags": self.youtube.tags,
            },
        ]
