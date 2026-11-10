from __future__ import annotations

import shutil
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
LOGS_DIR = DATA_DIR / "logs"
TOKENS_DIR = DATA_DIR / "tokens"
DB_PATH = DATA_DIR / "reels.db"
OUTPUT_DIR = ROOT / "output"
VIDEOS_DIR = OUTPUT_DIR / "videos"
PREVIEWS_DIR = OUTPUT_DIR / "previews"
RUNS_DIR = ROOT / "runs"
ASSETS_DIR = ROOT / "assets"
MUSIC_DIR = ASSETS_DIR / "music"
FONTS_DIR = ASSETS_DIR / "fonts"
CHARACTERS_DIR = ASSETS_DIR / "characters"
BRAND_DIR = ASSETS_DIR / "brand"
FFMPEG_DIR = ROOT / ".tools" / "ffmpeg" / "bin"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ROOT / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    language: str = "hi"
    tts_provider: str = "edge"
    tts_rate: str = "+4%"
    voice: str = "hi-IN-MadhurNeural"
    timezone: str = "Asia/Kolkata"
    schedule_times: str = "09:00,17:00"

    approval_mode: bool = True
    auto_publish: bool = False

    video_width: int = 1080
    video_height: int = 1920
    video_fps: int = 30
    min_duration_s: int = 30
    max_duration_s: int = 60

    gemini_api_key: str | None = None
    gemini_api_key_2: str | None = None
    gemini_model: str = "gemini-3.6-flash"
    gemini_fallback_model: str = "gemini-2.5-flash"
    gemini_max_retries: int = 5
    gemini_base_delay: float = 1.5
    gemini_max_delay: float = 30.0
    youtube_api_key: str | None = None
    youtube_client_secrets: str | None = None
    youtube_privacy: str = "private"
    gcp_project_id: str | None = None
    google_application_credentials: str | None = None
    ig_user_id: str | None = None
    ig_access_token: str | None = None
    ig_api_version: str = "v21.0"
    cloudflare_account_id: str | None = None
    cloudflare_api_token: str | None = None
    r2_account_id: str | None = None
    r2_access_key_id: str | None = None
    r2_secret_access_key: str | None = None
    r2_bucket: str | None = None
    r2_public_base_url: str | None = None
    r2_prefix: str = "reels"
    r2_retention_hours: int = 24
    fal_key: str | None = None
    elevenlabs_api_key: str | None = None

    ffmpeg_path: str | None = None

    @field_validator(
        "gemini_api_key",
        "gemini_api_key_2",
        "gemini_fallback_model",
        "youtube_api_key",
        "youtube_client_secrets",
        "gcp_project_id",
        "ig_user_id",
        "ig_access_token",
        "google_application_credentials",
        "cloudflare_account_id",
        "cloudflare_api_token",
        "r2_account_id",
        "r2_access_key_id",
        "r2_secret_access_key",
        "r2_bucket",
        "r2_public_base_url",
        "fal_key",
        "elevenlabs_api_key",
        "ffmpeg_path",
        mode="before",
    )
    @classmethod
    def _blank_to_none(cls, value):
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @property
    def gemini_api_keys(self) -> list[str]:
        keys: list[str] = []
        for k in (self.gemini_api_key, self.gemini_api_key_2):
            if k and k.strip() and k.strip() not in keys:
                keys.append(k.strip())
        return keys

    @property
    def schedule(self) -> list[str]:
        times = [t.strip() for t in self.schedule_times.split(",") if t.strip()]
        for t in times:
            hh, mm = t.split(":")
            if not (0 <= int(hh) <= 23 and 0 <= int(mm) <= 59):
                raise ValueError(f"Invalid schedule time: {t}")
        return times

    @property
    def r2_endpoint(self) -> str | None:
        account = self.r2_account_id or self.cloudflare_account_id
        return f"https://{account}.r2.cloudflarestorage.com" if account else None

    @property
    def r2_configured(self) -> bool:
        return bool(
            self.r2_endpoint
            and self.r2_access_key_id
            and self.r2_secret_access_key
            and self.r2_bucket
            and self.r2_public_base_url
        )

    def _tool(self, name: str) -> Path:
        candidates: list[Path | str | None] = []
        if self.ffmpeg_path:
            p = Path(self.ffmpeg_path)
            candidates.append(p / name if p.is_dir() else p)
        candidates.append(FFMPEG_DIR / f"{name}.exe")
        candidates.append(shutil.which(name))
        for candidate in candidates:
            if candidate and Path(candidate).is_file():
                return Path(candidate)
        raise FileNotFoundError(
            f"{name} not found. Set FFMPEG_PATH or install FFmpeg in .tools/ffmpeg."
        )

    def ffmpeg(self) -> Path:
        return self._tool("ffmpeg")

    def ffprobe(self) -> Path:
        return self._tool("ffprobe")


settings = Settings()
