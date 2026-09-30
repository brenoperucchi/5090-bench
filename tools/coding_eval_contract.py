"""Offline contract for a future sandboxed coding evaluation.

The module validates task definitions, creates a non-executable evaluation
packet, and validates result evidence supplied by a future runner.  It never
executes model-produced code, applies patches, starts a subprocess, opens a
network connection, or writes a workspace.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from typing import Any

from tools.json_safety import normalize_json


TASK_SCHEMA_VERSION = "coding-task-v1"
PACKET_SCHEMA_VERSION = "coding-eval-packet-v1"
RESULT_SCHEMA_VERSION = "coding-result-v1"
_TASK_ID = re.compile(r"^[a-z0-9][a-z0-9_-]{1,63}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_FAMILIES = {"functional", "api_hallucination", "instruction_adherence", "tool_flow"}
_MODES = {"stdout", "patch", "tool_trace", "forbidden_pattern"}
_TASK_FIELDS = {"task_id", "family", "language", "prompt", "expected", "sandbox"}
_EXPECTED_FIELDS = {"mode", "value"}
_SANDBOX_FIELDS = {"network", "filesystem", "timeout_s", "memory_limit_mb"}
_RESULT_FIELDS = {
    "schema_version",
    "task_id",
    "status",
    "candidate_sha256",
    "stdout_sha256",
    "stderr_sha256",
    "exit_code",
    "duration_ms",
    "sandbox_proof",
}
_PROOF_FIELDS = {"network_blocked", "filesystem_ephemeral", "timeout_enforced", "memory_enforced"}
_RESULT_STATUSES = {"pass", "fail", "error", "inconclusive"}

__all__ = [
    "PACKET_SCHEMA_VERSION",
    "RESULT_SCHEMA_VERSION",
    "TASK_SCHEMA_VERSION",
    "build_coding_packet",
    "classify_coding_result",
    "validate_coding_packet",
    "validate_coding_result",
    "validate_coding_task",
]


def validate_coding_task(value: Mapping[str, Any]) -> list[str]:
    """Return stable errors for one task definition."""
    try:
        value = normalize_json(value)
    except ValueError:
        return ["coding_task_not_json"]
    if not isinstance(value, Mapping):
        return ["coding_task_not_object"]
    if set(value) - _TASK_FIELDS:
        return ["coding_task_unknown_field"]
    task_id = value.get("task_id")
    if not isinstance(task_id, str) or not _TASK_ID.fullmatch(task_id):
        return ["task_id_invalid"]
    if value.get("family") not in _FAMILIES:
        return ["task_family_invalid"]
    for field in ("language", "prompt"):
        if not isinstance(value.get(field), str) or not value[field].strip():
            return [f"task_{field}_invalid"]
    expected = value.get("expected")
    if not isinstance(expected, Mapping):
        return ["task_expected_invalid"]
    if set(expected) - _EXPECTED_FIELDS or "mode" not in expected or "value" not in expected:
        return ["task_expected_invalid"]
    if expected.get("mode") not in _MODES:
        return ["task_expected_mode_invalid"]
    sandbox = value.get("sandbox")
    if not isinstance(sandbox, Mapping) or set(sandbox) - _SANDBOX_FIELDS:
        return ["task_sandbox_invalid"]
    if sandbox.get("network") is not False:
        return ["sandbox_network_must_be_disabled"]
    if sandbox.get("filesystem") != "ephemeral":
        return ["sandbox_filesystem_must_be_ephemeral"]
    if type(sandbox.get("timeout_s")) is not int or sandbox["timeout_s"] <= 0:
        return ["sandbox_timeout_invalid"]
    if type(sandbox.get("memory_limit_mb")) is not int or sandbox["memory_limit_mb"] <= 0:
        return ["sandbox_memory_limit_invalid"]
    return []


def build_coding_packet(*, suite_id: str, tasks: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    """Build a deterministic, non-executable coding-evaluation packet."""
    if not isinstance(suite_id, str) or not _TASK_ID.fullmatch(suite_id):
        raise ValueError("suite_id is invalid")
    normalized_tasks: list[dict[str, Any]] = []
    seen: set[str] = set()
    for task in tasks:
        try:
            normalized = normalize_json(task)
        except ValueError as exc:
            raise ValueError("coding_task_not_json") from exc
        errors = validate_coding_task(normalized)
        if errors:
            raise ValueError(errors[0])
        task_id = normalized["task_id"]
        if task_id in seen:
            raise ValueError("duplicate_task_id")
        seen.add(task_id)
        normalized_tasks.append(normalized)
    if not normalized_tasks:
        raise ValueError("tasks_must_not_be_empty")
    packet = {
        "schema_version": PACKET_SCHEMA_VERSION,
        "suite_id": suite_id,
        "can_execute": False,
        "tasks": normalized_tasks,
        "runner_requirements": [
            "network_disabled",
            "ephemeral_filesystem",
            "bounded_timeout",
            "bounded_memory",
            "discard_workspace_after_task",
        ],
        "stop_conditions": [
            "sandbox_proof_missing",
            "network_not_blocked",
            "filesystem_not_ephemeral",
            "timeout_not_enforced",
            "memory_not_enforced",
            "runner_identity_unknown",
        ],
    }
    errors = validate_coding_packet(packet)
    if errors:
        raise ValueError("invalid coding packet: " + "; ".join(errors))
    return packet


def validate_coding_packet(value: Mapping[str, Any]) -> list[str]:
    """Return stable errors for a non-executable packet."""
    try:
        value = normalize_json(value)
    except ValueError:
        return ["coding_packet_not_json"]
    if not isinstance(value, Mapping):
        return ["coding_packet_not_object"]
    if value.get("schema_version") != PACKET_SCHEMA_VERSION:
        return ["coding_packet_schema_version"]
    if value.get("can_execute") is not False:
        return ["coding_packet_must_be_non_executable"]
    if not isinstance(value.get("suite_id"), str) or not _TASK_ID.fullmatch(value["suite_id"]):
        return ["suite_id_invalid"]
    tasks = value.get("tasks")
    if not isinstance(tasks, list) or not tasks:
        return ["tasks_invalid"]
    seen: set[str] = set()
    for task in tasks:
        errors = validate_coding_task(task)
        if errors:
            return errors
        if task["task_id"] in seen:
            return ["duplicate_task_id"]
        seen.add(task["task_id"])
    if not isinstance(value.get("runner_requirements"), list) or not value["runner_requirements"]:
        return ["runner_requirements_invalid"]
    if not isinstance(value.get("stop_conditions"), list) or not value["stop_conditions"]:
        return ["stop_conditions_invalid"]
    return []


def validate_coding_result(value: Mapping[str, Any]) -> list[str]:
    """Return stable errors for result evidence from a future sandbox."""
    try:
        value = normalize_json(value)
    except ValueError:
        return ["coding_result_not_json"]
    if not isinstance(value, Mapping):
        return ["coding_result_not_object"]
    if set(value) - _RESULT_FIELDS:
        return ["coding_result_unknown_field"]
    if value.get("schema_version") != RESULT_SCHEMA_VERSION:
        return ["coding_result_schema_version"]
    if not isinstance(value.get("task_id"), str) or not _TASK_ID.fullmatch(value["task_id"]):
        return ["task_id_invalid"]
    if value.get("status") not in _RESULT_STATUSES:
        return ["result_status_invalid"]
    for field in ("candidate_sha256", "stdout_sha256", "stderr_sha256"):
        item = value.get(field)
        if item is not None and (not isinstance(item, str) or not _SHA256.fullmatch(item)):
            return [f"{field}_invalid"]
    if not isinstance(value.get("candidate_sha256"), str) or not _SHA256.fullmatch(value["candidate_sha256"]):
        return ["candidate_sha256_invalid"]
    for field in ("exit_code", "duration_ms"):
        item = value.get(field)
        if item is not None and (type(item) is not int or item < 0):
            return [f"{field}_invalid"]
    proof = value.get("sandbox_proof")
    if not isinstance(proof, Mapping) or set(proof) != _PROOF_FIELDS:
        return ["sandbox_proof_invalid"]
    if any(type(proof[field]) is not bool for field in _PROOF_FIELDS):
        return ["sandbox_proof_invalid"]
    return []


def classify_coding_result(value: Mapping[str, Any]) -> dict[str, Any]:
    """Classify result evidence without executing or trusting candidate code."""
    errors = validate_coding_result(value)
    if errors:
        return {"status": "invalid", "reasons": errors}
    proof = value["sandbox_proof"]
    if proof["network_blocked"] is not True:
        return {"status": "sandbox_failed", "reasons": ["network_not_blocked"]}
    if proof["filesystem_ephemeral"] is not True:
        return {"status": "sandbox_failed", "reasons": ["filesystem_not_ephemeral"]}
    if proof["timeout_enforced"] is not True:
        return {"status": "sandbox_unproven", "reasons": ["timeout_not_enforced"]}
    if proof["memory_enforced"] is not True:
        return {"status": "sandbox_unproven", "reasons": ["memory_not_enforced"]}
    if value["status"] in {"error", "inconclusive"}:
        return {"status": "inconclusive", "reasons": [value["status"]]}
    return {"status": "usable", "reasons": []}
