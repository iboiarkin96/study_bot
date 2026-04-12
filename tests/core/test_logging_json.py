"""JSON log formatter and request context filter tests."""

from __future__ import annotations

import json
import logging
import sys

from app.core.logging import JsonLogFormatter, RequestContextFilter, TextLogFormatter
from app.core.request_context import (
    normalize_request_id_header,
    request_id_var,
    reset_request_context,
    span_id_var,
    trace_id_var,
)


def test_json_formatter_includes_correlation_and_null_trace_fields() -> None:
    formatter = JsonLogFormatter(service_name="study-app-api", app_env="qa")
    logger = logging.getLogger("test_json_fmt")
    record = logger.makeRecord(
        "test_json_fmt",
        logging.INFO,
        __file__,
        1,
        "hello",
        (),
        None,
    )
    RequestContextFilter().filter(record)
    line = formatter.format(record)
    data = json.loads(line)
    assert data["message"] == "hello"
    assert data["level"] == "INFO"
    assert data["service"] == {"name": "study-app-api"}
    assert data["app_env"] == "qa"
    assert data["request_id"] == "-"
    assert data["trace_id"] is None
    assert data["span_id"] is None
    assert "@timestamp" in data


def test_json_formatter_with_request_id_in_context() -> None:
    formatter = JsonLogFormatter(service_name="study-app-api", app_env="dev")
    token = request_id_var.set("req-abc")
    try:
        record = logging.LogRecord(
            name="t",
            level=logging.WARNING,
            pathname=__file__,
            lineno=10,
            msg="warn",
            args=(),
            exc_info=None,
        )
        RequestContextFilter().filter(record)
        data = json.loads(formatter.format(record))
        assert data["request_id"] == "req-abc"
    finally:
        request_id_var.reset(token)


def test_json_formatter_includes_error_when_exc_info() -> None:
    formatter = JsonLogFormatter(service_name="study-app-api", app_env="qa")
    try:
        raise ValueError("boom")
    except ValueError:
        exc = sys.exc_info()
        record = logging.LogRecord(
            name="t",
            level=logging.ERROR,
            pathname=__file__,
            lineno=1,
            msg="failed",
            args=(),
            exc_info=exc,
        )
    RequestContextFilter().filter(record)
    data = json.loads(formatter.format(record))
    assert "error" in data
    assert "ValueError" in data["error"]


def test_text_formatter_appends_traceback_when_exc_info() -> None:
    formatter = TextLogFormatter()
    try:
        raise RuntimeError("x")
    except RuntimeError:
        exc = sys.exc_info()
        record = logging.LogRecord(
            name="t",
            level=logging.ERROR,
            pathname=__file__,
            lineno=1,
            msg="oops",
            args=(),
            exc_info=exc,
        )
    RequestContextFilter().filter(record)
    text = formatter.format(record)
    assert "RuntimeError" in text
    assert "oops" in text


def test_normalize_request_id_rejects_too_long() -> None:
    assert normalize_request_id_header("a" * 129) is None


def test_reset_request_context_clears_id() -> None:
    token = request_id_var.set("rid")
    reset_request_context(token)
    assert request_id_var.get() is None


def test_reset_request_context_clears_trace_and_span() -> None:
    rt = request_id_var.set("r")
    tt = trace_id_var.set("t")
    st = span_id_var.set("s")
    reset_request_context(rt, tt, st)
    assert request_id_var.get() is None
    assert trace_id_var.get() is None
    assert span_id_var.get() is None


def test_json_formatter_includes_trace_and_span_when_set() -> None:
    formatter = JsonLogFormatter(service_name="study-app-api", app_env="dev")
    tt = trace_id_var.set("trace-1")
    st = span_id_var.set("span-1")
    try:
        record = logging.LogRecord(
            name="t",
            level=logging.INFO,
            pathname=__file__,
            lineno=1,
            msg="ok",
            args=(),
            exc_info=None,
        )
        RequestContextFilter().filter(record)
        data = json.loads(formatter.format(record))
        assert data["trace_id"] == "trace-1"
        assert data["span_id"] == "span-1"
    finally:
        trace_id_var.reset(tt)
        span_id_var.reset(st)
