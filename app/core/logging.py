"""Centralized logging setup for the application."""

from __future__ import annotations

import logging
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

from app.core.config import Settings

LOG_FORMAT = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def _resolve_log_path(settings: Settings) -> Path:
    """Resolve and ensure the directory for the rotating log file exists.

    Args:
        settings: Configuration providing ``log_dir`` and ``log_file_name``.

    Returns:
        Absolute path to the log file (parent directories created as needed).
    """
    log_dir = Path(settings.log_dir).expanduser()
    if not log_dir.is_absolute():
        log_dir = Path.cwd() / log_dir
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir / settings.log_file_name


def configure_logging(settings: Settings) -> Path:
    """Reset root logging to a single timed rotating file and propagate framework logs.

    Args:
        settings: Log level, directory, and file name.

    Returns:
        Absolute path of the active log file.
    """
    log_path = _resolve_log_path(settings)
    level = getattr(logging, settings.log_level, logging.INFO)

    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    for handler in list(root_logger.handlers):
        root_logger.removeHandler(handler)

    file_handler = TimedRotatingFileHandler(
        filename=log_path,
        when="midnight",
        backupCount=14,
        encoding="utf-8",
    )
    file_handler.setLevel(level)
    file_handler.setFormatter(logging.Formatter(fmt=LOG_FORMAT, datefmt=DATE_FORMAT))
    root_logger.addHandler(file_handler)

    logging.captureWarnings(True)

    # Route framework logs through root file handler.
    for logger_name in ("uvicorn", "uvicorn.error", "uvicorn.access", "fastapi"):
        framework_logger = logging.getLogger(logger_name)
        framework_logger.handlers = []
        framework_logger.propagate = True

    return log_path
