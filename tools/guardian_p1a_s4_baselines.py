#!/usr/bin/env python3
"""Compute only the deterministic S4 baselines for guardian decision work.

This tool is deliberately unable to load or score the judgment residue.  It
uses the two immutable round manifests and their S4 sidecars, then rechecks
S4 from source metrics/filesystem.  The rubric has two deterministic forms:
an aborted dispatch (``dispatch == false`` plus ``reset_error``), or a
dispatched stalled slot with no artifact.  The output is a provenance
artifact, not a model evaluation.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


S4 = "stalled"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def slot_s4(mode: str, source: dict[str, Any], metrics: dict[str, Any]) -> bool:
    reviewers = metrics.get("reviewers")
    if not isinstance(reviewers, dict):
        return False
    artifact_name = "verdict.md" if mode == "review" else "answer.md"
    for reviewer, entry in reviewers.items():
        if not isinstance(entry, dict):
            continue
        if entry.get("dispatched") is not True or entry.get("status") != "stalled":
            continue
        artifact = Path(source["dir"]) / str(reviewer) / artifact_name
        if not artifact.is_file() or artifact.stat().st_size == 0:
            return True
    return False


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--llm-bench-root", required=True, type=Path)
    parser.add_argument("--claude-bridge-root", required=True, type=Path)
    args = parser.parse_args()

    # Both hash-addressed manifests are stored in claude-bridge's bench
    # directory; their ``dir`` fields point at the two source workspaces.
    bench_root = args.claude_bridge_root / ".herdr/bench"
    sources = [
        ("llm-bench", "llm-bench-rounds.json", "llm-bench-round-labels.json"),
        ("claude-bridge", "claude-bridge-rounds.json", "claude-bridge-round-labels.json"),
    ]
    rows: list[dict[str, Any]] = []
    input_hashes: dict[str, str] = {}

    for corpus, manifest_name, labels_name in sources:
        manifest_path = bench_root / manifest_name
        labels_path = bench_root / labels_name
        input_hashes[f"{corpus}.rounds"] = sha256(manifest_path)
        input_hashes[f"{corpus}.round_labels"] = sha256(labels_path)
        manifest = load(manifest_path)
        labels = load(labels_path)
        manifest_by_id = {item["id"]: item for item in manifest["rounds"]}

        for candidate in labels["candidates"]:
            round_id = candidate["round_id"]
            signals = candidate.get("signals") or []
            if "S4" not in signals:
                continue
            source = manifest_by_id[round_id]
            metrics_path = Path(source["dir"]) / "metrics.json"
            metrics = load(metrics_path)
            dispatch = metrics.get("dispatch")
            reset_error = metrics.get("reset_error")
            aborted_before_dispatch = (
                dispatch is False and isinstance(reset_error, str) and bool(reset_error.strip())
            )
            stalled_slot_without_artifact = slot_s4(source["mode"]["value"], source, metrics)
            regex_match = aborted_before_dispatch or stalled_slot_without_artifact
            rows.append(
                {
                    "corpus": corpus,
                    "round_id": round_id,
                    "mode": source["mode"]["value"],
                    "regime": source["regime"]["value"],
                    "target": S4,
                    "regex_s4_match": regex_match,
                    "s4_form": (
                        "aborted_before_dispatch"
                        if aborted_before_dispatch
                        else "stalled_slot_without_artifact"
                        if stalled_slot_without_artifact
                        else "unclassified"
                    ),
                }
            )

    rows.sort(key=lambda row: (row["corpus"], row["round_id"]))
    if not rows:
        raise SystemExit("no S4 rows found")

    target_counts = Counter(row["target"] for row in rows)
    majority = target_counts.most_common(1)[0][0]
    majority_correct = sum(row["target"] == majority for row in rows)

    by_regime: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_regime[row["regime"]].append(row)
    regime_table = []
    for regime in sorted(by_regime):
        group = by_regime[regime]
        counts = Counter(row["target"] for row in group)
        prediction = counts.most_common(1)[0][0]
        regime_table.append(
            {
                "regime": regime,
                "n": len(group),
                "target_counts": dict(sorted(counts.items())),
                "prediction": prediction,
                "correct": sum(row["target"] == prediction for row in group),
            }
        )

    regex_correct = sum(row["regex_s4_match"] for row in rows)
    output = {
        "schema": "guardian-p1a-s4-baselines-v1",
        "scope": {
            "allowed_subset": "S4-derivable positives only",
            "s4_rule": (
                "(dispatch == false AND reset_error is a non-empty string) "
                "OR (a dispatched stalled slot has no non-empty artifact)"
            ),
            "target_state": S4,
            "n": len(rows),
            "residual_judgment_included": False,
            "residual_numbers_emitted": False,
            "observation_cutoff": None,
            "observation_cutoff_status": "not_registered; no residual outputs generated",
        },
        "inputs": input_hashes,
        "baselines": {
            "majority_class": {
                "prediction": majority,
                "correct": majority_correct,
                "n": len(rows),
                "accuracy_within_s4_only": majority_correct / len(rows),
                "specificity": "not_measured: no negatives in authorized subset",
            },
            "table_by_regime": {
                "rows": regime_table,
                "accuracy_within_s4_only": sum(item["correct"] for item in regime_table) / len(rows),
                "specificity": "not_measured: no negatives in authorized subset",
            },
            "regex_s4": {
                "matches": regex_correct,
                "correct": regex_correct,
                "n": len(rows),
                "recall_within_s4_only": regex_correct / len(rows),
                "specificity": "not_measured: no negatives in authorized subset",
            },
        },
        "rows": rows,
        "interpretation": [
            "These are deterministic-rule baselines, not evidence of model quality.",
            "No metric from the 42-case judgment residue was computed or emitted.",
            "No baseline can establish false-positive behavior without authorized negatives.",
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output), "n": len(rows), "regex_matches": regex_correct}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
