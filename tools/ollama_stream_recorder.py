"""Offline-safe adapter for recording an injected NDJSON HTTP-like stream.

This module deliberately has no HTTP client and no default endpoint.  A caller
supplies a transport so tests and later HTTP integrations can control network
behaviour explicitly.  JSONL writes are append-and-flush convenience records;
they do not claim fsync, atomic multi-record transactions, or crash durability.

The public record is a redacted summary.  Request fields and raw stream data
belong only in the private record and must only be sent to ``private_writer``.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import uuid
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from tools.stream_record import parse_stream


@dataclass(frozen=True)
class TransportResponse:
    """The only response shape required from an injected transport."""

    status_code: int | None
    lines: Iterable[bytes | str]


@dataclass(frozen=True)
class RecordResult:
    """In-memory records; write only ``public`` to shareable artifacts."""

    public: dict[str, Any]
    private: dict[str, Any]


class JsonlWriter:
    """Append-and-flush JSONL writer; it intentionally makes no durability claim."""

    def __init__(self, path: Path, handle: Any):
        self.path = path
        self._handle = handle

    def write(self, record: Mapping[str, Any]) -> None:
        self._handle.write(json.dumps(_json_safe(record), sort_keys=True, separators=(",", ":")) + "\n")
        self._handle.flush()

    def close(self) -> None:
        self._handle.close()


def create_jsonl_writer(directory: str | Path, label: str) -> JsonlWriter:
    """Provision a collision-safe, newly-created JSONL file in an existing directory."""
    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]*", label):
        raise ValueError("label must contain lowercase letters, digits, '_' or '-'")
    target_directory = Path(directory)
    if not target_directory.is_dir():
        raise ValueError("directory must already exist")
    while True:
        path = target_directory / f"{label}-{uuid.uuid4().hex}.jsonl"
        try:
            descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            continue
        return JsonlWriter(path, os.fdopen(descriptor, "w", encoding="utf-8"))


def record_stream(
    *,
    endpoint: str,
    request_fields: Mapping[str, Any],
    transport: Callable[[str, Mapping[str, Any]], TransportResponse],
    run_id: str,
    campaign_id: str,
    private_writer: JsonlWriter | None = None,
    public_writer: JsonlWriter | None = None,
    now: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> RecordResult:
    """Record an injected stream without performing network I/O itself.

    ``transport`` receives the explicit endpoint and a detached request copy.
    The public record identifies the canonical input mapping, not wire bytes:
    an HTTP integration must separately capture its serializer's exact bytes.
    If the iterator fails, no partial parser result is represented as complete.
    """
    if not isinstance(endpoint, str) or not endpoint.strip():
        raise ValueError("endpoint is required; this recorder has no default endpoint")
    if not isinstance(run_id, str) or not run_id:
        raise ValueError("run_id is required")
    if not isinstance(campaign_id, str) or not campaign_id:
        raise ValueError("campaign_id is required")

    record_id = uuid.uuid4().hex
    started_at = _timestamp(now())
    request_snapshot = _canonical_request(request_fields)
    private_identity = {
        "record_id": record_id,
        "run_id": run_id,
        "campaign_id": campaign_id,
        "endpoint": endpoint,
        "canonical_request_fields_sha256": _sha256(request_snapshot),
        "started_at": started_at,
    }
    public_identity = {
        "record_id": record_id,
        "run_id_sha256": _sha256(run_id),
        "campaign_id_sha256": _sha256(campaign_id),
        "endpoint_sha256": _sha256(endpoint),
        "canonical_request_fields_sha256": _sha256(request_snapshot),
        "started_at": started_at,
    }
    private_started = {"record_type": "started", **private_identity, "request_fields": json.loads(request_snapshot)}
    public_started = {"record_type": "started", **public_identity}
    if private_writer:
        private_writer.write(private_started)
    if public_writer:
        public_writer.write(public_started)

    observed_raw_lines: list[bytes | str] = []
    http_status: int | None = None
    parsed_stream: dict[str, Any] | None = None
    transport_error: dict[str, str] | None = None
    try:
        response = transport(endpoint, json.loads(request_snapshot))
        if not isinstance(response, TransportResponse):
            raise TypeError("transport must return TransportResponse")
        http_status = response.status_code

        def observed_lines() -> Iterable[bytes | str]:
            for line in response.lines:
                observed_raw_lines.append(line)
                yield line

        parsed_stream = parse_stream(observed_lines())
        status = parsed_stream["status"]
        if not isinstance(http_status, int) or isinstance(http_status, bool) or not 200 <= http_status < 300:
            status = "http_error"
    except Exception as exc:  # Records the failure; never labels it complete.
        status = "transport_error"
        transport_error = {"type": type(exc).__name__, "message": str(exc)}

    ended_at = _timestamp(now())
    public_stream = _public_stream(parsed_stream)
    public = {
        "record_type": "result",
        **public_identity,
        "ended_at": ended_at,
        "status": status,
        "http_status": _public_http_status(http_status),
        "parsed_stream": public_stream,
    }
    if transport_error is not None:
        public["transport_error"] = {"type": transport_error["type"]}
    private = {
        "record_type": "result",
        **private_identity,
        "ended_at": ended_at,
        "status": status,
        "http_status": http_status,
        "request_fields": json.loads(request_snapshot),
        "parsed_stream": parsed_stream,
        "observed_raw_lines": observed_raw_lines,
    }
    if transport_error is not None:
        private["transport_error"] = transport_error
    if private_writer:
        private_writer.write(private)
    if public_writer:
        public_writer.write(public)
    return RecordResult(public=public, private=private)


def _canonical_request(request_fields: Mapping[str, Any]) -> str:
    return json.dumps(_json_safe(request_fields), sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _public_done_reason(value: Any) -> str | None:
    if isinstance(value, str) and value in {"stop", "length"}:
        return value
    if value is None:
        return None
    return "other"


def _public_stream(parsed_stream: dict[str, Any] | None) -> dict[str, Any] | None:
    if parsed_stream is None:
        return None
    # Terminal events and diagnostics can include server paths or echoed data.
    return {
        "status": parsed_stream.get("status"),
        "task_success": parsed_stream.get("task_success"),
        "done_reason": _public_done_reason(parsed_stream.get("done_reason")),
        "metrics": _public_metrics(parsed_stream.get("metrics")),
        "metrics_valid": parsed_stream.get("metrics_valid"),
        "event_count": len(parsed_stream.get("raw_events", [])),
        "validation_error_count": len(parsed_stream.get("validation_errors", [])),
    }


def _public_metrics(value: Any) -> dict[str, int | None]:
    if not isinstance(value, dict):
        return {}
    return {
        str(field): (metric if type(metric) is int and metric >= 0 else None)
        for field, metric in value.items()
    }


def _public_http_status(value: Any) -> int | None:
    """Expose only a real integer status; adapter values stay private."""
    if type(value) is int:
        return value
    return None


def _timestamp(value: datetime) -> str:
    if value.tzinfo is None:
        raise ValueError("now() must return a timezone-aware datetime")
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _json_safe(value: Any) -> Any:
    if isinstance(value, bytes):
        return {"encoding": "base64", "data": base64.b64encode(value).decode("ascii")}
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return value
