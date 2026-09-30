"""Immutable, hash-addressed campaign manifest builder.

The manifest describes a planned or completed run. Building or writing one is
offline bookkeeping; it does not call a model, server, network, or GPU.
"""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from pathlib import Path
from typing import Any, Mapping


SCHEMA_VERSION = "run-manifest-v1"
_CACHE_STATES = {"cold", "warm_uncached", "warm_cached", "unknown"}
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


def sha256_file(path: str | Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def sha256_json(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def new_manifest(
    *,
    campaign_id: str | None = None,
    run_id: str | None = None,
    model: str,
    code_sha256: str,
    prompt_sha256: str,
    goldset_sha256: str,
    payload_sha256: str,
    options: Mapping[str, Any],
    cache_state: str,
) -> dict[str, Any]:
    """Build a complete manifest with explicit code/input/options hashes."""
    campaign = campaign_id or f"campaign-{uuid.uuid4().hex}"
    run = run_id or f"run-{uuid.uuid4().hex}"
    _validate_id("campaign_id", campaign)
    _validate_id("run_id", run)
    if campaign == run:
        raise ValueError("campaign_id and run_id must be distinct")
    if not isinstance(model, str) or not model:
        raise ValueError("model must be a non-empty string")
    for name, value in {
        "code_sha256": code_sha256,
        "prompt_sha256": prompt_sha256,
        "goldset_sha256": goldset_sha256,
        "payload_sha256": payload_sha256,
    }.items():
        _validate_hash(name, value)
    if not isinstance(options, Mapping):
        raise ValueError("options must be an object")
    if not isinstance(cache_state, str) or cache_state not in _CACHE_STATES:
        raise ValueError("cache_state must be cold, warm_uncached, warm_cached, or unknown")
    return {
        "schema_version": SCHEMA_VERSION,
        "campaign_id": campaign,
        "run_id": run,
        "model": model,
        "code_sha256": code_sha256,
        "prompt_sha256": prompt_sha256,
        "goldset_sha256": goldset_sha256,
        "payload_sha256": payload_sha256,
        "options_sha256": sha256_json(options),
        "cache_state": cache_state,
    }


def validate_manifest(value: Mapping[str, Any]) -> list[str]:
    """Return contract errors without accepting inferred or missing hashes."""
    errors: list[str] = []
    if not isinstance(value, Mapping):
        return ["manifest must be an object"]
    if value.get("schema_version") != SCHEMA_VERSION:
        errors.append("schema_version must be run-manifest-v1")
    campaign, run = value.get("campaign_id"), value.get("run_id")
    if not isinstance(campaign, str) or not _ID.fullmatch(campaign):
        errors.append("campaign_id is invalid")
    if not isinstance(run, str) or not _ID.fullmatch(run):
        errors.append("run_id is invalid")
    if campaign == run:
        errors.append("campaign_id and run_id must be distinct")
    if not isinstance(value.get("model"), str) or not value["model"]:
        errors.append("model must be a non-empty string")
    for name in ("code_sha256", "prompt_sha256", "goldset_sha256", "payload_sha256", "options_sha256"):
        item = value.get(name)
        if not isinstance(item, str) or not _SHA256.fullmatch(item):
            errors.append(f"{name} must be a lowercase SHA-256 string")
    if not isinstance(value.get("cache_state"), str) or value["cache_state"] not in _CACHE_STATES:
        errors.append("cache_state is invalid")
    return errors


def write_manifest(path: str | Path, manifest: Mapping[str, Any]) -> Path:
    """Write once using exclusive creation; never overwrite an existing run."""
    errors = validate_manifest(manifest)
    if errors:
        raise ValueError("invalid manifest: " + "; ".join(errors))
    target = Path(path)
    if not target.parent.is_dir():
        raise ValueError("manifest parent directory must already exist")
    encoded = json.dumps(manifest, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n"
    with target.open("x", encoding="utf-8") as handle:
        handle.write(encoded)
    return target


def _validate_hash(name: str, value: Any) -> None:
    if not isinstance(value, str) or not _SHA256.fullmatch(value):
        raise ValueError(f"{name} must be a lowercase SHA-256 string")


def _validate_id(name: str, value: Any) -> None:
    if not isinstance(value, str) or not _ID.fullmatch(value):
        raise ValueError(f"{name} is invalid")
