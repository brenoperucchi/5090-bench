#!/usr/bin/env python3
"""Build a deterministic, label-free KL corpus from llm-bench artifacts."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INCLUDE_NAMES = {"metrics.json", "verdict.md", "answer.md"}


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    args = parser.parse_args()

    files = sorted(
        path
        for base in (ROOT / ".herdr/review", ROOT / ".herdr/ask")
        if base.exists()
        for path in base.rglob("*")
        if path.is_file() and path.name in INCLUDE_NAMES
    )
    sections: list[bytes] = []
    manifest_files: list[dict[str, object]] = []
    for path in files:
        relative = path.relative_to(ROOT).as_posix()
        data = path.read_bytes()
        header = f"\n\n===== {relative} =====\n".encode("utf-8")
        sections.extend((header, data))
        manifest_files.append(
            {"path": relative, "bytes": len(data), "sha256": sha256(data)}
        )
    corpus = b"".join(sections).lstrip()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(corpus)
    record = {
        "schema": "llm-bench-kl-corpus-v1",
        "source_root": str(ROOT),
        "labels_included": False,
        "included_names": sorted(INCLUDE_NAMES),
        "file_count": len(manifest_files),
        "bytes": len(corpus),
        "sha256": sha256(corpus),
        "files": manifest_files,
    }
    args.manifest.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: record[k] for k in ("file_count", "bytes", "sha256")}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
