"""Offline lifecycle packet and restoration evidence contract.

This module describes what a future, explicitly approved live campaign must
observe.  It never starts or stops a process, probes an endpoint, or reads the
machine.  A packet is therefore a reviewable runbook, not an execution plan
that can accidentally affect production.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from typing import Any

from tools.json_safety import normalize_json


SCHEMA_VERSION = "lifecycle-evidence-v1"
PACKET_SCHEMA_VERSION = "lifecycle-packet-v1"
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_ROLES = {"production", "auxiliary"}
_HEALTH_STATES = {"healthy", "unhealthy", "unknown"}
_PACKET_ACTIONS = {
    "observe_initial",
    "start_auxiliary_after_approval",
    "health_check",
    "run_one_bounded_request",
    "stop_owned_process_tree",
    "verify_restoration",
}

__all__ = [
    "PACKET_SCHEMA_VERSION",
    "SCHEMA_VERSION",
    "build_lifecycle_packet",
    "detect_orphans",
    "evaluate_restoration",
    "validate_lifecycle_evidence",
    "validate_lifecycle_packet",
]


def build_lifecycle_packet(
    *,
    campaign_id: str,
    production_endpoint: str,
    auxiliary_endpoint: str,
    timeout_s: int = 300,
) -> dict[str, Any]:
    """Build a deterministic, non-executable lifecycle runbook.

    Endpoint strings identify what a future operator must verify; they are not
    contacted here.  The packet deliberately contains no shell command,
    process-control primitive, or default endpoint.
    """
    _validate_id("campaign_id", campaign_id)
    _validate_endpoint("production_endpoint", production_endpoint)
    _validate_endpoint("auxiliary_endpoint", auxiliary_endpoint)
    if production_endpoint == auxiliary_endpoint:
        raise ValueError("production and auxiliary endpoints must differ")
    if type(timeout_s) is not int or timeout_s <= 0:
        raise ValueError("timeout_s must be a positive integer")
    packet = {
        "schema_version": PACKET_SCHEMA_VERSION,
        "campaign_id": campaign_id,
        "can_execute": False,
        "production_endpoint": production_endpoint,
        "auxiliary_endpoint": auxiliary_endpoint,
        "timeout_s": timeout_s,
        "steps": [
            {"id": 1, "action": "observe_initial"},
            {"id": 2, "action": "start_auxiliary_after_approval"},
            {"id": 3, "action": "health_check"},
            {"id": 4, "action": "run_one_bounded_request"},
            {"id": 5, "action": "stop_owned_process_tree"},
            {"id": 6, "action": "verify_restoration"},
        ],
        "stop_conditions": [
            "identity_mismatch",
            "unknown_residency",
            "unexpected_eviction",
            "spill_detected",
            "endpoint_unhealthy",
            "request_failure",
            "restoration_unverified",
        ],
        "restoration_requirements": [
            "auxiliary_process_tree_absent",
            "initial_process_identities_match",
            "initial_endpoint_healthy",
            "initial_residency_state_verified",
        ],
    }
    errors = validate_lifecycle_packet(packet)
    if errors:
        raise ValueError("invalid lifecycle packet: " + "; ".join(errors))
    return packet


def validate_lifecycle_packet(value: Mapping[str, Any]) -> list[str]:
    """Return deterministic contract errors for a non-executable packet."""
    try:
        value = normalize_json(value)
    except ValueError:
        return ["packet_not_json"]
    if not isinstance(value, Mapping):
        return ["packet_not_object"]
    if value.get("schema_version") != PACKET_SCHEMA_VERSION:
        return ["packet_schema_version"]
    if value.get("can_execute") is not False:
        return ["packet_must_be_non_executable"]
    if not isinstance(value.get("campaign_id"), str) or not value["campaign_id"]:
        return ["campaign_id_invalid"]
    for field in ("production_endpoint", "auxiliary_endpoint"):
        if not isinstance(value.get(field), str) or not value[field].strip():
            return [f"{field}_invalid"]
    if value.get("production_endpoint") == value.get("auxiliary_endpoint"):
        return ["endpoints_must_differ"]
    if type(value.get("timeout_s")) is not int or value["timeout_s"] <= 0:
        return ["timeout_invalid"]
    steps = value.get("steps")
    if not isinstance(steps, list) or not steps:
        return ["steps_invalid"]
    expected_ids = list(range(1, len(steps) + 1))
    ids = [item.get("id") if isinstance(item, Mapping) else None for item in steps]
    actions = [item.get("action") if isinstance(item, Mapping) else None for item in steps]
    if ids != expected_ids or any(action not in _PACKET_ACTIONS for action in actions):
        return ["steps_invalid"]
    if not isinstance(value.get("stop_conditions"), list) or not value["stop_conditions"]:
        return ["stop_conditions_invalid"]
    if not isinstance(value.get("restoration_requirements"), list) or not value["restoration_requirements"]:
        return ["restoration_requirements_invalid"]
    return []


def validate_lifecycle_evidence(value: Mapping[str, Any]) -> list[str]:
    """Validate observed process/endpoint evidence without probing anything."""
    try:
        value = normalize_json(value)
    except ValueError:
        return ["evidence_not_json"]
    if not isinstance(value, Mapping):
        return ["evidence_not_object"]
    if value.get("schema_version") != SCHEMA_VERSION:
        return ["evidence_schema_version"]
    for phase in ("initial", "auxiliary", "final"):
        if phase not in value:
            return [f"{phase}_missing"]
        phase_value = value[phase]
        if not isinstance(phase_value, Mapping):
            return [f"{phase}_not_object"]
        errors = _validate_phase(phase, phase_value)
        if errors:
            return errors
    return []


def detect_orphans(
    initial_processes: Iterable[Mapping[str, Any]],
    final_processes: Iterable[Mapping[str, Any]],
    auxiliary_processes: Iterable[Mapping[str, Any]],
) -> list[int]:
    """Return final PIDs not present initially, including surviving auxiliaries.

    Inputs are already captured evidence.  The function does not inspect PIDs
    or send signals.  A malformed process record raises ``ValueError`` so a
    caller cannot interpret incomplete evidence as a clean restoration.
    """
    initial = _process_identity_map(initial_processes, "initial_processes")
    final = _process_identity_map(final_processes, "final_processes")
    auxiliary = _process_identity_map(auxiliary_processes, "auxiliary_processes")
    # A process not present initially is an orphan; an auxiliary PID that is
    # still present is also an orphan even if a caller accidentally reused a
    # PID set in its initial list.
    return sorted((set(final) - set(initial)) | (set(final) & set(auxiliary)))


def evaluate_restoration(value: Mapping[str, Any]) -> dict[str, Any]:
    """Classify restoration as restored, failed, or unknown from captured data."""
    errors = validate_lifecycle_evidence(value)
    if errors:
        return {"status": "invalid", "reasons": errors}
    initial = value["initial"]
    auxiliary = value["auxiliary"]
    final = value["final"]
    orphan_pids = detect_orphans(
        initial["processes"], final["processes"], auxiliary["processes"]
    )
    if orphan_pids:
        return {"status": "failed", "reasons": ["orphan_processes"], "orphan_pids": orphan_pids}
    if initial["endpoint_health"] != "healthy" or final["endpoint_health"] != "healthy":
        return {"status": "failed", "reasons": ["endpoint_unhealthy"]}
    if set(
        item["pid"] for item in auxiliary["processes"]
    ) & set(item["pid"] for item in final["processes"]):
        return {"status": "failed", "reasons": ["auxiliary_processes_remain"]}
    if _identity_fingerprint(initial["processes"]) != _identity_fingerprint(final["processes"]):
        return {"status": "failed", "reasons": ["initial_process_identities_mismatch"]}
    if initial["residency"] == "unknown" or final["residency"] == "unknown":
        return {"status": "unknown", "reasons": ["residency_unknown"]}
    if initial["residency"] != "healthy" or final["residency"] != "healthy":
        return {"status": "failed", "reasons": ["residency_not_restored"]}
    return {"status": "restored", "reasons": []}


def _validate_phase(phase: str, value: Mapping[str, Any]) -> list[str]:
    processes = value.get("processes")
    if not isinstance(processes, list):
        return [f"{phase}_processes_invalid"]
    try:
        _process_identity_map(processes, f"{phase}.processes")
    except ValueError:
        return [f"{phase}_process_identity_invalid"]
    if value.get("endpoint_health") not in _HEALTH_STATES:
        return [f"{phase}_endpoint_health_invalid"]
    if value.get("residency") not in _HEALTH_STATES:
        return [f"{phase}_residency_invalid"]
    return []


def _process_identity_map(
    processes: Iterable[Mapping[str, Any]], name: str
) -> dict[int, tuple[str, str, str]]:
    result: dict[int, tuple[str, str, str]] = {}
    for item in processes:
        if not isinstance(item, Mapping):
            raise ValueError(f"{name} contains a non-object")
        pid = item.get("pid")
        if type(pid) is not int or pid <= 0:
            raise ValueError(f"{name} contains an invalid pid")
        start_time = item.get("start_time")
        executable = item.get("executable")
        executable_sha256 = item.get("executable_sha256")
        if not isinstance(start_time, str) or not start_time:
            raise ValueError(f"{name} contains an invalid start_time")
        if not isinstance(executable, str) or not executable:
            raise ValueError(f"{name} contains an invalid executable")
        if not isinstance(executable_sha256, str) or not _SHA256.fullmatch(executable_sha256):
            raise ValueError(f"{name} contains an invalid executable_sha256")
        if pid in result:
            raise ValueError(f"{name} contains duplicate pid")
        result[pid] = (start_time, executable, executable_sha256)
    return result


def _identity_fingerprint(processes: Iterable[Mapping[str, Any]]) -> tuple[tuple[Any, ...], ...]:
    identities = _process_identity_map(processes, "processes")
    return tuple(sorted((pid, *identity) for pid, identity in identities.items()))


def _validate_id(name: str, value: Any) -> None:
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", value):
        raise ValueError(f"{name} is invalid")


def _validate_endpoint(name: str, value: Any) -> None:
    if not isinstance(value, str) or not value.strip() or "\n" in value or "\r" in value:
        raise ValueError(f"{name} is invalid")
