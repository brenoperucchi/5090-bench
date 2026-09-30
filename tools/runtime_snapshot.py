"""Schema and unknown-preserving normalizer for executable runtime evidence.

The module validates an evidence *shape* only. It never probes a process,
server, model, or GPU and it never turns an omitted field into an observation.
Inputs cross the shared finite-JSON boundary before they are copied into the
unknown-preserving template.  An explicitly supplied but invalid value is
rejected; ``unknown`` represents absence of an observation, not a malformed
one.
"""

from __future__ import annotations

from typing import Any, Mapping

from tools.json_safety import MAX_JSON_DEPTH, normalize_json


SCHEMA_VERSION = "runtime-snapshot-v1"

# ``MAX_JSON_DEPTH`` is intentionally re-exported for callers that need to
# construct boundary fixtures without importing the implementation module.
__all__ = [
    "MAX_JSON_DEPTH",
    "SCHEMA_VERSION",
    "normalize_snapshot",
    "unknown_snapshot",
    "validate_snapshot",
]

_SECTIONS = {
    "process": ("pid", "listener", "command_line", "binary", "binary_sha256"),
    "server": ("version", "endpoint", "settings", "log_path", "logs"),
    "model": ("name", "digest", "runner", "layers"),
    "gpu": ("memory_used_bytes", "memory_free_bytes", "residency", "spill"),
}
_TOP_LEVEL_FIELDS = {"schema_version", "captured_at", "status", *(_SECTIONS.keys())}
_STRING_FIELDS = {
    "binary",
    "binary_sha256",
    "version",
    "endpoint",
    "log_path",
    "name",
    "digest",
    "runner",
}
_INTEGER_FIELDS = {"pid", "layers", "memory_used_bytes", "memory_free_bytes"}
_FLEXIBLE_FIELDS = {"listener", "command_line", "settings", "logs", "residency", "spill"}


def unknown_snapshot() -> dict[str, Any]:
    """Return a complete schema whose unobserved fields are explicit unknowns."""
    return {
        "schema_version": SCHEMA_VERSION,
        "captured_at": None,
        "status": "unknown",
        **{section: {field: None for field in fields} for section, fields in _SECTIONS.items()},
    }


def normalize_snapshot(value: Mapping[str, Any] | None) -> dict[str, Any]:
    """Overlay observed fields on the unknown template; never infer omissions.

    ``None`` and an empty object mean that no observation was supplied and
    produce the explicit unknown template.  A supplied value outside the
    finite JSON domain raises a stable ``ValueError`` instead of silently
    erasing the reason for rejection.  A finite JSON root with the wrong type
    raises ``snapshot_not_object``.
    """
    normalized = unknown_snapshot()
    if value is None:
        return normalized
    try:
        value = normalize_json(value)
    except ValueError as exc:
        raise ValueError("snapshot_not_json") from exc
    if not isinstance(value, Mapping):
        raise ValueError("snapshot_not_object")
    if not value:
        return normalized
    schema_errors = validate_snapshot(value)
    if schema_errors:
        reason = schema_errors[0]
        if reason == "snapshot_not_json":
            raise ValueError(reason)
        if reason in {"snapshot_not_object", "snapshot_schema_version"}:
            raise ValueError(reason)
        raise ValueError("snapshot_schema")
    if "captured_at" in value:
        normalized["captured_at"] = value["captured_at"]
    for section, fields in _SECTIONS.items():
        source = value.get(section)
        if isinstance(source, Mapping):
            normalized[section].update({field: source[field] for field in fields if field in source})
    normalized["status"] = "known" if _known_values(normalized) else "unknown"
    return normalized


def validate_snapshot(value: Mapping[str, Any]) -> list[str]:
    """Return schema errors; missing fields are valid and remain unknown."""
    try:
        value = normalize_json(value)
    except ValueError:
        return ["snapshot_not_json"]
    errors: list[str] = []
    if not isinstance(value, Mapping):
        return ["snapshot_not_object"]
    if set(value) - _TOP_LEVEL_FIELDS:
        errors.append("snapshot_schema")
    if value.get("schema_version", SCHEMA_VERSION) != SCHEMA_VERSION:
        errors.append("snapshot_schema_version")
    if "status" in value and (not isinstance(value["status"], str) or value["status"] not in {"unknown", "known"}):
        errors.append("snapshot_schema")
    if "captured_at" in value and value["captured_at"] is not None and (
        not isinstance(value["captured_at"], str) or not value["captured_at"]
    ):
        errors.append("snapshot_schema")
    for section, fields in _SECTIONS.items():
        source = value.get(section)
        if source is None:
            continue
        if not isinstance(source, Mapping):
            errors.append(f"{section} must be an object")
            continue
        if set(source) - set(fields):
            errors.append("snapshot_schema")
        for field in fields:
            if field not in source or source[field] is None:
                continue
            item = source[field]
            if field in _INTEGER_FIELDS:
                if type(item) is not int or item < 0:
                    errors.append(f"{section}.{field} must be a nonnegative integer or null")
            elif field in _STRING_FIELDS:
                if not isinstance(item, str) or not item:
                    errors.append(f"{section}.{field} must be a non-empty string or null")
            elif field in _FLEXIBLE_FIELDS:
                if not isinstance(item, (str, bool, list, dict)):
                    errors.append(f"{section}.{field} has an unsupported type")
    return errors


def _known_values(snapshot: Mapping[str, Any]) -> bool:
    return any(
        isinstance(snapshot.get(section), Mapping)
        and any(snapshot[section].get(field) is not None for field in fields)
        for section, fields in _SECTIONS.items()
    )
