from __future__ import annotations

import html
import re
import xml.etree.ElementTree as ET
from urllib.parse import quote, urlparse

import httpx

from ..trends.sources import USER_AGENT

MIN_SOURCE_CHARS = 800

_BLOCK = re.compile(r"(?is)<(script|style|noscript|svg)[^>]*>.*?</\1>")
_TAG = re.compile(r"(?s)<[^>]+>")
_SPACE = re.compile(r"\s+")


def extract_text(html_text: str, max_chars: int = 9000) -> str:
    text = _BLOCK.sub(" ", html_text)
    text = _TAG.sub(" ", text)
    text = html.unescape(text)
    return _SPACE.sub(" ", text).strip()[:max_chars]


def fetch_article(url: str, timeout: float = 20.0, max_chars: int = 9000) -> str:
    if not url:
        return ""
    with httpx.Client(
        headers={"User-Agent": USER_AGENT},
        follow_redirects=True,
        timeout=timeout,
    ) as client:
        response = client.get(url)
        response.raise_for_status()
        content_type = response.headers.get("content-type", "")
        if "html" not in content_type and "text" not in content_type:
            return ""
        return extract_text(response.text, max_chars=max_chars)


def bing_news_article(
    title: str, min_chars: int = MIN_SOURCE_CHARS, max_items: int = 3
) -> tuple[str, str | None]:
    query = quote(title.split(":", 1)[0].strip())
    rss_url = f"https://www.bing.com/news/search?q={query}&format=rss&setlang=hi&cc=IN"
    try:
        with httpx.Client(
            headers={"User-Agent": USER_AGENT}, follow_redirects=True, timeout=20
        ) as client:
            response = client.get(rss_url)
            response.raise_for_status()
            root = ET.fromstring(response.text)
            for item in root.findall(".//item")[:max_items]:
                link = (item.findtext("link") or "").strip()
                description = html.unescape((item.findtext("description") or "").strip())
                if not link:
                    continue
                try:
                    text = fetch_article(link)
                except Exception:
                    continue
                if len(text) >= min_chars:
                    return text, link
                if len(description) >= min_chars:
                    return description, link
    except Exception:
        pass
    return "", None


def resolve_article(url: str, title: str) -> tuple[str, str | None]:
    """Return (text, source_url). Google News RSS links carry no article text."""
    text = ""
    if url and "google." not in urlparse(url).netloc:
        try:
            text = fetch_article(url)
        except Exception:
            text = ""
    if len(text) >= MIN_SOURCE_CHARS:
        return text, url
    bing_text, bing_url = bing_news_article(title)
    if len(bing_text) > len(text):
        return bing_text, bing_url
    return text, (url or None)
