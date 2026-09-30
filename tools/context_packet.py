"""Offline builder for the preregistered NUM_PARALLEL diagnostic packet.

The packet is a deterministic description of two requests and their validity
checks. It has no transport or process-control code and cannot execute the
diagnostic itself.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from typing import Any


CONTEXT = 32_768
KEEP = 4
TARGET_EFFECTIVE_INPUT = 40_000
SENTINEL_PREFIX = "CTX_SENTINEL_"
WIRE_FIELDS = ("model", "messages", "stream", "think", "options")
VALIDITY_CHECKS = (
    "endpoint_identity",
    "process_settings",
    "model_digest",
    "gpu_residency_before",
    "gpu_residency_after",
    "spill_absent",
    "server_tokenization_observed",
    "restoration_verified",
)


def predicted_limits(*, parallel: int, context: int = CONTEXT, keep: int = KEEP) -> dict[str, int]:
    """Return both preregistered hypotheses; no runtime observation is implied."""
    if type(parallel) is not int or parallel not in (1, 2):
        raise ValueError("parallel must be 1 or 2")
    if type(context) is not int or context <= 0 or type(keep) is not int or keep < 0:
        raise ValueError("context must be a positive integer and keep a nonnegative integer")
    law_a = context // parallel
    law_b = context - max((context - keep) // 2, 1)
    return {"law_a_limit": law_a, "law_b_limit": law_b}


def sentinel_prompt(token_units: int = TARGET_EFFECTIVE_INPUT) -> str:
    """Create a deterministic sentinel prompt; effective server tokens remain unknown."""
    if type(token_units) is not int or token_units <= 0:
        raise ValueError("token_units must be a positive integer")
    return " ".join(f"{SENTINEL_PREFIX}{index:06d}" for index in range(token_units))


def build_arm(*, parallel: int, model: str = "qwen3:14b") -> dict[str, Any]:
    """Build one fixed request plus offline evidence requirements."""
    if not isinstance(model, str) or not model:
        raise ValueError("model must be a non-empty string")
    prompt = sentinel_prompt()
    payload: dict[str, Any] = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "stream": True,
        "think": False,
        "options": {
            "num_ctx": CONTEXT,
            "num_predict": 1,
            "num_keep": KEEP,
            "temperature": 0,
        },
    }
    first = f"{SENTINEL_PREFIX}000000"
    last = f"{SENTINEL_PREFIX}{TARGET_EFFECTIVE_INPUT - 1:06d}"
    payload["packet"] = {
        "process_num_parallel": parallel,
        "context": CONTEXT,
        "target_effective_input_tokens": TARGET_EFFECTIVE_INPUT,
        "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
        "serialized_request_sha256": serialized_request_sha256(payload),
        "effective_input_tokens": None,
        "sentinels": {"prefix": SENTINEL_PREFIX, "count": TARGET_EFFECTIVE_INPUT, "first": first, "last": last},
        "counters": {
            "server_prompt_eval_count": None,
            "server_eval_count": None,
            "effective_input_tokens": None,
            "delivered_input_tokens": None,
            "truncated": None,
        },
        "predictions": predicted_limits(parallel=parallel),
        "validity_checks": list(VALIDITY_CHECKS),
        "can_execute": False,
    }
    return payload


def wire_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Return only fields intended for the API body; packet metadata is local."""
    return {field: payload[field] for field in WIRE_FIELDS if field in payload}


def canonical_json(payload: Mapping[str, Any]) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def serialized_request_sha256(payload: Mapping[str, Any]) -> str:
    """Hash the canonical API body, excluding local packet metadata."""
    return hashlib.sha256(canonical_json(wire_payload(payload))).hexdigest()
