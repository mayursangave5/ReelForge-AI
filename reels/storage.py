from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx

from .config import DB_PATH, settings
from .db import log_error, session


class StorageError(RuntimeError):
    pass


def configured() -> bool:
    return settings.r2_configured


def object_key(run_id: str) -> str:
    return f"{settings.r2_prefix.strip('/')}/{run_id}.mp4"


def _default_client():
    missing = [
        name
        for name in ("r2_endpoint", "r2_access_key_id", "r2_secret_access_key", "r2_bucket")
        if not getattr(settings, name)
    ]
    if missing:
        raise StorageError(f"R2 not configured: missing {', '.join(missing)}")
    import boto3
    from botocore.config import Config

    return boto3.client(
        "s3",
        endpoint_url=settings.r2_endpoint,
        aws_access_key_id=settings.r2_access_key_id,
        aws_secret_access_key=settings.r2_secret_access_key,
        region_name="auto",
        config=Config(
            signature_version="s3v4",
            retries={"max_attempts": 4, "mode": "standard"},
            connect_timeout=10,
            read_timeout=120,
        ),
    )


class R2Storage:
    def __init__(
        self,
        client=None,
        bucket: str | None = None,
        public_base_url: str | None = None,
        prefix: str | None = None,
    ):
        self._client = client
        self.bucket = bucket or settings.r2_bucket
        self.public_base_url = public_base_url or settings.r2_public_base_url
        self.prefix = (prefix or settings.r2_prefix).strip("/")
        if not self.bucket or not self.public_base_url:
            raise StorageError("R2 bucket or public base URL is not configured")

    @property
    def client(self):
        if self._client is None:
            self._client = _default_client()
        return self._client

    def key(self, run_id: str) -> str:
        return f"{self.prefix}/{run_id}.mp4"

    def public_url(self, key: str) -> str:
        return f"{self.public_base_url.rstrip('/')}/{key}"

    def upload(
        self,
        path: Path,
        key: str | None = None,
        content_type: str = "video/mp4",
        attempts: int = 3,
        sleep=time.sleep,
    ) -> str:
        key = key or self.key(Path(path).stem)
        last: Exception | None = None
        for attempt in range(attempts):
            try:
                self.client.upload_file(
                    str(path), self.bucket, key, ExtraArgs={"ContentType": content_type}
                )
                return self.public_url(key)
            except Exception as exc:
                last = exc
                if attempt + 1 < attempts:
                    sleep(2**attempt)
        raise StorageError(f"R2 upload failed for {Path(path).name}: {last}")

    def delete(self, key: str) -> None:
        self.client.delete_object(Bucket=self.bucket, Key=key)

    def verify(
        self,
        url: str,
        attempts: int = 3,
        sleep=time.sleep,
        head=None,
    ) -> bool:
        return _check_url(url, attempts=attempts, sleep=sleep, head=head)


def _check_url(url: str, attempts: int = 3, sleep=time.sleep, head=None) -> bool:
    head = head or httpx.head
    for attempt in range(attempts):
        try:
            response = head(url, follow_redirects=True, timeout=30)
            if response.status_code in (200, 206):
                content_type = response.headers.get("content-type", "")
                length = response.headers.get("content-length", "0")
                if content_type.startswith("video") or int(length or 0) > 0:
                    return True
        except Exception:
            pass
        if attempt + 1 < attempts:
            sleep(2**attempt)
    return False


def _storage(storage: R2Storage | None) -> R2Storage:
    return storage or R2Storage()


def verify_public(url: str, attempts: int = 3) -> bool:
    if not url.startswith("https://"):
        return False
    return _check_url(url, attempts=attempts)


def _video_id(run_id: str, db_path: Path) -> int | None:
    with session(db_path) as conn:
        row = conn.execute("SELECT id FROM videos WHERE run_id = ?", (run_id,)).fetchone()
    return row["id"] if row else None


def stored_url(video_id: int, db_path: Path = DB_PATH) -> str | None:
    with session(db_path) as conn:
        row = conn.execute(
            "SELECT url FROM cloud_uploads WHERE video_id = ? AND status = 'uploaded' "
            "ORDER BY id DESC LIMIT 1",
            (video_id,),
        ).fetchone()
    return row["url"] if row else None


def stored_url_for_run(run_id: str, db_path: Path = DB_PATH) -> str | None:
    video_id = _video_id(run_id, db_path)
    return stored_url(video_id, db_path) if video_id else None


def upload_video(
    video_path: Path,
    run_id: str,
    db_path: Path = DB_PATH,
    storage: R2Storage | None = None,
    verify: bool = True,
) -> dict:
    storage = _storage(storage)
    video_path = Path(video_path)
    if not video_path.is_file():
        raise StorageError(f"video file not found: {video_path}")
    key = storage.key(run_id)
    url = storage.upload(video_path, key)
    verified = storage.verify(url) if verify else False
    if verify and not verified:
        raise StorageError(f"uploaded video is not publicly reachable: {url}")
    video_id = _video_id(run_id, db_path)
    with session(db_path) as conn:
        conn.execute(
            "INSERT INTO cloud_uploads (video_id, key, url, status) VALUES (?, ?, ?, 'uploaded') "
            "ON CONFLICT(key) DO UPDATE SET url = excluded.url, status = 'uploaded', "
            "error = NULL, uploaded_at = datetime('now'), deleted_at = NULL",
            (video_id, key, url),
        )
    return {"key": key, "url": url, "verified": verified}


def uploads(db_path: Path = DB_PATH) -> list[dict]:
    with session(db_path) as conn:
        rows = conn.execute(
            "SELECT u.id, u.video_id, v.run_id, u.key, u.url, u.status, u.error, "
            "u.uploaded_at, u.deleted_at FROM cloud_uploads u "
            "LEFT JOIN videos v ON v.id = u.video_id ORDER BY u.id DESC"
        ).fetchall()
    return [dict(row) for row in rows]


def _delete_rows(rows: list[dict], db_path: Path, storage: R2Storage) -> int:
    deleted = 0
    for row in rows:
        try:
            storage.delete(row["key"])
        except Exception as exc:
            log_error("storage", f"R2 delete failed for {row['key']}: {exc}", path=db_path)
            with session(db_path) as conn:
                conn.execute(
                    "UPDATE cloud_uploads SET status = 'failed', error = ? WHERE id = ?",
                    (str(exc), row["id"]),
                )
            continue
        with session(db_path) as conn:
            conn.execute(
                "UPDATE cloud_uploads SET status = 'deleted', deleted_at = datetime('now') "
                "WHERE id = ?",
                (row["id"],),
            )
        deleted += 1
    return deleted


def delete_for_video(
    video_id: int | None, db_path: Path = DB_PATH, storage: R2Storage | None = None
) -> int:
    if video_id is None:
        return 0
    with session(db_path) as conn:
        rows = [
            dict(row)
            for row in conn.execute(
                "SELECT * FROM cloud_uploads WHERE video_id = ? AND status = 'uploaded'",
                (video_id,),
            ).fetchall()
        ]
    if not rows:
        return 0
    return _delete_rows(rows, db_path, _storage(storage))


def cleanup_expired(
    db_path: Path = DB_PATH,
    retention_hours: int | None = None,
    storage: R2Storage | None = None,
    now: datetime | None = None,
) -> dict:
    hours = settings.r2_retention_hours if retention_hours is None else retention_hours
    now = now or datetime.now(timezone.utc).replace(tzinfo=None)
    cutoff = now - timedelta(hours=hours)
    with session(db_path) as conn:
        rows = [
            dict(row)
            for row in conn.execute(
                "SELECT u.id, u.key, u.uploaded_at FROM cloud_uploads u "
                "WHERE u.status = 'uploaded' AND EXISTS ("
                "  SELECT 1 FROM publications p "
                "  WHERE p.video_id = u.video_id AND p.status = 'published')"
            ).fetchall()
        ]
    stale = []
    for row in rows:
        try:
            uploaded = datetime.strptime(row["uploaded_at"], "%Y-%m-%d %H:%M:%S")
        except (TypeError, ValueError):
            continue
        if uploaded <= cutoff:
            stale.append(row)
    if not stale:
        return {"deleted": 0, "errors": 0}
    if storage is None and not settings.r2_configured:
        return {"deleted": 0, "errors": 0, "skipped": "R2 not configured"}
    deleted = _delete_rows(stale, db_path, _storage(storage))
    return {"deleted": deleted, "errors": len(stale) - deleted}
