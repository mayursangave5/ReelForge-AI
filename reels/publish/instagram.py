from __future__ import annotations

import time

import httpx

from ..config import settings
from .auth import redact


class InstagramError(RuntimeError):
    pass


class InstagramClient:
    def __init__(
        self,
        user_id: str,
        token: str,
        api_version: str | None = None,
        client: httpx.Client | None = None,
    ) -> None:
        self.user_id = user_id
        self._token = token
        self.base = f"https://graph.facebook.com/{api_version or settings.ig_api_version}"
        self._client = client or httpx.Client(timeout=60.0)

    def _post(self, path: str, data: dict) -> dict:
        response = self._client.post(
            f"{self.base}/{path}", data={**data, "access_token": self._token}
        )
        return self._json(response)

    def _get(self, path: str, params: dict) -> dict:
        response = self._client.get(
            f"{self.base}/{path}", params={**params, "access_token": self._token}
        )
        return self._json(response)

    @staticmethod
    def _json(response: httpx.Response) -> dict:
        try:
            payload = response.json()
        except ValueError:
            raise InstagramError(
                redact(f"Instagram returned HTTP {response.status_code}: {response.text[:300]}")
            )
        if response.is_error or "error" in payload:
            raise InstagramError(redact(f"Instagram API error: {payload}"))
        return payload

    def create_container(self, video_url: str, caption: str) -> str:
        payload = self._post(
            f"{self.user_id}/media",
            {
                "media_type": "REELS",
                "video_url": video_url,
                "caption": caption,
                "share_to_feed": "true",
            },
        )
        creation_id = payload.get("id")
        if not creation_id:
            raise InstagramError("Instagram did not return a creation id.")
        return creation_id

    def wait_ready(self, creation_id: str, timeout_s: int = 300) -> None:
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            payload = self._get(creation_id, {"fields": "status_code,status"})
            status = payload.get("status_code")
            if status == "FINISHED":
                return
            if status in {"ERROR", "EXPIRED"}:
                raise InstagramError(f"Instagram processing failed: {payload.get('status')}")
            time.sleep(5)
        raise InstagramError("Instagram processing timed out.")

    def publish(self, creation_id: str) -> str:
        payload = self._post(
            f"{self.user_id}/media_publish", {"creation_id": creation_id}
        )
        media_id = payload.get("id")
        if not media_id:
            raise InstagramError("Instagram did not return a media id.")
        return media_id

    def permalink(self, media_id: str) -> str | None:
        payload = self._get(media_id, {"fields": "permalink"})
        return payload.get("permalink")


def publish_reel(
    video_url: str,
    caption: str,
    user_id: str,
    token: str,
    api_version: str | None = None,
    client: httpx.Client | None = None,
) -> tuple[str, str | None]:
    if not video_url.lower().startswith("https://"):
        raise InstagramError("Instagram requires a public HTTPS video_url.")
    api = InstagramClient(user_id, token, api_version, client)
    creation_id = api.create_container(video_url, caption)
    api.wait_ready(creation_id)
    media_id = api.publish(creation_id)
    return media_id, api.permalink(media_id)
