from __future__ import annotations

import html
import re
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

import httpx

from ..config import settings

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0 Safari/537.36"
)

NEWS_QUERIES = [
    "technology",
    "science",
    "artificial intelligence",
    "space",
    "archaeology",
    "अंतरिक्ष",
    "रहस्य",
]
REDDIT_SUBS = ["india", "technology"]
YOUTUBE_QUERIES = ["science", "technology india"]

ATOM = {"a": "http://www.w3.org/2005/Atom"}
TRENDS = {"ht": "https://trends.google.com/trending/rss"}

_OTHER_INDIC = re.compile(
    "[\u0980-\u09FF\u0A00-\u0AFF\u0B00-\u0BFF\u0C00-\u0CFF\u0D00-\u0D7F]"
)


@dataclass
class TrendItem:
    title: str
    source: str
    url: str
    published_at: datetime | None = None
    hint: dict = field(default_factory=dict)


def clean_text(value: str | None) -> str:
    text = re.sub(r"<[^>]+>", " ", value or "")
    return " ".join(html.unescape(text).split())


def allowed_script(title: str) -> bool:
    """Keep Latin/Devanagari titles; drop other Indic scripts we cannot narrate cleanly."""
    return not _OTHER_INDIC.search(title)


def parse_date(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _xml(client: httpx.Client, url: str, params: dict | None = None) -> ET.Element:
    response = client.get(url, params=params)
    response.raise_for_status()
    return ET.fromstring(response.content)


def fetch_google_trends(client: httpx.Client) -> list[TrendItem]:
    root = _xml(client, "https://trends.google.com/trending/rss", {"geo": "IN"})
    items: list[TrendItem] = []
    for node in root.findall("./channel/item")[:25]:
        title = clean_text(node.findtext("title"))
        if not title:
            continue
        items.append(
            TrendItem(
                title=title,
                source="google_trends",
                url=node.findtext("link") or "https://trends.google.com/trending/rss?geo=IN",
                published_at=parse_date(node.findtext("pubDate")),
                hint={"traffic": node.findtext("ht:approx_traffic", default="", namespaces=TRENDS)},
            )
        )
    return items


def fetch_google_news(client: httpx.Client) -> list[TrendItem]:
    items: list[TrendItem] = []
    for query in NEWS_QUERIES:
        root = _xml(
            client,
            "https://news.google.com/rss/search",
            {"q": query, "hl": "hi", "gl": "IN", "ceid": "IN:hi"},
        )
        for node in root.findall("./channel/item")[:20]:
            title = clean_text(node.findtext("title"))
            source = clean_text(node.findtext("source")) or "Google News"
            if title.endswith(f" - {source}"):
                title = title[: -(len(source) + 3)].strip()
            if not title:
                continue
            items.append(
                TrendItem(
                    title=title,
                    source="google_news",
                    url=node.findtext("link") or "",
                    published_at=parse_date(node.findtext("pubDate")),
                    hint={"query": query, "publisher": source},
                )
            )
    return items


def fetch_reddit(client: httpx.Client) -> list[TrendItem]:
    items: list[TrendItem] = []
    for index, sub in enumerate(REDDIT_SUBS):
        if index:
            time.sleep(1.5)
        root = _xml(client, f"https://www.reddit.com/r/{sub}/hot/.rss", {"limit": 25})
        for entry in root.findall("a:entry", ATOM)[:25]:
            author = entry.findtext("a:author/a:name", default="", namespaces=ATOM)
            if author == "/u/AutoModerator":
                continue
            title = clean_text(entry.findtext("a:title", default="", namespaces=ATOM))
            if not title or title.startswith("[Removed]"):
                continue
            link = entry.find("a:link", ATOM)
            items.append(
                TrendItem(
                    title=title,
                    source="reddit",
                    url=link.get("href", "") if link is not None else "",
                    published_at=parse_date(entry.findtext("a:updated", namespaces=ATOM)),
                    hint={"subreddit": sub},
                )
            )
    return items


def fetch_youtube(client: httpx.Client) -> list[TrendItem]:
    if not settings.youtube_api_key:
        return []
    published_after = (datetime.now(timezone.utc) - timedelta(days=3)).strftime("%Y-%m-%dT%H:%M:%SZ")
    items: list[TrendItem] = []
    for query in YOUTUBE_QUERIES:
        response = client.get(
            "https://www.googleapis.com/youtube/v3/search",
            params={
                "part": "snippet",
                "q": query,
                "regionCode": "IN",
                "relevanceLanguage": "hi",
                "maxResults": 25,
                "type": "video",
                "order": "viewCount",
                "publishedAfter": published_after,
                "key": settings.youtube_api_key,
            },
        )
        if response.status_code != 200:
            raise RuntimeError(f"YouTube API {response.status_code}: {response.text[:200]}")
        for entry in response.json().get("items", []):
            snippet = entry.get("snippet", {})
            title = clean_text(snippet.get("title"))
            if not title:
                continue
            items.append(
                TrendItem(
                    title=title,
                    source="youtube",
                    url=f"https://www.youtube.com/watch?v={entry.get('id', {}).get('videoId', '')}",
                    published_at=parse_date(snippet.get("publishedAt")),
                    hint={"query": query, "channel": snippet.get("channelTitle", "")},
                )
            )
    return items


FETCHERS = [fetch_google_trends, fetch_google_news, fetch_reddit, fetch_youtube]
