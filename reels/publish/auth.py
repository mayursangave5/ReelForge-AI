from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from ..config import TOKENS_DIR, settings

YOUTUBE_SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",
]
TOKEN_FILE = TOKENS_DIR / "youtube_token.json"
DEFAULT_CLIENT_SECRET = TOKENS_DIR / "client_secret.json"

_SECRET = re.compile(
    r"(access_token|refresh_token|client_secret|Bearer)\s*[=:]?\s*[A-Za-z0-9._\-]{8,}",
    re.IGNORECASE,
)
_LONG_TOKEN = re.compile(r"\b(EAA[A-Za-z0-9]{20,}|AQ\.[A-Za-z0-9_\-\.]{20,})\b")


class AuthError(RuntimeError):
    pass


def redact(text: str) -> str:
    cleaned = _SECRET.sub(r"\1=<redacted>", text)
    return _LONG_TOKEN.sub("<redacted>", cleaned)


def client_secrets_path() -> Path:
    if settings.youtube_client_secrets:
        return Path(settings.youtube_client_secrets)
    return DEFAULT_CLIENT_SECRET


def youtube_status() -> dict[str, Any]:
    secret = client_secrets_path()
    token = TOKEN_FILE
    status: dict[str, Any] = {
        "client_secrets": str(secret),
        "client_secrets_ready": secret.is_file(),
        "token": str(token),
        "token_ready": token.is_file(),
        "scopes": [],
        "authorized": False,
        "expired": None,
    }
    if token.is_file():
        try:
            data = json.loads(token.read_text(encoding="utf-8"))
            status["scopes"] = data.get("scopes", [])
            status["authorized"] = bool(data.get("refresh_token"))
            status["expired"] = data.get("expiry")
        except (OSError, json.JSONDecodeError):
            status["authorized"] = False
    return status


def instagram_status() -> dict[str, Any]:
    return {
        "ig_user_id": bool(settings.ig_user_id),
        "access_token": bool(settings.ig_access_token),
        "api_version": settings.ig_api_version,
    }


def youtube_credentials(interactive: bool = False) -> Any:
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials

    secret = client_secrets_path()
    creds = None
    if TOKEN_FILE.is_file():
        try:
            creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), YOUTUBE_SCOPES)
        except (OSError, ValueError) as exc:
            raise AuthError(f"Stored YouTube token is invalid: {redact(str(exc))}") from exc

    if creds and creds.valid:
        return creds
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        _save(creds)
        return creds
    if not interactive:
        raise AuthError(
            "YouTube is not authorized. Run `python -m reels auth --platform youtube`."
        )
    if not secret.is_file():
        raise AuthError(
            f"Missing OAuth client file at {secret}. Download a Desktop-app OAuth "
            "client JSON from Google Cloud and save it there (see docs/publishing-setup.md)."
        )
    from google_auth_oauthlib.flow import InstalledAppFlow

    flow = InstalledAppFlow.from_client_secrets_file(str(secret), YOUTUBE_SCOPES)
    creds = flow.run_local_server(port=0, access_type="offline", prompt="consent")
    _save(creds)
    return creds


def _save(creds: Any) -> None:
    TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
    TOKEN_FILE.write_text(creds.to_json(), encoding="utf-8")
    try:
        TOKEN_FILE.chmod(0o600)
    except OSError:
        pass


def require_instagram() -> tuple[str, str]:
    if not settings.ig_user_id or not settings.ig_access_token:
        raise AuthError(
            "Instagram credentials missing. Set IG_USER_ID and IG_ACCESS_TOKEN "
            "(see docs/publishing-setup.md)."
        )
    return settings.ig_user_id, settings.ig_access_token
