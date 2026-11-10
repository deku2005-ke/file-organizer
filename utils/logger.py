"""Application logging: writes to logs/file_organizer.log (created automatically)."""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler

from utils.paths import LOG_FILE, ensure_app_dirs

ROOT_NAME = "file_organizer"


def setup_logging() -> None:
    """Attach a rotating file handler once. Safe to call repeatedly."""
    logger = logging.getLogger(ROOT_NAME)
    if logger.handlers:
        return
    ensure_app_dirs()
    handler = RotatingFileHandler(LOG_FILE, maxBytes=500_000, backupCount=3, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)


def get_logger(name: str) -> logging.Logger:
    """Return a child logger such as 'file_organizer.organizer'."""
    return logging.getLogger(f"{ROOT_NAME}.{name}")
