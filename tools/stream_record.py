"""Offline NDJSON payload parser; this is not a network recorder.

``complete`` means a syntactically valid payload stream ended with boolean
``done: true``. It makes no claim about HTTP transport, answer correctness,
GPU residency, context retention, or successful tool execution. Callers must
provide complete NDJSON lines, not arbitrary network chunks. Blank lines are
ignored. Timing and HTTP status must be recorded by a separate adapter.
"""

import json
from collections.abc import Iterable


METRIC_FIELDS = (
    "total_duration", "load_duration", "prompt_eval_count",
    "prompt_eval_duration", "eval_count", "eval_duration",
)


def parse_stream(lines: Iterable[bytes | str]) -> dict:
    """Preserve received events and fail closed on malformed/unterminated input.

    Missing metrics remain None and set ``metrics_valid`` to None; present
    metrics must be nonnegative integers (booleans are rejected). Presence of an error key conservatively
    marks an API-error terminal, even when its value is null or empty; this
    takes precedence over done in the same event. Every event after done
    (or an API error) is invalid,
    including another terminal. Raw bytes are retained on UTF-8 failure;
    consumers serializing results must explicitly encode those bytes.
    Iterator/transport exceptions propagate: this function cannot certify
    completion when its input reader fails. A decoder recursion failure from a
    deeply nested line is content validation and is recorded as malformed JSON
    rather than escaping as a transport failure.

    The error field is status-dependent: None on complete, an explanation
    on incomplete, and the original API error value on api_error (possibly
    null). On invalid_stream it retains a nonempty API error if present,
    otherwise it contains the validation diagnostic summary. Full validation
    diagnostics always live in validation_errors and original error values
    remain in raw_events. Consult status, not error truthiness, for success.
    task_success is always None pending an independent consumer's evaluation.
    """
    result = {
        "status": "incomplete", "error": None, "task_success": None,
        "raw_lines": [], "raw_events": [], "terminal_event": None,
        "done_reason": None,
        "metrics": {field: None for field in METRIC_FIELDS}, "metrics_valid": None,
        "validation_errors": [],
    }
    ended = False
    api_error_seen = False

    def invalid(message):
        result["validation_errors"].append(message)

    for number, line in enumerate(lines, 1):
        if isinstance(line, bytes):
            try:
                line = line.decode("utf-8")
            except UnicodeDecodeError:
                result["raw_lines"].append(line)
                invalid(f"line {number}: invalid UTF-8")
                continue
        if not isinstance(line, str):
            result["raw_lines"].append(line)
            invalid(f"line {number}: expected bytes or str")
            continue
        result["raw_lines"].append(line)
        if not line.strip():
            continue
        if ended:
            invalid(f"line {number}: data after terminal event")
        try:
            event = json.loads(line)
        except (TypeError, ValueError, json.JSONDecodeError, RecursionError):
            invalid(f"line {number}: malformed JSON")
            continue
        result["raw_events"].append(event)
        if not isinstance(event, dict):
            invalid(f"line {number}: expected JSON object")
            continue
        if "done" in event and type(event["done"]) is not bool:
            invalid(f"line {number}: done must be boolean")
        # Preserve all events but never overwrite the first terminal.
        if ended:
            continue
        if "error" in event:
            api_error_seen = True
            result["error"] = event["error"]
            ended = True
            result["terminal_event"] = event
        elif event.get("done") is True:
            ended = True
            result["terminal_event"] = event
        if ended:
            result["done_reason"] = event.get("done_reason")
            result["metrics"] = {field: event.get(field) for field in METRIC_FIELDS}
            present_metrics = [value for value in result["metrics"].values() if value is not None]
            if not present_metrics:
                result["metrics_valid"] = None
            elif all(type(value) is int and value >= 0 for value in present_metrics):
                result["metrics_valid"] = True
            else:
                result["metrics_valid"] = False
                invalid(f"line {number}: metrics must be nonnegative integers")

    if result["validation_errors"]:
        result["status"] = "invalid_stream"
        if not api_error_seen or not result["error"]:
            result["error"] = "; ".join(result["validation_errors"])
    elif api_error_seen:
        result["status"] = "api_error"
    elif ended:
        result["status"] = "complete"
    else:
        result["error"] = "stream ended without boolean done=true or API error"
    return result
