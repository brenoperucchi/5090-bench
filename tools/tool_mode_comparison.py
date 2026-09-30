"""Offline packet and contract checks for native-tool versus JSON arms.

The packet fixes one logical request across native, JSON-envelope and control
arms.  The validator checks a normalized multi-turn transcript; it does not
call a model, render a prompt, infer semantic quality, or produce a score.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from typing import Any, Mapping

from tools.json_safety import MAX_JSON_DEPTH, normalize_json


SCHEMA_VERSION = "tool-mode-comparison-v1"
ARM_MODES = ("native", "json", "control")
_JSON_TYPES = {"object", "array", "string", "number", "integer", "boolean", "null"}
_ARGUMENT_SCHEMA_KEYS = {
    "type",
    "required",
    "properties",
    "items",
    "enum",
    "minItems",
    "maxItems",
    "minLength",
    "maxLength",
    "additionalProperties",
}
_ROLES = {"system", "user", "assistant", "tool"}
_RENDERED_STATES = {"captured", "unknown", "unavailable"}
_FINISH_REASONS = {"stop", "length", "tool_calls"}
MAX_TOOL_ROUNDS = 2

DEFAULT_PROMPT = "Retrieve invoice demo-001 and report its current status."
_INSTRUCTIONS = {
    "native": (
        "Use the supplied lookup tool when the request needs invoice data. "
        "After the tool result, answer the user and identify which call result you used."
    ),
    "json": (
        "When invoice data is needed, emit a JSON object with a tool_calls array "
        "containing name, id and arguments. After the tool result, emit an answer "
        "object and list the used_tool_call_ids."
    ),
    "control": "Do not call tools. Answer only from information already in the conversation.",
}
DEFAULT_TOOL = {
    "name": "lookup_invoice",
    "description": "Look up one invoice by its identifier.",
    "parameters": {
        "type": "object",
        "required": ["invoice_id"],
        "properties": {"invoice_id": {"type": "string", "minLength": 1}},
        "additionalProperties": False,
    },
}


@dataclass(frozen=True)
class ToolValidation:
    """Named transcript result; deliberately contains no aggregate score."""

    valid: bool
    reasons: tuple[str, ...]


def canonical_json(value: Any) -> bytes:
    """Serialize a packet value deterministically for hashing."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")


def _safe_json_normalize(value: Any) -> Any:
    """Copy JSON-compatible values while rejecting cycles and deep input."""
    return normalize_json(value)


def _instructions_for(mode: str, tool: Mapping[str, Any]) -> str:
    """Return deterministic instructions, including the JSON arm's tool definition."""
    base = _INSTRUCTIONS[mode]
    if mode == "json":
        definition = canonical_json(tool).decode("utf-8")
        return f"{base}\nTool definition (use this exact logical interface): {definition}"
    return base


def _request_for(mode: str, model: str, prompt: str, tool: Mapping[str, Any]) -> dict[str, Any]:
    instructions = _instructions_for(mode, tool)
    request: dict[str, Any] = {
        "model": model,
        "messages": [
            {"role": "system", "content": instructions},
            {"role": "user", "content": prompt},
        ],
        "stream": True,
        "options": {"temperature": 0},
    }
    if mode == "native":
        # The tool was already normalized; normalize again to produce an
        # independent JSON clone without recursive ``copy.deepcopy`` escapes.
        request["tools"] = [_safe_json_normalize(tool)]
    elif mode == "json":
        request["format"] = "json"
    else:
        request["tools"] = []
    return request


def _contract_for(mode: str, tool: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "mode": mode,
        "tool_name": tool["name"] if mode != "control" else None,
        "tool_schema": _safe_json_normalize(tool["parameters"]) if mode != "control" else None,
        "max_tool_rounds": MAX_TOOL_ROUNDS,
        "require_result_use": mode != "control",
        "wire": {"native": "tool_calls", "json": "json_envelope", "control": "none"}[mode],
        "final_json_key": "answer" if mode == "json" else None,
    }


def build_comparison_packet(
    *,
    model: str = "qwen3:14b",
    prompt: str = DEFAULT_PROMPT,
    tool: Mapping[str, Any] = DEFAULT_TOOL,
) -> dict[str, Any]:
    """Build the preregistered three-arm packet without an execution path."""
    if not isinstance(model, str) or not model:
        raise ValueError("model must be a non-empty string")
    if not isinstance(prompt, str) or not prompt:
        raise ValueError("prompt must be a non-empty string")
    model = _safe_json_normalize(model)
    prompt = _safe_json_normalize(prompt)
    normalized_tool = _normalize_tool(tool)
    arms: list[dict[str, Any]] = []
    for mode in ARM_MODES:
        request = _request_for(mode, model, prompt, normalized_tool)
        contract = _contract_for(mode, normalized_tool)
        instructions = _instructions_for(mode, normalized_tool)
        arm = {
            "arm_id": f"{mode}-v1",
            "mode": mode,
            "instructions_sha256": _sha256_text(instructions),
            "request": request,
            "serialized_request_sha256": _sha256(canonical_json(request)),
            "rendered_input": None,
            "rendered_input_status": "unknown",
            "contract": contract,
        }
        arms.append(arm)
    packet: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "packet_id": "tool-mode-comparison-v1",
        "model": model,
        "prompt": prompt,
        "prompt_sha256": _sha256_text(prompt),
        "tool": normalized_tool,
        "arms": arms,
        "can_execute": False,
    }
    try:
        # Validate the complete artifact, not just each component.  The fixed
        # packet envelope adds nesting around the tool and can otherwise make
        # a component-valid tool fail its own consumer's depth boundary.
        packet = _safe_json_normalize(packet)
    except ValueError as exc:
        raise ValueError("comparison packet exceeds the JSON contract") from exc
    packet["packet_sha256"] = _sha256(canonical_json(packet))
    return packet


def validate_packet(packet: Mapping[str, Any]) -> list[str]:
    """Return packet contract errors, including tampered serialized hashes."""
    try:
        packet = _safe_json_normalize(packet)
    except ValueError:
        return ["packet_not_json_serializable"]
    errors: list[str] = []
    if not isinstance(packet, Mapping):
        return ["packet_not_object"]
    if packet.get("schema_version") != SCHEMA_VERSION:
        errors.append("schema_version_invalid")
    if packet.get("packet_id") != "tool-mode-comparison-v1":
        errors.append("packet_id_invalid")
    if not isinstance(packet.get("model"), str) or not packet["model"]:
        errors.append("model_invalid")
    if not isinstance(packet.get("prompt"), str) or not packet["prompt"]:
        errors.append("prompt_invalid")
    prompt = packet.get("prompt")
    if isinstance(prompt, str) and prompt:
        if packet.get("prompt_sha256") != _sha256_text(prompt):
            errors.append("prompt_hash_mismatch")
    else:
        errors.append("prompt_hash_mismatch")
    if packet.get("can_execute") is not False:
        errors.append("execution_not_disabled")
    try:
        normalized_tool = _normalize_tool(packet.get("tool"))
    except (TypeError, ValueError):
        normalized_tool = None
        errors.append("tool_schema_invalid")
    arms = packet.get("arms")
    if not isinstance(arms, list):
        errors.append("arms_not_list")
        return errors
    seen: set[str] = set()
    for arm in arms:
        if not isinstance(arm, Mapping):
            errors.append("arm_not_object")
            continue
        mode = arm.get("mode")
        if mode not in ARM_MODES:
            errors.append("arm_mode_invalid")
            continue
        if mode in seen:
            errors.append("arm_mode_duplicate")
        seen.add(mode)
        if arm.get("arm_id") != f"{mode}-v1":
            errors.append(f"{mode}:arm_id_invalid")
        request = arm.get("request")
        if not isinstance(request, Mapping):
            errors.append(f"{mode}:request_not_object")
        else:
            try:
                expected_hash = _sha256(canonical_json(request))
            except (TypeError, ValueError):
                expected_hash = None
            if expected_hash is None or arm.get("serialized_request_sha256") != expected_hash:
                errors.append(f"{mode}:request_hash_mismatch")
            if normalized_tool is not None and isinstance(packet.get("model"), str) and isinstance(prompt, str) and prompt:
                expected_request = _request_for(mode, packet["model"], prompt, normalized_tool)
                expected_contract = _contract_for(mode, normalized_tool)
                expected_instructions = _instructions_for(mode, normalized_tool)
                if not _canonical_equal(request, expected_request):
                    errors.append(f"{mode}:request_invariant_mismatch")
                if not _canonical_equal(arm.get("contract"), expected_contract):
                    errors.append(f"{mode}:contract_invariant_mismatch")
            else:
                expected_instructions = _INSTRUCTIONS[mode]
            if arm.get("instructions_sha256") != _sha256_text(expected_instructions):
                errors.append(f"{mode}:instructions_hash_mismatch")
        status = arm.get("rendered_input_status")
        if not isinstance(status, str) or status not in _RENDERED_STATES:
            errors.append(f"{mode}:rendered_input_status_invalid")
        elif status == "captured" and not isinstance(arm.get("rendered_input"), str):
            errors.append(f"{mode}:rendered_input_missing")
        elif status != "captured" and arm.get("rendered_input") is not None:
            errors.append(f"{mode}:rendered_input_must_be_null")
        contract = arm.get("contract")
        if not isinstance(contract, Mapping) or contract.get("mode") != mode:
            errors.append(f"{mode}:contract_invalid")
    if seen != set(ARM_MODES):
        errors.append("arm_set_incomplete")
    if isinstance(packet.get("packet_sha256"), str):
        unsigned = dict(packet)
        unsigned.pop("packet_sha256", None)
        try:
            expected_packet_hash = _sha256(canonical_json(unsigned))
        except (TypeError, ValueError):
            expected_packet_hash = None
        if expected_packet_hash is None or packet["packet_sha256"] != expected_packet_hash:
            errors.append("packet_hash_mismatch")
    else:
        errors.append("packet_hash_missing")
    return errors


def validate_tool_transcript(observation: Mapping[str, Any], arm: Mapping[str, Any]) -> ToolValidation:
    """Validate one normalized native/JSON/control multi-turn observation."""
    try:
        observation = _safe_json_normalize(observation)
    except ValueError:
        return ToolValidation(False, ("observation_not_json",))
    try:
        arm = _safe_json_normalize(arm)
    except ValueError:
        return ToolValidation(False, ("arm_not_json",))
    reasons: list[str] = []
    if not isinstance(observation, Mapping):
        return ToolValidation(False, ("observation_not_object",))
    contract = arm.get("contract") if isinstance(arm, Mapping) else None
    if not isinstance(contract, Mapping):
        return ToolValidation(False, ("contract_missing",))
    mode = contract.get("mode")
    if mode not in ARM_MODES:
        return ToolValidation(False, ("contract_mode_invalid",))
    contract_errors = _validate_arm_contract(contract)
    if contract_errors:
        return ToolValidation(False, tuple(dict.fromkeys(contract_errors)))
    if observation.get("arm") is not None and observation.get("arm") != mode:
        reasons.append("arm_mismatch")
    if observation.get("stream_status") != "complete":
        reasons.append("stream_not_complete")
    finish_reason = observation.get("finish_reason")
    if not isinstance(finish_reason, str) or finish_reason not in _FINISH_REASONS:
        reasons.append("finish_reason_invalid")
    turns = observation.get("turns")
    if not isinstance(turns, list) or not turns:
        return ToolValidation(False, tuple(reasons + ["turns_missing"]))

    tool_name = contract.get("tool_name")
    tool_schema = contract.get("tool_schema")
    max_rounds = contract.get("max_tool_rounds")
    if type(max_rounds) is not int or max_rounds < 0:
        reasons.append("max_tool_rounds_invalid")
        max_rounds = 0
    require_result_use = contract.get("require_result_use") is True
    pending: dict[str, Mapping[str, Any]] = {}
    completed: set[str] = set()
    all_calls: set[str] = set()
    call_rounds = 0
    last_turn_was_final = False
    last_final_used_ids: set[str] = set()

    for index, turn in enumerate(turns):
        if not isinstance(turn, Mapping):
            reasons.append(f"turn[{index}]:not_object")
            continue
        role = turn.get("role")
        if not isinstance(role, str) or role not in _ROLES:
            reasons.append(f"turn[{index}]:role_invalid")
            continue
        if pending and role in {"system", "user"}:
            reasons.append(f"turn[{index}]:tool_result_interrupted")
        if role == "tool":
            _validate_tool_result(turn, index, pending, completed, tool_name, reasons)
            call_id = turn.get("tool_call_id")
            if isinstance(call_id, str) and call_id in pending and call_id not in completed:
                completed.add(call_id)
                pending.pop(call_id, None)
            last_turn_was_final = False
            continue
        if role == "assistant":
            calls = _assistant_calls(turn, mode, index, reasons)
            if calls:
                last_turn_was_final = False
                call_rounds += 1
                if call_rounds > max_rounds:
                    reasons.append("tool_loop_exceeded")
                if mode == "control":
                    reasons.append("tool_calls_not_allowed")
                if pending:
                    reasons.append("tool_result_missing_before_next_call")
                for call in calls:
                    _validate_tool_call(call, index, tool_name, tool_schema, all_calls, reasons)
                    call_id = call.get("id") if isinstance(call, Mapping) else None
                    if isinstance(call_id, str) and call_id not in all_calls:
                        all_calls.add(call_id)
                        pending[call_id] = call
                continue
            if pending:
                reasons.append("tool_result_missing")
            content_valid = isinstance(turn.get("content"), str) and bool(turn.get("content"))
            if not content_valid:
                reasons.append(f"turn[{index}]:final_content_missing")
            used_ids = _used_result_ids(turn, mode, index, reasons, contract.get("final_json_key"))
            last_final_used_ids = used_ids
            last_turn_was_final = content_valid and not pending
            continue
        last_turn_was_final = False

    if pending:
        reasons.append("tool_result_missing")
    if not last_turn_was_final:
        reasons.append("final_response_missing")
    if require_result_use:
        missing_use = completed - last_final_used_ids
        if missing_use:
            reasons.append("tool_result_unused")
    unknown_use = last_final_used_ids - completed
    if unknown_use:
        reasons.append("used_tool_call_unknown")
    return ToolValidation(not reasons, tuple(dict.fromkeys(reasons)))


def _validate_arm_contract(contract: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    mode = contract.get("mode")
    expected_wire = {"native": "tool_calls", "json": "json_envelope", "control": "none"}.get(mode)
    if contract.get("wire") != expected_wire:
        errors.append("contract_wire_invalid")
    expected_tool = mode != "control"
    if (contract.get("require_result_use") is True) != expected_tool:
        errors.append("contract_result_use_invalid")
    expected_final_key = "answer" if mode == "json" else None
    if contract.get("final_json_key") != expected_final_key:
        errors.append("contract_final_json_key_invalid")
    rounds = contract.get("max_tool_rounds")
    if type(rounds) is not int or rounds != MAX_TOOL_ROUNDS:
        errors.append("contract_max_tool_rounds_invalid")
    if expected_tool:
        if not isinstance(contract.get("tool_name"), str) or not contract["tool_name"]:
            errors.append("contract_tool_name_invalid")
        try:
            _validate_argument_schema(contract.get("tool_schema"))
        except ValueError:
            errors.append("contract_tool_schema_invalid")
    elif contract.get("tool_name") is not None or contract.get("tool_schema") is not None:
        errors.append("contract_control_tool_fields_present")
    return errors


def _parse_json_object(content: Any, index: int, reasons: list[str]) -> Mapping[str, Any] | None:
    """Parse and normalize one JSON wire envelope at its trust boundary."""
    try:
        parsed = json.loads(content, parse_constant=_reject_constant, parse_float=_parse_float)
    except (TypeError, ValueError, json.JSONDecodeError, RecursionError):
        reasons.append(f"turn[{index}]:invalid_json")
        return None
    try:
        parsed = _safe_json_normalize(parsed)
    except ValueError:
        # ``json.loads`` accepts escaped isolated UTF-16 surrogates; the
        # normalized envelope must obey the same UTF-8 policy as all other
        # public values before its fields are trusted.
        reasons.append(f"turn[{index}]:json_not_json")
        return None
    if not isinstance(parsed, Mapping):
        reasons.append(f"turn[{index}]:json_envelope_not_object")
        return None
    return parsed


def _assistant_calls(turn: Mapping[str, Any], mode: str, index: int, reasons: list[str]) -> list[Mapping[str, Any]]:
    if mode == "native":
        calls = turn.get("tool_calls", [])
        if not isinstance(calls, list):
            reasons.append(f"turn[{index}]:tool_calls_not_list")
            return []
        normalized: list[Mapping[str, Any]] = []
        for call in calls:
            if not isinstance(call, Mapping):
                reasons.append(f"turn[{index}]:tool_call_not_object")
                continue
            normalized.append(call)
        return normalized
    if mode == "json":
        if "tool_calls" in turn:
            reasons.append(f"turn[{index}]:native_field_in_json_arm")
        content = turn.get("content")
        if not isinstance(content, str):
            reasons.append(f"turn[{index}]:json_content_not_text")
            return []
        parsed = _parse_json_object(content, index, reasons)
        if parsed is None:
            return []
        calls = parsed.get("tool_calls", [])
        if not isinstance(calls, list):
            reasons.append(f"turn[{index}]:json_tool_calls_not_list")
            return []
        normalized = []
        for call in calls:
            if not isinstance(call, Mapping):
                reasons.append(f"turn[{index}]:tool_call_not_object")
                continue
            normalized.append(call)
        return normalized
    calls = turn.get("tool_calls", [])
    if calls:
        reasons.append(f"turn[{index}]:control_tool_calls_present")
        reasons.append("tool_calls_not_allowed")
    return []


def _used_result_ids(
    turn: Mapping[str, Any], mode: str, index: int, reasons: list[str], final_json_key: Any
) -> set[str]:
    if mode == "json":
        content = turn.get("content")
        if not isinstance(content, str):
            return set()
        parsed = _parse_json_object(content, index, reasons)
        if parsed is None:
            return set()
        if not isinstance(final_json_key, str) or not final_json_key:
            reasons.append(f"turn[{index}]:json_final_key_invalid")
            return set()
        if not isinstance(parsed.get(final_json_key), str) or not parsed[final_json_key]:
            reasons.append(f"turn[{index}]:json_final_field_missing")
        value = parsed.get("used_tool_call_ids", [])
    else:
        value = turn.get("used_tool_call_ids", [])
    if not isinstance(value, list) or any(not isinstance(item, str) or not item for item in value):
        reasons.append(f"turn[{index}]:used_tool_call_ids_invalid")
        return set()
    if len(value) != len(set(value)):
        reasons.append(f"turn[{index}]:used_tool_call_ids_duplicate")
    return set(value)


def _validate_tool_call(
    call: Mapping[str, Any],
    index: int,
    expected_name: Any,
    schema: Any,
    all_calls: set[str],
    reasons: list[str],
) -> None:
    call_id = call.get("id")
    if not isinstance(call_id, str) or not call_id:
        reasons.append(f"turn[{index}]:tool_call_id_missing")
    elif call_id in all_calls:
        reasons.append(f"turn[{index}]:tool_call_id_duplicate")
    name = call.get("name")
    if name != expected_name:
        reasons.append(f"turn[{index}]:tool_name_invalid")
    arguments = call.get("arguments")
    if not isinstance(arguments, Mapping):
        reasons.append(f"turn[{index}]:tool_arguments_not_object")
        return
    try:
        arguments = _safe_json_normalize(arguments)
    except ValueError:
        reasons.append(f"turn[{index}]:tool_arguments_not_json")
        return
    if isinstance(schema, Mapping):
        _schema_argument_errors(arguments, schema, index, reasons)


def _validate_tool_result(
    turn: Mapping[str, Any],
    index: int,
    pending: Mapping[str, Mapping[str, Any]],
    completed: set[str],
    expected_name: Any,
    reasons: list[str],
) -> None:
    call_id = turn.get("tool_call_id")
    if not isinstance(call_id, str) or not call_id:
        reasons.append(f"turn[{index}]:tool_result_id_missing")
    elif call_id in completed:
        reasons.append(f"turn[{index}]:tool_result_duplicate")
    elif call_id not in pending:
        reasons.append(f"turn[{index}]:tool_result_without_call")
    if turn.get("name") != expected_name:
        reasons.append(f"turn[{index}]:tool_result_name_invalid")
    if not isinstance(turn.get("content"), str):
        reasons.append(f"turn[{index}]:tool_result_content_not_text")


def _schema_argument_errors(
    value: Any, schema: Mapping[str, Any], index: int, reasons: list[str], path: str = ""
) -> None:
    expected_type = schema.get("type")
    if expected_type and not _matches_type(value, expected_type):
        reasons.append(f"turn[{index}]:tool_argument_type_invalid{path}")
        return
    if "enum" in schema and not any(_json_equal(value, candidate) for candidate in schema["enum"]):
        reasons.append(f"turn[{index}]:tool_argument_enum_invalid{path}")
    if isinstance(value, Mapping):
        required = schema.get("required", [])
        for field in required:
            if field not in value:
                reasons.append(f"turn[{index}]:tool_required_argument_missing{path}")
        properties = schema.get("properties", {})
        if schema.get("additionalProperties") is False:
            for field in value:
                if field not in properties:
                    reasons.append(f"turn[{index}]:tool_argument_unknown{path}")
        for field, child in properties.items():
            if field in value:
                _schema_argument_errors(value[field], child, index, reasons, f"{path}.{field}")
    if isinstance(value, list):
        if "minItems" in schema and len(value) < schema["minItems"]:
            reasons.append(f"turn[{index}]:tool_argument_length_invalid{path}")
        if "maxItems" in schema and len(value) > schema["maxItems"]:
            reasons.append(f"turn[{index}]:tool_argument_length_invalid{path}")
        if "items" in schema:
            for item in value:
                _schema_argument_errors(item, schema["items"], index, reasons, f"{path}[]")
    if isinstance(value, str):
        if "minLength" in schema and len(value) < schema["minLength"]:
            reasons.append(f"turn[{index}]:tool_argument_length_invalid{path}")
        if "maxLength" in schema and len(value) > schema["maxLength"]:
            reasons.append(f"turn[{index}]:tool_argument_length_invalid{path}")


def _normalize_tool(tool: Any) -> dict[str, Any]:
    try:
        tool = _safe_json_normalize(tool)
    except ValueError as exc:
        raise ValueError("tool is not a finite JSON object") from exc
    if not isinstance(tool, Mapping):
        raise ValueError("tool must be an object")
    if set(tool) - {"name", "description", "parameters"}:
        raise ValueError("tool has unsupported fields")
    name = tool.get("name")
    if not isinstance(name, str) or not name:
        raise ValueError("tool.name must be a non-empty string")
    description = tool.get("description", "")
    if not isinstance(description, str):
        raise ValueError("tool.description must be text")
    parameters = tool.get("parameters")
    _validate_argument_schema(parameters)
    return {"name": name, "description": description, "parameters": parameters}


def _validate_argument_schema(schema: Any) -> None:
    if not isinstance(schema, Mapping) or schema.get("type") != "object":
        raise ValueError("tool.parameters must be an object schema")
    _validate_schema_node(schema, root=True)


def _validate_schema_node(schema: Any, *, root: bool = False) -> None:
    if not isinstance(schema, Mapping):
        raise ValueError("tool schema node must be an object")
    unsupported = set(schema) - _ARGUMENT_SCHEMA_KEYS
    if unsupported:
        raise ValueError("tool.parameters has unsupported keywords")
    schema_type = schema.get("type")
    if not isinstance(schema_type, str) or schema_type not in _JSON_TYPES:
        raise ValueError("tool parameter type is invalid")
    if root and schema_type != "object":
        raise ValueError("tool.parameters must be an object schema")
    if "enum" in schema:
        if not isinstance(schema["enum"], list):
            raise ValueError("tool parameter enum must be a list")
        for candidate in schema["enum"]:
            _validate_json_value(candidate)
    for field in ("minItems", "maxItems", "minLength", "maxLength"):
        if field in schema and (type(schema[field]) is not int or schema[field] < 0):
            raise ValueError(f"tool parameter {field} must be a nonnegative integer")
    if "minItems" in schema and "maxItems" in schema and schema["minItems"] > schema["maxItems"]:
        raise ValueError("tool parameter item bounds are inverted")
    if "minLength" in schema and "maxLength" in schema and schema["minLength"] > schema["maxLength"]:
        raise ValueError("tool parameter length bounds are inverted")
    required = schema.get("required", [])
    if not isinstance(required, list) or any(not isinstance(item, str) or not item for item in required) or len(required) != len(set(required)):
        raise ValueError("tool.parameters.required must be unique strings")
    properties = schema.get("properties", {})
    if not isinstance(properties, Mapping):
        raise ValueError("tool.parameters.properties must be an object")
    if any(not isinstance(name, str) or not isinstance(child, Mapping) for name, child in properties.items()):
        raise ValueError("tool parameter properties are invalid")
    if any(item not in properties for item in required):
        raise ValueError("required tool parameter is not defined")
    if properties and schema_type != "object":
        raise ValueError("properties require an object parameter")
    if required and schema_type != "object":
        raise ValueError("required requires an object parameter")
    if "additionalProperties" in schema and type(schema["additionalProperties"]) is not bool:
        raise ValueError("tool.parameters.additionalProperties must be boolean")
    if "additionalProperties" in schema and schema_type != "object":
        raise ValueError("additionalProperties requires an object parameter")
    if "items" in schema:
        if schema_type != "array":
            raise ValueError("items requires an array parameter")
        _validate_schema_node(schema["items"])
    if properties:
        for child in properties.values():
            _validate_schema_node(child)
    if any(field in schema for field in ("minItems", "maxItems")) and schema_type != "array":
        raise ValueError("item bounds require an array parameter")
    if any(field in schema for field in ("minLength", "maxLength")) and schema_type != "string":
        raise ValueError("length bounds require a string parameter")


def _validate_json_value(value: Any) -> None:
    """Reject non-JSON, non-finite, cyclic or non-UTF-8 values."""
    _safe_json_normalize(value)


def _matches_type(value: Any, expected: str) -> bool:
    if expected == "null":
        return value is None
    if expected == "boolean":
        return type(value) is bool
    if expected == "integer":
        return type(value) is int
    if expected == "number":
        return (type(value) is int or type(value) is float) and not isinstance(value, bool) and (type(value) is int or math.isfinite(value))
    if expected == "string":
        return isinstance(value, str)
    if expected == "object":
        return isinstance(value, Mapping)
    if expected == "array":
        return isinstance(value, list)
    return False


def _json_equal(left: Any, right: Any) -> bool:
    if type(left) is bool or type(right) is bool:
        return type(left) is type(right) and left == right
    if (type(left) is int or type(left) is float) and (type(right) is int or type(right) is float):
        return (type(left) is int or math.isfinite(left)) and (type(right) is int or math.isfinite(right)) and left == right
    if isinstance(left, Mapping) or isinstance(right, Mapping):
        if not isinstance(left, Mapping) or not isinstance(right, Mapping) or set(left) != set(right):
            return False
        return all(_json_equal(left[key], right[key]) for key in left)
    if isinstance(left, list) or isinstance(right, list):
        return isinstance(left, list) and isinstance(right, list) and len(left) == len(right) and all(
            _json_equal(a, b) for a, b in zip(left, right)
        )
    return type(left) is type(right) and left == right


def _reject_constant(value: str) -> None:
    raise ValueError(f"non-standard JSON constant: {value}")


def _parse_float(value: str) -> float:
    parsed = float(value)
    if not math.isfinite(parsed):
        raise ValueError(f"non-finite JSON number: {value}")
    return parsed


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _canonical_equal(left: Any, right: Any) -> bool:
    try:
        return canonical_json(left) == canonical_json(right)
    except (TypeError, ValueError):
        return False


def _sha256_text(value: str) -> str:
    return _sha256(value.encode("utf-8"))
