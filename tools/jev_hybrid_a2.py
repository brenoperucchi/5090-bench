#!/usr/bin/env python3
"""Experiment 1 — desk test v3 + Jev deciding "does this excerpt state the item as fact?".

Rules frozen in results/jev-hibrido-a2-20260924/REGRAS.json before any call.
Candidates are exactly what desk test v3 counts as violations; Jev only filters them.
Every Jev call is persisted (results/jev-hibrido-a2-20260924/chamadas.jsonl), and a
rerun reuses them, so an interruption never re-bills or changes a score.
The API key is read from the environment and never written anywhere.
"""
import json
import os
import statistics
import sys
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import desk_test as v1  # noqa: E402
import desk_test_v2 as v2  # noqa: E402
import desk_test_v3 as v3  # noqa: E402
import guardian_agreement as ga  # noqa: E402
import shadow_lot_forms as s  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
RULES_DIR = ROOT / "results/jev-hibrido-a2-20260924"
RULES = json.load(open(RULES_DIR / "REGRAS.json"))
# JEV_HYB_OUT/SYSTEMONE_URL run the same frozen experiment against another TypeSafe-compatible
# server (e.g. a local Eikos) without mixing its calls with the hosted Jev's.
OUT = Path(os.environ.get("JEV_HYB_OUT", str(RULES_DIR)))
OUT.mkdir(parents=True, exist_ok=True)
CALLS = OUT / "chamadas.jsonl"


def candidates(content: str, items: list[dict]) -> list[dict]:
    """Same loop as desk_test_v3.a2, but keeping the excerpt of each counted occurrence."""
    prose, ledger = v1.split_ledger(content)
    if not v2.in_scope(prose):
        return []
    by_ts: dict[str, list[dict]] = {}
    for it in items:
        by_ts.setdefault(it["ts"], []).append(it)
    out = []
    for block, unit, inherited in v3.logical_units(prose):
        for m in v1.TS_RE.finditer(unit):
            ts = f"{m.group(1)} {m.group(2)}"
            for sent in v1.SENT_SPLIT.split(unit):
                if ts not in sent and ts.split()[1] not in sent:
                    continue
                it, _ = v3._pick(ts, sent, by_ts)
                if it is None or it["res"] != "não verificado" or v2.has_marker(sent) or inherited:
                    continue
                out.append({"item_ts": it["ts"], "item": it["text"], "bloco": block, "trecho": sent.strip()[:600]})
    for node in v3.arvore_nodes(ledger) or [] if ledger else []:
        claim = " ".join(str(node.get(k) or "") for k in ("nome", "estado")).strip()
        for ref in node.get("refs") or []:
            if not isinstance(ref, dict):
                continue
            ts = str(ref.get("ref", "")).strip("[] `")
            group = by_ts.get(ts, [])
            it = group[0] if len(group) == 1 else v3._pick(ts, str(ref.get("trecho", "")), by_ts)[0]
            if it is None or it["res"] != "não verificado" or v2.has_marker(claim):
                continue
            out.append({"item_ts": it["ts"], "item": it["text"], "bloco": "arvore",
                        "trecho": f"nó da árvore do trabalho: {claim}"[:600]})
    # one excerpt per (item, excerpt): identical repeats add no information
    seen, uniq = set(), []
    for c in out:
        k = (c["item_ts"], c["item"], c["trecho"])
        if k not in seen:
            seen.add(k)
            uniq.append(c)
    return uniq


def load_calls() -> dict:
    done = {}
    if CALLS.exists():
        for line in CALLS.read_text().splitlines():
            r = json.loads(line)
            done.setdefault(r["chave"], []).append(r)
    return done


def jev(state: dict, key: str) -> dict:
    j = RULES["jev"]
    body = {"model": j["modelo"], "state": state,
            "questions": {"q": {"type": "noul", "instructions": j["instructions"], "criteria": j["criteria"]}}}
    req = urllib.request.Request(os.environ.get("SYSTEMONE_URL", j["endpoint"]), data=json.dumps(body, ensure_ascii=False).encode(),
                                 headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    t0 = time.perf_counter()
    with urllib.request.urlopen(req, timeout=60) as r:
        d = json.loads(r.read().decode())
    a = d.get("answers", {}).get("q", {})
    return {"score": a.get("noul"), "latency_s": round(time.perf_counter() - t0, 3), "usage": d.get("usage")}


def main() -> int:
    key = os.environ.get("TYPESAFE_API_KEY", "").strip() or ("local" if "SYSTEMONE_URL" in os.environ else "")
    if not key:
        raise SystemExit("TYPESAFE_API_KEY ausente (set -a; . ~/.config/secrets/typesafe.env; set +a)")
    done = load_calls()
    reps = RULES["jev"]["repeticoes"]
    report = {"regras_sha": __import__("hashlib").sha256((RULES_DIR / "REGRAS.json").read_bytes()).hexdigest(), "lotes": {}}
    for lot in ("guardian-shadow-lote-v2", "guardian-shadow-lote-v1"):
        camp = ROOT / "results" / lot
        rows = {r["blind"]: r for r in json.load(open(camp / "lote.json"))}
        ids = json.load(open(camp / "avaliacao/amostra.json"))["blind_ids"]
        per = []
        for bid in ids:
            a = json.load(open(s.AN / f"{rows[bid]['id']}.json"))
            items = v1.annex((camp / "checklists" / f"{bid}.md").read_text())
            cands = candidates(a["text"], items)
            for c in cands:
                chave = f"{lot}|{bid}|{c['item_ts']}|{c['item'][:60]}|{c['trecho'][:120]}"
                calls = done.get(chave, [])
                while len(calls) < reps:
                    state = {"item_da_cronologia": c["item"], "resultado_do_item": "não verificado",
                             "trecho_da_resposta": c["trecho"]}
                    r = {"chave": chave, "rep": len(calls) + 1, **jev(state, key)}
                    with open(CALLS, "a") as f:
                        f.write(json.dumps(r, ensure_ascii=False) + "\n")
                    calls.append(r)
                scores = [x["score"] for x in calls[:reps] if x["score"] is not None]
                c["scores"] = scores
                c["mediana"] = statistics.median(scores) if scores else None
                c["desvio"] = round(statistics.pstdev(scores), 3) if len(scores) > 1 else None
            items_hybrid = {(c["item_ts"], c["item"]) for c in cands if c["mediana"] is not None and c["mediana"] >= 0.5}
            items_v3 = {(c["item_ts"], c["item"]) for c in cands}
            best = {}
            for c in cands:
                k = (c["item_ts"], c["item"])
                best[k] = max(best.get(k, 0), c["mediana"] or 0)
            per.append({"blind": bid, "projeto": rows[bid]["projeto"], "v3": len(items_v3), "hibrido": len(items_hybrid),
                        "soma_scores": round(sum(best.values()), 3),
                        "rev1": ga.raw_count(camp / "avaliacao/rev-1" / f"{bid}.md", "A2"),
                        "rev2": ga.raw_count(camp / "avaliacao/rev-2" / f"{bid}.md", "A2"), "candidatos": cands})
        def sp(k, r):
            return round(ga.spearman([p[k] for p in per], [p[r] for p in per]), 3)
        allc = [c for p in per for c in p["candidatos"] if c["desvio"] is not None]
        report["lotes"][lot] = {
            "n": len(per), "candidatos": sum(len(p["candidatos"]) for p in per),
            "spearman": {k: {"rev1": sp(k, "rev1"), "rev2": sp(k, "rev2")} for k in ("v3", "hibrido", "soma_scores")},
            "rev1_x_rev2": sp("rev1", "rev2"),
            "exato_tres": {k: sum(p[k] == p["rev1"] == p["rev2"] for p in per) for k in ("v3", "hibrido")},
            "jev_desvio_medio": round(statistics.mean(c["desvio"] for c in allc), 3) if allc else None,
            "jev_cruzou_limiar_entre_reps": sum(1 for c in allc if min(c["scores"]) < 0.5 <= max(c["scores"])),
            "por_resposta": per}
        r = report["lotes"][lot]
        print(f"{lot}: n={r['n']} candidatos={r['candidatos']} spearman={r['spearman']} humanos={r['rev1_x_rev2']} "
              f"exato={r['exato_tres']} desvio_jev={r['jev_desvio_medio']} cruzou_0.5={r['jev_cruzou_limiar_entre_reps']}")
    json.dump(report, open(OUT / "RESULTADO.json", "w"), ensure_ascii=False, indent=1)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
