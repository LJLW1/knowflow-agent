import json
import logging

from knowflow.observability import JsonFormatter, redact


def test_redaction_removes_common_secret_fields() -> None:
    payload = redact(
        {
            "api_key": "secret",
            "nested": {"Authorization": "Bearer x"},
            "safe": "ok",
            "path": "/healthz",
        }
    )
    assert payload["api_key"] == "[REDACTED]"
    assert payload["nested"]["Authorization"] == "[REDACTED]"
    assert payload["safe"] == "ok"
    assert payload["path"] == "/healthz"


def test_json_formatter_emits_trace_field() -> None:
    record = logging.LogRecord("knowflow", logging.INFO, "", 0, "request", (), None)
    record.fields = {"trace_id": "tr_1"}  # type: ignore[attr-defined]
    payload = json.loads(JsonFormatter().format(record))
    assert payload["trace_id"] == "tr_1"
    assert payload["message"] == "request"
