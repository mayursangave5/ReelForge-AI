from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler

from .config import LOGS_DIR

_FMT = "%(asctime)s %(levelname)-7s %(name)s: %(message)s"


def setup_logging(level: int = logging.INFO) -> logging.Logger:
    root = logging.getLogger()
    if root.handlers:
        return logging.getLogger("reels")

    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    formatter = logging.Formatter(_FMT)

    console = logging.StreamHandler()
    console.setFormatter(formatter)
    root.addHandler(console)

    file_handler = RotatingFileHandler(
        LOGS_DIR / "reels.log", maxBytes=5_000_000, backupCount=5, encoding="utf-8"
    )
    file_handler.setFormatter(formatter)
    root.addHandler(file_handler)

    root.setLevel(level)
    for noisy in ("httpx", "httpcore", "urllib3"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    return logging.getLogger("reels")
