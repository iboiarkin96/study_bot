"""Centralized logging setup: plain text or JSON lines for files and log platforms."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

from app.core.config import Settings
from app.core.request_context import request_id_var, span_id_var, trace_id_var

DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
TEXT_LOG_FORMAT = "%(asctime)s | %(levelname)s | %(name)s | req=%(request_id)s | %(message)s"


class RequestContextFilter(logging.Filter):
    """Attach correlation fields from contextvars for formatters."""

    def filter(self, record: logging.LogRecord) -> bool:
        rid = request_id_var.get(None)
        record.request_id = rid if rid else "-"
        tid = trace_id_var.get(None)
        record.trace_id = tid if tid else ""
        sid = span_id_var.get(None)
        record.span_id = sid if sid else ""
        return True


class JsonLogFormatter(logging.Formatter):
    """One JSON object per line (NDJSON), suitable for Filebeat → Elasticsearch."""

    def __init__(self, *, service_name: str, app_env: str) -> None:
        super().__init__()
        self._service_name = service_name
        self._app_env = app_env

    def format(self, record: logging.LogRecord) -> str:
        """Serialize ``record`` to a single JSON line with ECS-friendly keys.

        Args:
            record: Log record after :class:`RequestContextFilter` ran.

        Returns:
            UTF-8 JSON object as a string (no trailing newline; StreamHandler adds one).
        """
        ts = datetime.fromtimestamp(record.created, tz=UTC)
        payload: dict[str, object] = {
            "@timestamp": ts.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "service": {"name": self._service_name},
            "app_env": self._app_env,
            "request_id": getattr(record, "request_id", "-"),
        }
        trace_id = getattr(record, "trace_id", "") or None
        span_id = getattr(record, "span_id", "") or None
        payload["trace_id"] = trace_id
        payload["span_id"] = span_id
        if record.exc_info:
            payload["error"] = self.formatException(record.exc_info).strip()
        return json.dumps(payload, ensure_ascii=False)


class TextLogFormatter(logging.Formatter):
    """Plain text with optional ``exc_info`` appended."""

    def __init__(self) -> None:
        super().__init__(fmt=TEXT_LOG_FORMAT, datefmt=DATE_FORMAT)

    def format(self, record: logging.LogRecord) -> str:
        line = super().format(record)
        if record.exc_info:
            line += "\n" + self.formatException(record.exc_info).strip()
        return line


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
        settings: Log level, directory, file name, and ``log_format`` (``text`` or ``json``).

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
        filename=str(log_path),
        when="midnight",
        backupCount=14,
        encoding="utf-8",
    )
    file_handler.setLevel(level)
    ctx_filter = RequestContextFilter()
    file_handler.addFilter(ctx_filter)
    if settings.log_format == "json":
        file_handler.setFormatter(
            JsonLogFormatter(service_name=settings.log_service_name, app_env=settings.app_env)
        )
    else:
        file_handler.setFormatter(TextLogFormatter())
    root_logger.addHandler(file_handler)

    logging.captureWarnings(True)

    for logger_name in ("uvicorn", "uvicorn.error", "uvicorn.access", "fastapi"):
        framework_logger = logging.getLogger(logger_name)
        framework_logger.handlers = []
        framework_logger.propagate = True

    return log_path
