"""Offline validator for target/draft residency and spill evidence.

The classifier is deliberately evidence driven.  It never queries GPU memory,
``/api/ps`` or a runner log; callers provide captured observations.  Missing or
unattributed residency is ``residency_unknown`` and can never be promoted to
``verified_no_spill`` from global memory numbers alone.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from tools.json_safety import normalize_json


SCHEMA_VERSION = "spill-evidence-v1"
ROLES = ("target", "draft")
_KV_LOCATIONS = {"gpu", "cpu", "mixed", "unknown"}
_ROLE_FIELDS = {
    "model",
    "layers_expected",
    "layers_on_gpu",
    "kv_location",
    "attributed_memory_bytes",
    "sources",
}
_SOURCE_NAMES = {"startup_log", "runner_log", "api_ps", "gpu_sample"}

__all__ = ["SCHEMA_VERSION", "classify_spill_evidence", "validate_spill_evidence"]


def validate_spill_evidence(
    value: Mapping[str, Any], *, required_roles: Iterable[str] = ("target",)
) -> list[str]:
    """Return stable schema errors for captured residency observations."""
    try:
        value = normalize_json(value)
    except ValueError:
        return ["spill_evidence_not_json"]
    if not isinstance(value, Mapping):
        return ["spill_evidence_not_object"]
    if value.get("schema_version") != SCHEMA_VERSION:
        return ["spill_evidence_schema_version"]
    roles = tuple(required_roles)
    if not roles or any(role not in ROLES for role in roles):
        return ["required_roles_invalid"]
    observations = value.get("roles")
    if not isinstance(observations, Mapping):
        return ["roles_invalid"]
    if any(role not in ROLES for role in observations):
        return ["unknown_role"]
    for role in roles:
        if role not in observations:
            return [f"{role}_missing"]
        errors = _validate_role(role, observations[role])
        if errors:
            return errors
    global_memory = value.get("global_memory")
    if global_memory is not None:
        if not isinstance(global_memory, Mapping):
            return ["global_memory_invalid"]
        for name in ("used_bytes", "free_bytes"):
            item = global_memory.get(name)
            if type(item) is not int or item < 0:
                return [f"global_memory_{name}_invalid"]
    return []


def classify_spill_evidence(
    value: Mapping[str, Any], *, required_roles: Iterable[str] = ("target",)
) -> dict[str, Any]:
    """Classify evidence as verified, spill, unknown, or invalid.

    A role is clean only when all expected layers are on GPU, KV is on GPU,
    attributed memory is present, and at least one startup/runner source
    identifies the observation.  ``api_ps`` or global memory by themselves do
    not prove residency.
    """
    required = tuple(required_roles)
    errors = validate_spill_evidence(value, required_roles=required)
    if errors:
        return {"status": "invalid", "reasons": errors}
    observations = value["roles"]
    unknown: list[str] = []
    spill: list[str] = []
    for role in required:
        item = observations[role]
        if item["layers_on_gpu"] < item["layers_expected"]:
            spill.append(f"{role}_layers_offloaded")
        if item["kv_location"] in {"cpu", "mixed"}:
            spill.append(f"{role}_kv_offloaded")
        if item["kv_location"] == "unknown":
            unknown.append(f"{role}_kv_unknown")
        if item["attributed_memory_bytes"] is None:
            unknown.append(f"{role}_attributed_memory_unknown")
        sources = set(item["sources"])
        if not sources & {"startup_log", "runner_log"}:
            unknown.append(f"{role}_residency_source_unknown")
    if spill:
        return {"status": "spill_detected", "reasons": spill}
    if unknown:
        return {"status": "residency_unknown", "reasons": unknown}
    return {"status": "verified_no_spill", "reasons": []}


def _validate_role(role: str, value: Any) -> list[str]:
    if not isinstance(value, Mapping):
        return [f"{role}_invalid"]
    if set(value) - _ROLE_FIELDS:
        return [f"{role}_unknown_field"]
    model = value.get("model")
    if not isinstance(model, str) or not model:
        return [f"{role}_model_invalid"]
    expected = value.get("layers_expected")
    on_gpu = value.get("layers_on_gpu")
    if type(expected) is not int or expected <= 0:
        return [f"{role}_layers_expected_invalid"]
    if type(on_gpu) is not int or on_gpu < 0 or on_gpu > expected:
        return [f"{role}_layers_on_gpu_invalid"]
    if value.get("kv_location") not in _KV_LOCATIONS:
        return [f"{role}_kv_location_invalid"]
    attributed = value.get("attributed_memory_bytes")
    if attributed is not None and (type(attributed) is not int or attributed < 0):
        return [f"{role}_attributed_memory_invalid"]
    sources = value.get("sources")
    if not isinstance(sources, list) or not sources or any(
        not isinstance(source, str) or source not in _SOURCE_NAMES for source in sources
    ):
        return [f"{role}_sources_invalid"]
    return []
