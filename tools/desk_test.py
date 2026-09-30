#!/usr/bin/env python3
"""Deterministic desk test for Guardian synthesis — spec v1.

Spec: claude-bridge/guardian/aval/TESTE-DE-MESA-SPEC.md, sha256
54c9dc7818143675c4b09e3965cad92775074b3a335fcbe80acc462ac96e1e39, frozen before
this code was written. Implemented literally; any divergence from the human
rating is reported, never tuned here (a fix is a v2 of the spec, written by
claude-bridge).

Scope v1: A2, A5 (named entities only), C1.
"""
from __future__ import annotations

import json
import re
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CAMP = ROOT / "results/guardian-synthesis-20260921"
SPEC_SHA = "54c9dc7818143675c4b09e3965cad92775074b3a335fcbe80acc462ac96e1e39"

# Frozen stopword list (spec: "lista de palavras vazias, congelada no código").
STOP = frozenset("""
a o e as os de da do das dos em no na nos nas um uma uns umas que com para por
se foi ao aos à às é está estão era ser sido ter tem foram pelo pela pelos pelas
como mas ou já não sim mais menos muito muita seu sua seus suas ele ela eles
elas isso este esta esse essa isto aquele aquela entre sobre sem até após
também quando onde porque pois então nem cada todo toda todos todas outro outra
agente item itens foi feita feito sendo está sendo
""".split())

# Frozen caveat markers (spec, closed list). "?" is NOT a caveat.
CAVEATS = ("não verificado", "não confirmado", "sem confirmação", "a confirmar",
           "pendente de verificação", "não foi verificado", "não foi confirmado",
           "(não verificado)")

TS_RE = re.compile(r"(\d{2}/\d{2}) (\d{2}:\d{2})")
SENT_SPLIT = re.compile(r"(?<=[.!;])\s+|\s+—\s+")


def norm(s: str) -> str:
    return unicodedata.normalize("NFKD", s.lower()).encode("ascii", "ignore").decode()


def distinct_words(s: str) -> set[str]:
    stop = {norm(w) for w in STOP}
    return {w for w in re.findall(r"[a-z0-9_./\\:-]{3,}", norm(s)) if w not in stop}


def annex(form: str) -> list[dict]:
    items = []
    for m in re.finditer(r"^- `(\d{2}/\d{2} \d{2}:\d{2})` \*\*\[([^\]]+)\]\*\* (.+)$", form, re.M):
        items.append({"ts": m.group(1), "res": m.group(2), "text": m.group(3).strip()})
    return items


def split_ledger(content: str) -> tuple[str, str]:
    i = content.find("```json ledger")
    return (content, "") if i < 0 else (content[:i], content[i:])


# --- block segmentation: same header rule as H-PROSA-COMPACT ---------------------
HEAD = re.compile(r"^\s*(#{1,6}\s.*|\*\*[^*]+\*\*:?\s*|\*\*\d+\..*)$")
KW = [("pendencias", ("decis", "pendent")), ("lacunas", ("nao da para saber", "lacuna")),
      ("regra_de_negocio", ("regra de negocio", "sendo construido", "problema")),
      ("so_cabecalho", ("cabecalho",)),
      ("tres_listas", ("funcionou", "falhou", "nao verificado", "tres listas")),
      ("arvore_textual", ("estrutura", "arvore", "tronco", "ramo", "linha do tempo")),
      ("forma_visual", ("visual", "diagrama", "fluxo", "mapa"))]


def classify(title: str) -> str:
    t = norm(title)
    for name, kws in KW:
        if any(k in t for k in kws):
            return name
    return "outro"


def segment(prose: str) -> list[tuple[str, str]]:
    out, block = [], "outro"
    for line in prose.splitlines():
        if HEAD.match(line) and len(line.strip()) < 160:
            block = classify(line)
        out.append((block, line))
    return out


# --- A2 --------------------------------------------------------------------------
def a2(prose: str, items: list[dict], with_question: bool = False) -> dict:
    nv = [i for i in items if i["res"] == "não verificado"]
    by_ts: dict[str, list[dict]] = {}
    for it in items:
        by_ts.setdefault(it["ts"], []).append(it)
    violated, ambiguous, unmatchable, blocks = {}, set(), [], {}
    for it in nv:
        if len(distinct_words(it["text"])) < 4:
            unmatchable.append(it["text"][:60])
    for block, line in segment(prose):
        for m in TS_RE.finditer(line):
            ts = f"{m.group(1)} {m.group(2)}"
            for sent in SENT_SPLIT.split(line):
                if ts not in sent and ts.split()[1] not in sent:
                    continue
                cands = []
                for it in by_ts.get(ts, []):
                    ov = len(distinct_words(it["text"]) & distinct_words(sent))
                    if ov >= 4:
                        cands.append((ov, it))
                if not cands:
                    continue
                cands.sort(key=lambda x: -x[0])
                if len(cands) > 1 and cands[0][0] == cands[1][0]:
                    ambiguous.add((ts, sent[:80]))
                    continue
                it = cands[0][1]
                if it["res"] != "não verificado" or len(distinct_words(it["text"])) < 4:
                    continue
                s = norm(sent)
                caveat = any(norm(c) in s for c in CAVEATS) or (with_question and "?" in sent)
                if not caveat:
                    key = (it["ts"], it["text"])
                    violated.setdefault(key, block)
                    blocks.setdefault(block, set()).add(key)
    return {"count": len(violated), "violated": [f"[{k[0]}] {k[1][:70]}" for k in violated],
            "blocks": {b: len(v) for b, v in blocks.items()}, "ambiguous": len(ambiguous),
            "nao_casavel": len(unmatchable)}


# --- A5 (named entities only) -----------------------------------------------------
ENT_PATTERNS = {
    "ip": re.compile(r"\b\d{1,3}(?:\.\d{1,3}){3}\b"),
    # ":NNNN" only when not the minutes of a carimbo "hh:mm" (implementation fix, 23/09)
    "porta": re.compile(r"(?:porta|port)\s+(\d{2,5})\b|(?<!\d\d):(\d{2,5})\b", re.I),
    "caminho": re.compile(r"(?:[A-Za-z]:\\[^\s`'\")]+|(?<![\w.])/(?:[\w.-]+/)+[\w.-]*)"),
    "container": re.compile(r"\b(?:mt5|mfc)[\w]*-[\w-]+\b", re.I),
    "host": re.compile(r"\bRyzen\d+\w*\b|\b[A-Z][A-Za-z]*\d+[A-Za-z]*WSL\b"),
}


def a5(prose: str, items: list[dict]) -> dict:
    corpus = norm(" ".join(i["text"] for i in items))
    found = []
    for kind, pat in ENT_PATTERNS.items():
        for m in pat.finditer(prose):
            ent = next((g for g in m.groups() if g), None) if m.groups() else m.group(0)
            ent = (ent or m.group(0)).rstrip(".,;:)`")
            if len(ent) < 2:
                continue
            if norm(ent) not in corpus:
                found.append(f"{kind}:{ent}")
    return {"violacao": bool(found), "entidades_sem_fonte": sorted(set(found))[:20]}


# --- C1 ---------------------------------------------------------------------------
LITERAL_NONE = "Nenhuma decisão pendente registrada nos itens."


def c1(content: str) -> bool:
    prose, _ = split_ledger(content)
    lines = [l for l in prose.splitlines() if l.strip()]
    i = 0
    # a leading isolated title (single header line followed by another header) is skipped
    if lines and lines[0].lstrip().startswith("# ") and len(lines) > 1 and HEAD.match(lines[1]):
        i = 1
    for line in lines[i:]:
        if LITERAL_NONE in line:
            return True
        if HEAD.match(line):
            return classify(line) == "pendencias"
        return False
    return False


def evaluate(content: str, items: list[dict]) -> dict:
    prose, _ = split_ledger(content)
    return {"A2": a2(prose, items), "A2_com_interrogacao": a2(prose, items, with_question=True)["count"],
            "A5": a5(prose, items), "C1": c1(content)}


if __name__ == "__main__":
    run = json.load(open(sys.argv[1]))
    snap = json.load(open(CAMP / "snapshots" / f"{run['snapshot']}.json"))
    print(json.dumps(evaluate(run["content"], snap), ensure_ascii=False, indent=1))
