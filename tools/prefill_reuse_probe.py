#!/usr/bin/env python3
"""Does prompt layout let llama.cpp reuse the prefill across typed questions?

P4 measured four typed questions costing 3.6–4.1× one question. Parallel
constrained decoding avoids that by computing the context once. llama.cpp
already reuses a cached prefix per slot, but only up to the first differing
token — so the *layout* decides whether the reuse can happen at all:

* layout A — question BEFORE the context: prompts diverge early; little reuse;
* layout B — context FIRST, question at the END: the whole context is a shared
  prefix; only the question tail should need prefill.

Every call is persisted with the server's own `timings` (prompt_n = tokens
actually evaluated, cache_n = tokens served from cache). The production server
is shared with the Guardian narrator, whose requests can evict the cache
between ours; that is recorded as it happens, not corrected away.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import time
import urllib.request
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SNAP = ROOT / "results/guardian-synthesis-20260921/snapshots/mfc-exec~Ryzen9~ff6b18a9aaf6.prompt.md"

QUESTIONS = {
    "estado": ("Qual o estado do trabalho descrito?",
               {"A": "concluído", "B": "em andamento", "C": "bloqueado", "D": "indeterminado"}),
    "pendencia": ("Há decisão esperando o Breno?",
                  {"A": "sim, explícita", "B": "sim, implícita", "C": "não", "D": "não dá para saber"}),
    "risco": ("Há risco operacional em aberto?",
              {"A": "alto", "B": "médio", "C": "baixo", "D": "não dá para saber"}),
    "direcao": ("Qual a direção da migração?",
                {"A": "para fora do Ryzen9", "B": "para o Ryzen9", "C": "sem migração", "D": "não dá para saber"}),
}


def question_block(qid: str) -> str:
    q, opts = QUESTIONS[qid]
    return q + "\n" + "\n".join(f"{k} = {v}" for k, v in opts.items()) + "\nResponda só com a letra."


def prompt(layout: str, qid: str, context: str) -> str:
    if layout == "A":
        return "PERGUNTA:\n" + question_block(qid) + "\n\nCONTEXTO:\n" + context
    return "CONTEXTO:\n" + context + "\n\nPERGUNTA:\n" + question_block(qid)


def call(endpoint: str, text: str) -> dict:
    body = {"model": "qwen3-coder-30b", "messages": [{"role": "user", "content": text}],
            "temperature": 0, "max_tokens": 1, "cache_prompt": True}
    req = urllib.request.Request(endpoint, data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
                                 headers={"Content-Type": "application/json"})
    t0 = time.perf_counter()
    with urllib.request.urlopen(req, timeout=120) as r:
        d = json.loads(r.read().decode("utf-8"))
    return {"latency_s": round(time.perf_counter() - t0, 4),
            "answer": d["choices"][0]["message"].get("content"),
            "usage": d.get("usage"), "timings": d.get("timings")}


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--endpoint", default="http://127.0.0.1:18194/v1/chat/completions")
    p.add_argument("--repeats", type=int, default=3)
    p.add_argument("--out", default=str(ROOT / "results/prefill-reuse-20260922.json"))
    a = p.parse_args()
    out_path = Path(a.out)
    if out_path.exists():
        raise SystemExit(f"recuso sobrescrever {out_path}")
    context = SNAP.read_text(encoding="utf-8")
    calls = []
    for rep in range(1, a.repeats + 1):
        for layout in ("A", "B"):
            # one question alone first (the "1×" reference), then the four in sequence
            for position, qid in enumerate(["estado", "estado", "pendencia", "risco", "direcao"]):
                role = "sozinha" if position == 0 else "sequencia"
                text = prompt(layout, qid, context)
                r = call(a.endpoint, text)
                rec = {"repeticao": rep, "layout": layout, "papel": role, "pergunta": qid,
                       "timestamp": datetime.now().astimezone().isoformat(timespec="milliseconds"),
                       "prompt_sha256": hashlib.sha256(text.encode()).hexdigest(), **r}
                calls.append(rec)
                t = r.get("timings") or {}
                print(f"rep{rep} {layout} {role:9} {qid:9} {r['latency_s']:.3f}s prompt_n={t.get('prompt_n')} "
                      f"cache_n={t.get('cache_n')} resp={r['answer']!r}")
    # derived
    agg = {}
    for layout in ("A", "B"):
        alone = [c["latency_s"] for c in calls if c["layout"] == layout and c["papel"] == "sozinha"]
        four = [sum(c["latency_s"] for c in calls if c["layout"] == layout and c["papel"] == "sequencia"
                    and c["repeticao"] == r) for r in range(1, a.repeats + 1)]
        pn = [(c.get("timings") or {}).get("prompt_n") for c in calls if c["layout"] == layout and c["papel"] == "sequencia"]
        pn = [x for x in pn if x is not None]
        agg[layout] = {"uma_sozinha_mediana_s": statistics.median(alone),
                       "quatro_em_sequencia_mediana_s": statistics.median(four),
                       "razao_quatro_sobre_uma": round(statistics.median(four) / statistics.median(alone), 3),
                       "prompt_n_mediano_na_sequencia": statistics.median(pn) if pn else None}
    doc = {"schema": "prefill-reuse-probe-v1", "endpoint": a.endpoint, "modelo": "qwen3-coder-30b",
           "contexto": str(SNAP.relative_to(ROOT)), "contexto_sha256": hashlib.sha256(context.encode()).hexdigest(),
           "ressalva": "servidor de produção compartilhado com o narrador; requisições dele podem despejar o cache entre as nossas",
           "chamadas": calls, "derivados": agg}
    out_path.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("\n" + json.dumps(agg, ensure_ascii=False, indent=2))
    print(f"escrito: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
