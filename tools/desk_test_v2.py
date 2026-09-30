#!/usr/bin/env python3
"""Deterministic desk test — spec v2.

Spec: claude-bridge/guardian/aval/TESTE-DE-MESA-SPEC-v2.md, sha256
70de95eee6216b9eafbb430c4727681817413390c8af7ee4d81c68672ce540f9. Replaces v1
(desk_test.py, kept unchanged). Only three things change, per the spec:

1. scope — a response with no carimbo in the prose is ``fora_de_escopo_A2``;
2. caveat inherited from the nearest header above a list, if that header holds a
   marker from the closed list; valid until the next header of the same or a
   higher level; never inside the pendências block;
3. acceptance — provisional (in-sample) here; prospective confirmation later.

Matching, marker list, "?", A5 and C1 are identical to v1 and imported from it.
"""
from __future__ import annotations

import re

import desk_test as v1

SPEC_SHA = "70de95eee6216b9eafbb430c4727681817413390c8af7ee4d81c68672ce540f9"

MD_HEAD = re.compile(r"^\s*(#{1,6})\s")
BOLD_NUM = re.compile(r"^\s*\*\*\d+\.")
# a bold line that opens a list: the whole line is bold, optionally as a bullet
BOLD_LINE = re.compile(r"^\s*(?:[-*]\s+)?\*\*[^*]+\*\*:?\s*$")


def header_level(line: str) -> int | None:
    """Markdown '#'×k → k; bold numbered section ('**N.') → 2; other bold line → 3."""
    m = MD_HEAD.match(line)
    if m:
        return len(m.group(1))
    if BOLD_NUM.match(line):
        return 2
    if BOLD_LINE.match(line):
        return 3
    return None


def has_marker(text: str) -> bool:
    s = v1.norm(text)
    return any(v1.norm(c) in s for c in v1.CAVEATS)


def annotate(prose: str) -> list[tuple[str, str, bool]]:
    """(block, line, inherited_caveat) for every prose line."""
    out, stack = [], []  # stack of (level, carries_marker)
    for block, line in v1.segment(prose):
        lvl = header_level(line)
        if lvl is not None and len(line.strip()) < 160:
            while stack and stack[-1][0] >= lvl:
                stack.pop()
            stack.append((lvl, has_marker(line)))
            out.append((block, line, False))  # the header line itself is not a list item
            continue
        inherited = block != "pendencias" and any(m for _, m in stack)
        out.append((block, line, inherited))
    return out


def in_scope(prose: str) -> bool:
    return bool(v1.TS_RE.search(prose))


def a2(prose: str, items: list[dict], with_question: bool = False) -> dict:
    if not in_scope(prose):
        return {"count": None, "status": "fora_de_escopo_A2"}
    nv = [i for i in items if i["res"] == "não verificado"]
    by_ts: dict[str, list[dict]] = {}
    for it in items:
        by_ts.setdefault(it["ts"], []).append(it)
    violated, ambiguous, blocks = {}, set(), {}
    inherited_hits = 0
    unmatchable = sum(1 for it in nv if len(v1.distinct_words(it["text"])) < 4)
    for block, line, inherited in annotate(prose):
        for m in v1.TS_RE.finditer(line):
            ts = f"{m.group(1)} {m.group(2)}"
            for sent in v1.SENT_SPLIT.split(line):
                if ts not in sent and ts.split()[1] not in sent:
                    continue
                cands = [(len(v1.distinct_words(it["text"]) & v1.distinct_words(sent)), it) for it in by_ts.get(ts, [])]
                cands = sorted([c for c in cands if c[0] >= 4], key=lambda x: -x[0])
                if not cands:
                    continue
                if len(cands) > 1 and cands[0][0] == cands[1][0]:
                    ambiguous.add((ts, sent[:80]))
                    continue
                it = cands[0][1]
                if it["res"] != "não verificado" or len(v1.distinct_words(it["text"])) < 4:
                    continue
                same_sentence = has_marker(sent) or (with_question and "?" in sent)
                if same_sentence:
                    continue
                if inherited:
                    inherited_hits += 1
                    continue
                key = (it["ts"], it["text"])
                violated.setdefault(key, block)
                blocks.setdefault(block, set()).add(key)
    return {"count": len(violated), "status": "medido", "violated": [f"[{k[0]}] {k[1][:70]}" for k in violated],
            "blocks": {b: len(v) for b, v in blocks.items()}, "ambiguous": len(ambiguous),
            "nao_casavel": unmatchable, "ressalva_herdada_aplicada": inherited_hits}


def evaluate(content: str, items: list[dict]) -> dict:
    prose, _ = v1.split_ledger(content)
    r = a2(prose, items)
    return {"A2": r, "A2_com_interrogacao": a2(prose, items, with_question=True)["count"],
            "A5": v1.a5(prose, items), "C1": v1.c1(content)}
