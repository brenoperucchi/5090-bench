#!/usr/bin/env python3
"""Deterministic desk test — spec v3 (the LAST iteration).

Spec: claude-bridge/guardian/aval/TESTE-DE-MESA-SPEC-v3.md, sha256
60fc0f277e32d8568def9cb9bf8841605a25c8a4c96d84f4562057366a445ac7. Replaces v2
(desk_test_v2.py, kept unchanged). Only three things change, per the spec:

1. the ledger's ``arvore`` enters the A2 scope: a node that cites, by carimbo in
   ``refs``, a ``não verificado`` item and states it as fact (no marker in its
   name/estado) is a violation located in ``arvore``; other ledger entries stay out;
2. the matching unit is the LOGICAL item (a list item with its continuation lines,
   or a paragraph), not the physical line;
3. a short item (< 4 distinctive words) matches by carimbo alone when that carimbo
   is unique in the slice; a shared carimbo stays ``nao_casavel``.

The inherited caveat from a "Não verificado" header (v2) does not change.
"""
from __future__ import annotations

import json
import re

import desk_test as v1
import desk_test_v2 as v2

SPEC_SHA = "60fc0f277e32d8568def9cb9bf8841605a25c8a4c96d84f4562057366a445ac7"
LIST_MARK = re.compile(r"^(\s*)(?:[-*+]|\d+[.)])\s+")


def logical_units(prose: str) -> list[tuple[str, str, bool]]:
    """(block, text, inherited_caveat) per logical item. A unit starts at a list
    marker or a non-list line after a break; continuation lines (deeper-indented or
    unmarked, non-blank, non-header) join it; a blank line, a header, or a list
    marker at the same or lower indent closes it."""
    units: list[list] = []
    cur = None  # [block, [lines], inherited, indent]
    for block, line, inherited in v2.annotate(prose):
        if not line.strip():
            cur = None
            continue
        if v2.header_level(line) is not None and len(line.strip()) < 160:
            cur = None
            units.append([block, [line], False, -1])  # a header is a unit of its own
            continue
        m = LIST_MARK.match(line)
        if m:
            ind = len(m.group(1))
            if cur is not None and cur[3] >= 0 and ind > cur[3]:
                # a deeper list marker is a sub-item: its own unit
                pass
            cur = [block, [line], inherited, ind]
            units.append(cur)
            continue
        if cur is None:
            cur = [block, [line], inherited, -2]  # paragraph
            units.append(cur)
        else:
            cur[1].append(line)
    return [(b, " ".join(l.strip() for l in ls), inh) for b, ls, inh, _ in units]


def _pick(ts: str, text: str, by_ts: dict) -> tuple[dict | None, str]:
    """Rule 1–4 of the matching, with the v3 short-item rule."""
    group = by_ts.get(ts, [])
    cands = sorted([(len(v1.distinct_words(it["text"]) & v1.distinct_words(text)), it) for it in group],
                   key=lambda x: -x[0])
    cands = [c for c in cands if c[0] >= 4]
    if cands:
        if len(cands) > 1 and cands[0][0] == cands[1][0]:
            return None, "ambiguo"
        return cands[0][1], "casado"
    if len(group) == 1 and len(v1.distinct_words(group[0]["text"])) < 4:
        return group[0], "casado_curto"  # NOVO v3: unique carimbo, short item
    return None, "sem_casamento"


def arvore_nodes(ledger: str) -> list[dict] | None:
    body = ledger.split("```json ledger", 1)[-1].rsplit("```", 1)[0] if "```" in ledger[10:] else None
    try:
        arv = json.loads(body).get("arvore") if body else None
    except (json.JSONDecodeError, AttributeError):
        return None
    if not isinstance(arv, dict):
        return None
    nodes = []
    for k in ("tronco",):
        if isinstance(arv.get(k), dict):
            nodes.append(arv[k])
    for k in ("ramos", "mortos"):
        nodes += [n for n in (arv.get(k) or []) if isinstance(n, dict)]
    return nodes


def a2(content: str, items: list[dict], with_question: bool = False) -> dict:
    prose, ledger = v1.split_ledger(content)
    if not v2.in_scope(prose):
        return {"count": None, "status": "fora_de_escopo_A2"}
    by_ts: dict[str, list[dict]] = {}
    for it in items:
        by_ts.setdefault(it["ts"], []).append(it)
    nv = [i for i in items if i["res"] == "não verificado"]
    nao_casavel = sum(1 for it in nv if len(v1.distinct_words(it["text"])) < 4 and len(by_ts[it["ts"]]) > 1)
    violated, blocks, ambiguous, inherited_hits, short_hits = {}, {}, 0, 0, 0

    def hit(it, block):
        key = (it["ts"], it["text"])
        violated.setdefault(key, block)
        blocks.setdefault(block, set()).add(key)

    for block, unit, inherited in logical_units(prose):
        for m in v1.TS_RE.finditer(unit):
            ts = f"{m.group(1)} {m.group(2)}"
            for sent in v1.SENT_SPLIT.split(unit):
                if ts not in sent and ts.split()[1] not in sent:
                    continue
                it, how = _pick(ts, sent, by_ts)
                if it is None:
                    ambiguous += how == "ambiguo"
                    continue
                if it["res"] != "não verificado":
                    continue
                if v2.has_marker(sent) or (with_question and "?" in sent):
                    continue
                if inherited:
                    inherited_hits += 1
                    continue
                short_hits += how == "casado_curto"
                hit(it, block)
    nodes = arvore_nodes(ledger) if ledger else []
    for node in nodes or []:
        claim = " ".join(str(node.get(k) or "") for k in ("nome", "estado"))
        for ref in node.get("refs") or []:
            if not isinstance(ref, dict):
                continue
            ts = str(ref.get("ref", "")).strip("[] `")
            # the node cites the item "pelo carimbo em refs" (spec): a unique carimbo
            # identifies it; a shared one is disambiguated by the ref's trecho
            group = by_ts.get(ts, [])
            it, how = (group[0], "carimbo_unico") if len(group) == 1 else _pick(ts, str(ref.get("trecho", "")), by_ts)
            if it is None or it["res"] != "não verificado":
                continue
            if v2.has_marker(claim) or (with_question and "?" in claim):
                continue
            hit(it, "arvore")
    return {"count": len(violated), "status": "medido", "violated": [f"[{k[0]}] {k[1][:70]}" for k in violated],
            "blocks": {b: len(v) for b, v in blocks.items()}, "ambiguous": ambiguous, "nao_casavel": nao_casavel,
            "ressalva_herdada_aplicada": inherited_hits, "casado_curto": short_hits,
            "arvore": "ausente_ou_invalida" if ledger and nodes is None else ("sem_ledger" if not ledger else "lida")}


def evaluate(content: str, items: list[dict]) -> dict:
    prose, _ = v1.split_ledger(content)
    return {"A2": a2(content, items), "A2_com_interrogacao": a2(content, items, with_question=True)["count"],
            "A5": v1.a5(prose, items), "C1": v1.c1(content)}
