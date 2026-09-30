"""Offline validator for explicit structured-response contracts.

This module validates a caller-supplied contract and one normalized response.
It does not choose a gateway policy, call a model, or assign a quality score.
The JSON-Schema support is intentionally a small, documented subset suitable
for deterministic preflight fixtures; unsupported keywords fail closed. Both
inputs and decoded JSON values cross the shared finite-JSON safety boundary.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from typing import Any, Mapping

from tools.json_safety import MAX_JSON_DEPTH, normalize_json


_FORMATS = {"json", "text"}
_FINISH_REASONS = {"stop", "length", "tool_calls"}
_SCHEMA_KEYS = {"type", "enum", "required", "properties", "items", "minItems", "maxItems", "minLength", "maxLength", "additionalProperties"}
_JSON_TYPES = {"object", "array", "string", "number", "integer", "boolean", "null"}


@dataclass(frozen=True)
class StructuredValidation:
    """Named validation result; deliberately contains no aggregate score."""

    valid: bool
    reasons: tuple[str, ...]
    value: Any = None


def _normalize_object(value: Any, label: str) -> Mapping[str, Any]:
    try:
        normalized = normalize_json(value)
    except ValueError as exc:
        raise ValueError(f"{label} must be a finite JSON object") from exc
    if not isinstance(normalized, Mapping):
        raise ValueError(f"{label} must be an object")
    return normalized


def validate_contract(contract: Mapping[str, Any]) -> None:
    """Raise ``ValueError`` when a structured-response contract is malformed."""
    _validate_contract(_normalize_object(contract, "contract"))


def _validate_contract(contract: Mapping[str, Any]) -> None:
    if not isinstance(contract, Mapping):
        raise ValueError("contract must be an object")
    response_format = contract.get("format", "text")
    if not isinstance(response_format, str) or response_format not in _FORMATS:
        raise ValueError("format must be json or text")
    for field in ("allow_tool_only", "allow_reasoning"):
        if field in contract and type(contract[field]) is not bool:
            raise ValueError(f"{field} must be boolean")
    _validate_string_list(contract, "allowed_finish_reasons", allow_empty=False)
    if "allowed_finish_reasons" in contract and any(item not in _FINISH_REASONS for item in contract["allowed_finish_reasons"]):
        raise ValueError("allowed_finish_reasons contains an unknown reason")
    _validate_string_list(contract, "allowed_tools", allow_empty=True)
    if "required_tool_arguments" in contract:
        arguments = contract["required_tool_arguments"]
        if not isinstance(arguments, Mapping):
            raise ValueError("required_tool_arguments must be an object")
        allowed = set(contract.get("allowed_tools", []))
        for name, fields in arguments.items():
            if not isinstance(name, str) or not name or name not in allowed:
                raise ValueError("required_tool_arguments names must be allowed tools")
            if not isinstance(fields, list) or any(not isinstance(field, str) or not field for field in fields) or len(fields) != len(set(fields)):
                raise ValueError("required_tool_arguments values must be unique non-empty strings")
    if "tool_finish_reason" in contract and (not isinstance(contract["tool_finish_reason"], str) or contract["tool_finish_reason"] not in _FINISH_REASONS):
        raise ValueError("tool_finish_reason is unknown")
    if "response_schema" in contract:
        _validate_schema(contract["response_schema"])
    provenance = contract.get("provenance")
    if provenance is not None:
        if not isinstance(provenance, Mapping):
            raise ValueError("provenance must be an object")
        if "required" in provenance and type(provenance["required"]) is not bool:
            raise ValueError("provenance.required must be boolean")
        _validate_string_list(provenance, "required_fields", allow_empty=True)


def validate_structured_response(response: Mapping[str, Any], contract: Mapping[str, Any]) -> StructuredValidation:
    """Validate one normalized response against an explicit offline contract."""
    contract = _normalize_object(contract, "contract")
    _validate_contract(contract)
    try:
        response = normalize_json(response)
    except ValueError:
        return StructuredValidation(False, ("response_not_json",))
    reasons: list[str] = []
    if not isinstance(response, Mapping):
        return StructuredValidation(False, ("response_not_object",))

    stream_status = response.get("stream_status")
    if stream_status != "complete":
        known_incomplete = isinstance(stream_status, str) and stream_status in {"incomplete", "invalid_stream", "api_error", "transport_error"}
        reasons.append("stream_not_complete" if known_incomplete else "stream_status_unknown")

    finish_reason = response.get("finish_reason")
    if not isinstance(finish_reason, str):
        reasons.append("finish_reason_missing")
    else:
        allowed_reasons = contract.get("allowed_finish_reasons")
        if allowed_reasons is not None and finish_reason not in allowed_reasons:
            reasons.append("finish_reason_not_allowed")

    reasoning = response.get("reasoning")
    if reasoning is not None and not isinstance(reasoning, str):
        reasons.append("reasoning_not_text")
    elif isinstance(reasoning, str) and reasoning and contract.get("allow_reasoning", False) is not True:
        reasons.append("reasoning_not_allowed")

    tool_calls = response.get("tool_calls", [])
    if not isinstance(tool_calls, list):
        reasons.append("tool_calls_not_list")
        tool_calls = []
    _validate_tool_calls(tool_calls, contract, reasons)

    content = response.get("content")
    tool_only = bool(tool_calls) and (content is None or content == "")
    if tool_only and contract.get("allow_tool_only", False) is not True:
        reasons.append("tool_only_not_allowed")
    if tool_only and contract.get("tool_finish_reason") is not None and finish_reason != contract["tool_finish_reason"]:
        reasons.append("tool_finish_reason_mismatch")

    parsed: Any = None
    response_format = contract.get("format", "text")
    if not tool_only:
        if response_format == "json":
            if not isinstance(content, str):
                reasons.append("json_content_not_text")
            else:
                try:
                    parsed = json.loads(
                        content,
                        parse_constant=_reject_json_constant,
                        parse_float=_parse_json_float,
                    )
                except (TypeError, ValueError, json.JSONDecodeError, RecursionError):
                    reasons.append("invalid_json")
                else:
                    try:
                        parsed = normalize_json(parsed)
                    except ValueError:
                        parsed = None
                        reasons.append("json_not_json")
                    else:
                        if "response_schema" in contract:
                            reasons.extend(_schema_errors(parsed, contract["response_schema"], "$"))
        elif content is not None and not isinstance(content, str):
            reasons.append("text_content_not_text")
        elif content is None and not tool_only:
            reasons.append("content_missing")

    _validate_provenance(response, contract, reasons)
    return StructuredValidation(not reasons, tuple(reasons), parsed)


def _validate_tool_calls(calls: list[Any], contract: Mapping[str, Any], reasons: list[str]) -> None:
    allowed = contract.get("allowed_tools")
    required_arguments = contract.get("required_tool_arguments", {})
    for call in calls:
        if not isinstance(call, Mapping):
            reasons.append("tool_call_not_object")
            continue
        name = call.get("name")
        if not isinstance(name, str) or not name:
            reasons.append("tool_name_missing")
            continue
        if allowed is not None and name not in allowed:
            reasons.append("tool_not_allowed")
        arguments = call.get("arguments")
        if not isinstance(arguments, Mapping):
            reasons.append("tool_arguments_not_object")
            continue
        for field in required_arguments.get(name, []):
            if field not in arguments:
                reasons.append("tool_required_argument_missing")


def _validate_provenance(response: Mapping[str, Any], contract: Mapping[str, Any], reasons: list[str]) -> None:
    provenance = contract.get("provenance")
    if provenance is None:
        return
    required = provenance.get("required", False) is True
    entries = response.get("provenance")
    if entries is None:
        if required:
            reasons.append("provenance_missing")
        return
    if not isinstance(entries, list):
        reasons.append("provenance_not_list")
        return
    if required and not entries:
        reasons.append("provenance_missing")
        return
    fields = provenance.get("required_fields", [])
    for entry in entries:
        if not isinstance(entry, Mapping):
            reasons.append("provenance_entry_not_object")
            continue
        if any(field not in entry or not isinstance(entry[field], str) or not entry[field] for field in fields):
            reasons.append("provenance_required_field_missing")


def _validate_string_list(container: Mapping[str, Any], field: str, *, allow_empty: bool) -> None:
    if field not in container:
        return
    value = container[field]
    if not isinstance(value, list) or any(not isinstance(item, str) or not item for item in value) or len(value) != len(set(value)):
        raise ValueError(f"{field} must be a list of unique non-empty strings")
    if not allow_empty and not value:
        raise ValueError(f"{field} must not be empty")


def _validate_schema(schema: Any) -> None:
    if not isinstance(schema, Mapping):
        raise ValueError("response_schema must be an object")
    unsupported = set(schema) - _SCHEMA_KEYS
    if unsupported:
        raise ValueError(f"response_schema has unsupported keywords: {sorted(unsupported)}")
    schema_type = schema.get("type")
    if schema_type is not None:
        if not isinstance(schema_type, str) or schema_type not in _JSON_TYPES:
            raise ValueError("response_schema.type is invalid")
    if "enum" in schema and not isinstance(schema["enum"], list):
        raise ValueError("response_schema.enum must be a list")
    if "required" in schema and (not isinstance(schema["required"], list) or any(not isinstance(item, str) or not item for item in schema["required"]) or len(schema["required"]) != len(set(schema["required"]))):
        raise ValueError("response_schema.required must be unique strings")
    if "properties" in schema:
        if not isinstance(schema["properties"], Mapping):
            raise ValueError("response_schema.properties must be an object")
        for child in schema["properties"].values():
            _validate_schema(child)
    if "items" in schema:
        _validate_schema(schema["items"])
    for field in ("minItems", "maxItems", "minLength", "maxLength"):
        if field in schema and (type(schema[field]) is not int or schema[field] < 0):
            raise ValueError(f"response_schema.{field} must be a nonnegative integer")
    if "additionalProperties" in schema and type(schema["additionalProperties"]) is not bool:
        raise ValueError("response_schema.additionalProperties must be boolean")


def _schema_errors(value: Any, schema: Mapping[str, Any], path: str) -> list[str]:
    errors: list[str] = []
    schema_type = schema.get("type")
    if schema_type is not None and not _matches_type(value, schema_type):
        errors.append(f"{path}:type")
        return errors
    if "enum" in schema and not any(_json_equal(value, candidate) for candidate in schema["enum"]):
        errors.append(f"{path}:enum")
    if isinstance(value, Mapping):
        for field in schema.get("required", []):
            if field not in value:
                errors.append(f"{path}.{field}:required")
        properties = schema.get("properties", {})
        for field, child in properties.items():
            if field in value:
                errors.extend(_schema_errors(value[field], child, f"{path}.{field}"))
        if schema.get("additionalProperties") is False:
            for field in value:
                if field not in properties:
                    errors.append(f"{path}.{field}:additional")
    if isinstance(value, list):
        if "minItems" in schema and len(value) < schema["minItems"]:
            errors.append(f"{path}:minItems")
        if "maxItems" in schema and len(value) > schema["maxItems"]:
            errors.append(f"{path}:maxItems")
        if "items" in schema:
            for index, item in enumerate(value):
                errors.extend(_schema_errors(item, schema["items"], f"{path}[{index}]"))
    if isinstance(value, str):
        if "minLength" in schema and len(value) < schema["minLength"]:
            errors.append(f"{path}:minLength")
        if "maxLength" in schema and len(value) > schema["maxLength"]:
            errors.append(f"{path}:maxLength")
    return errors


def _matches_type(value: Any, schema_type: str) -> bool:
    if schema_type == "null":
        return value is None
    if schema_type == "boolean":
        return type(value) is bool
    if schema_type == "integer":
        return type(value) is int
    if schema_type == "number":
        return (type(value) is int or type(value) is float) and not isinstance(value, bool) and (type(value) is int or math.isfinite(value))
    if schema_type == "string":
        return isinstance(value, str)
    if schema_type == "object":
        return isinstance(value, Mapping)
    if schema_type == "array":
        return isinstance(value, list)
    return False


def _reject_json_constant(value: str) -> None:
    raise ValueError(f"non-standard JSON constant: {value}")


def _parse_json_float(value: str) -> float:
    """Parse a JSON decimal and reject overflow to a non-finite float."""
    parsed = float(value)
    if not math.isfinite(parsed):
        raise ValueError(f"non-finite JSON number: {value}")
    return parsed


def _json_equal(left: Any, right: Any) -> bool:
    """Compare JSON values without Python's bool-as-number equality quirk."""
    if type(left) is bool or type(right) is bool:
        return type(left) is type(right) and left == right
    if (type(left) is int or type(left) is float) and (type(right) is int or type(right) is float):
        return _finite_number(left) and _finite_number(right) and left == right
    if isinstance(left, Mapping) or isinstance(right, Mapping):
        if not isinstance(left, Mapping) or not isinstance(right, Mapping) or set(left) != set(right):
            return False
        return all(_json_equal(left[key], right[key]) for key in left)
    if isinstance(left, list) or isinstance(right, list):
        return isinstance(left, list) and isinstance(right, list) and len(left) == len(right) and all(_json_equal(a, b) for a, b in zip(left, right))
    return type(left) is type(right) and left == right


def _finite_number(value: int | float) -> bool:
    return type(value) is int or math.isfinite(value)
