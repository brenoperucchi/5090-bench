"""Small, fail-closed JSON value normalizer shared by offline validators.

The normalizer deliberately accepts only the finite JSON value domain.  It
returns a fresh tree, converts ordinary mapping subclasses to dictionaries,
rejects active-path cycles and isolated UTF-16 surrogates, and caps nesting so
later recursive consumers cannot escape their public error boundary.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Any


MAX_JSON_DEPTH = 256


def normalize_json(value: Any, *, max_depth: int = MAX_JSON_DEPTH) -> Any:
    """Return an independent JSON-compatible copy or raise ``ValueError``.

    ``max_depth`` counts nested mapping/list containers.  Acyclic subtrees may
    be shared by the caller; each occurrence is copied independently and only
    active-path re-entry is treated as a cycle.
    """
    if type(max_depth) is not int or max_depth < 0:
        raise ValueError("max_depth must be a nonnegative integer")
    try:
        return _normalize(value, set(), 0, max_depth)
    except (TypeError, ValueError, UnicodeError, OverflowError, RecursionError) as exc:
        raise ValueError("value is not a finite JSON structure") from exc


def _normalize(value: Any, stack: set[int], depth: int, max_depth: int) -> Any:
    if value is None or type(value) is bool:
        return value
    if isinstance(value, str):
        # Python strings can contain isolated surrogates.  They are not valid
        # UTF-8 and must not cross an artifact boundary.
        value.encode("utf-8")
        return str(value)
    if type(value) is int:
        # Python may reject conversion of huge integers when serializing them.
        str(value)
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("non-finite JSON number")
        return float(value)
    if isinstance(value, Mapping):
        if depth >= max_depth:
            raise ValueError("JSON structure exceeds maximum depth")
        marker = id(value)
        if marker in stack:
            raise ValueError("cyclic JSON mapping")
        stack.add(marker)
        try:
            normalized: dict[str, Any] = {}
            for key, item in value.items():
                if not isinstance(key, str):
                    raise ValueError("JSON object keys must be strings")
                key.encode("utf-8")
                if key in normalized:
                    raise ValueError("duplicate JSON object key")
                normalized[str(key)] = _normalize(item, stack, depth + 1, max_depth)
            return normalized
        finally:
            stack.remove(marker)
    if isinstance(value, list):
        if depth >= max_depth:
            raise ValueError("JSON structure exceeds maximum depth")
        marker = id(value)
        if marker in stack:
            raise ValueError("cyclic JSON list")
        stack.add(marker)
        try:
            return [_normalize(item, stack, depth + 1, max_depth) for item in value]
        finally:
            stack.remove(marker)
    raise ValueError(f"unsupported JSON value: {type(value).__name__}")

