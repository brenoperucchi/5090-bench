#!/usr/bin/env python3
"""Audit historical guardian runs without issuing new model requests.

P0(c) is safe to answer offline: each historical record already stores content
and reasoning_content validation separately.  This tool intentionally emits
counts and request metadata only; it never copies prompts or model output.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


def read(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected object: {path}")
    return value


def nonempty(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--root", type=Path, default=Path("results"))
    args = parser.parse_args()

    groups: dict[tuple[str, str, str, str], Counter[str]] = defaultdict(Counter)
    total = Counter()
    files = 0
    for summary_path in sorted(args.root.glob("guardian-probe-*/**/summary.json")):
        summary = read(summary_path)
        model = str(summary.get("model", "unknown"))
        phase = str(summary.get("phase", "unknown"))
        constraint = str(summary.get("constraint_mode", "unknown"))
        template = json.dumps(summary.get("chat_template_kwargs"), sort_keys=True)
        key = (model, phase, constraint, template)
        for record in summary.get("records", []):
            files += 1
            content = record.get("content")
            reasoning = record.get("reasoning_content")
            metrics = groups[key]
            metrics["records"] += 1
            metrics["content_empty"] += int(not nonempty(content))
            metrics["reasoning_nonempty"] += int(nonempty(reasoning))
            metrics["content_empty_reasoning_nonempty"] += int(not nonempty(content) and nonempty(reasoning))
            metrics["content_schema_valid"] += int(record.get("content_schema_valid", record.get("schema_valid", False)))
            metrics["reasoning_schema_valid"] += int(record.get("reasoning_schema_valid", False))
            metrics["content_empty_reasoning_schema_valid"] += int(
                not nonempty(content) and record.get("reasoning_schema_valid", False)
            )
            metrics[f"finish_{record.get('finish_reason')}"] += 1
            total["records"] += 1
            total["content_empty"] += int(not nonempty(content))
            total["reasoning_nonempty"] += int(nonempty(reasoning))
            total["content_empty_reasoning_nonempty"] += int(not nonempty(content) and nonempty(reasoning))
            total["content_schema_valid"] += int(record.get("content_schema_valid", record.get("schema_valid", False)))
            total["reasoning_schema_valid"] += int(record.get("reasoning_schema_valid", False))
            total["content_empty_reasoning_schema_valid"] += int(
                not nonempty(content) and record.get("reasoning_schema_valid", False)
            )

    if not total:
        raise SystemExit("no historical guardian records found")

    def pct(n: int, d: int) -> float | None:
        return round(n / d, 6) if d else None

    runs = []
    for (model, phase, constraint, template), metrics in sorted(groups.items()):
        item = dict(metrics)
        item.update(
            {
                "model": model,
                "phase": phase,
                "constraint_mode": constraint,
                "chat_template_kwargs": json.loads(template),
                "content_empty_reasoning_fraction": pct(
                    metrics["content_empty_reasoning_nonempty"], metrics["records"]
                ),
                "reasoning_schema_valid_given_content_empty": pct(
                    metrics["content_empty_reasoning_schema_valid"], metrics["content_empty"]
                ),
            }
        )
        runs.append(item)

    output = {
        "schema": "guardian-p0-offline-audit-v1",
        "scope": {
            "fresh_requests": 0,
            "p0_a_reasoning_format_none": "not_run: remote runtime unavailable",
            "p0_b_chat_template_kwargs_live": "not_run: remote runtime unavailable",
            "p0_c_reasoning_channel_separate_column": "completed_from_historical_artifacts",
        },
        "environment_blocker": {
            "local_probe_endpoints": "no response",
            "remote_ssh": "connection timed out",
            "note": "No server was started, stopped, or reconfigured by this audit.",
        },
        "aggregate": {
            **total,
            "content_empty_reasoning_fraction": pct(total["content_empty_reasoning_nonempty"], total["records"]),
            "reasoning_schema_valid_given_content_empty": pct(
                total["content_empty_reasoning_schema_valid"], total["content_empty"]
            ),
        },
        "runs": runs,
        "interpretation": [
            "reasoning_schema_valid is diagnostic and does not replace content_schema_valid in historical scores",
            "P0(c) shows whether the separate validator column can recover structured data already present in reasoning_content",
            "P0(a/b) remain unanswered until an explicitly controlled runtime is reachable",
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output), "records": total["records"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
