"""Fail-closed scanner for candidate public artifacts.

This is intentionally an explicit release check, not a claim that regexes can
prove a file contains no sensitive information.  A caller passes only the
files intended for publication; findings block that release until reviewed.
"""

from __future__ import annotations

import argparse
import re
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path


_RULES = {
    "authorization": re.compile(r"(?:\bauthorization|[\"']authorization[\"'])\s*[:=]|\bbearer\s+\S+", re.I),
    "credential_assignment": re.compile(r"(?:\b|[\"'])(?:password|passwd|api[_-]?key|token|secret)(?:\b|[\"'])\s*[:=]\s*[\"']?\S+", re.I),
    "private_key": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    "url_userinfo": re.compile(r"\bhttps?://[^\s/@:]+:[^\s/@]+@", re.I),
    "test_canary": re.compile(r"\bCANARY_PRIVATE_[A-Z0-9_]+\b"),
}


@dataclass(frozen=True)
class Finding:
    path: Path
    line: int
    rule: str


def scan_paths(paths: Iterable[str | Path]) -> list[Finding]:
    """Return every policy finding; unreadable or binary input is rejected."""
    findings: list[Finding] = []
    for value in paths:
        path = Path(value)
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            findings.append(Finding(path, 0, f"unreadable_or_non_utf8:{type(exc).__name__}"))
            continue
        for number, line in enumerate(text.splitlines(), 1):
            for name, pattern in _RULES.items():
                if pattern.search(line):
                    findings.append(Finding(path, number, name))
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description="Block candidate public artifacts with sensitive-data signals")
    parser.add_argument("paths", nargs="+", type=Path)
    arguments = parser.parse_args()
    findings = scan_paths(arguments.paths)
    for finding in findings:
        print(f"{finding.path}:{finding.line}: {finding.rule}")
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
