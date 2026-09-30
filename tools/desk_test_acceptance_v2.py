#!/usr/bin/env python3
"""Provisional (in-sample) acceptance of desk test v2 against the human-rated responses (spec thresholds, frozen)."""
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import desk_test as dt
import desk_test_v2 as v2
import guardian_agreement as ga

A = dt.CAMP / "avaliacao"
KEY = json.load(open(dt.CAMP / "_blind-key.json"))
ROUNDS = [("bracos", "amostra-bracos.json", "rev-1-bracos", "rev-2-bracos", "scout-bracos"),
          ("h-ledger", "amostra-h-ledger.json", "rev-1-h-ledger", "rev-2-h-ledger", "scout-h-ledger"),
          ("compact", "amostra-compact.json", "rev-1-compact", "rev-2-compact", "scout-compact")]
rows = []
for name, sample, r1, r2, sc in ROUNDS:
    for bid in json.load(open(A / sample))["blind_ids"]:
        run = json.load(open(dt.CAMP / "runs" / KEY[bid]["run"]))
        items = dt.annex((dt.CAMP / "checklists" / f"{bid}.md").read_text())
        ev = v2.evaluate(run["content"], items)
        f1, f2 = ga.parse_form(A / r1 / f"{bid}.md"), ga.parse_form(A / r2 / f"{bid}.md")
        scp = A / sc / f"{bid}.md"
        fs = ga.parse_form(scp) if scp.exists() else {}
        def cons(c):
            a, b = f1.get(c), f2.get(c)
            return a if a == b else fs.get(c)  # None if split and not arbitrated
        rows.append({"rodada": name, "blind": bid, "braco": KEY[bid]["run"].split("~")[0],
                     "A2_mesa": ev["A2"]["count"], "A2_mesa_com_interrogacao": ev["A2_com_interrogacao"],
                     "A2_rev1": ga.raw_count(A / r1 / f"{bid}.md", "A2"), "A2_rev2": ga.raw_count(A / r2 / f"{bid}.md", "A2"),
                     "A2_status": ev["A2"]["status"], "A2_blocos": ev["A2"].get("blocks"), "A2_herdada": ev["A2"].get("ressalva_herdada_aplicada"), "A2_ambiguo": ev["A2"].get("ambiguous"), "A2_nao_casavel": ev["A2"].get("nao_casavel"),
                     "C1_mesa": "sim" if ev["C1"] else "nao", "C1_humano": cons("C1"),
                     "A5_mesa": ev["A5"]["violacao"], "A5_entidades": ev["A5"]["entidades_sem_fonte"], "A5_humano": cons("A5")})
json.dump(rows, open(A / "teste-de-mesa" / "aceitacao-v2-provisoria-por-resposta.json", "w"), ensure_ascii=False, indent=1)
out = {"spec_sha256": v2.SPEC_SHA, "etapa": "provisória, in-sample — NÃO valida", "n": len(rows)}
for r in ("rev1", "rev2"):
    P = [(x["A2_mesa"], x[f"A2_{r}"]) for x in rows if x[f"A2_{r}"] is not None and x["A2_mesa"] is not None]
    out[f"A2_spearman_{r}"] = round(ga.spearman([p[0] for p in P], [p[1] for p in P]), 3)
    out[f"A2_n_{r}"] = len(P)
out["A2_fora_de_escopo"] = sum(x["A2_mesa"] is None for x in rows)
C = [x for x in rows if x["C1_humano"] in ("sim", "nao")]
out["C1_concordancia_exata"] = round(sum(x["C1_mesa"] == x["C1_humano"] for x in C) / len(C), 3)
out["C1_n"] = len(C); out["C1_sem_consenso"] = len(rows) - len(C)
F = [x for x in rows if x["A5_mesa"]]
out["A5_sinalizadas_mesa"] = len(F)
out["A5_precisao_vs_humano"] = round(sum(x["A5_humano"] == "sim" for x in F) / len(F), 3) if F else None
out["A5_humano_sim"] = sum(x["A5_humano"] == "sim" for x in rows)
out["aceite"] = {"A2": out["A2_spearman_rev1"] >= 0.80 and out["A2_spearman_rev2"] >= 0.80,
                 "C1": out["C1_concordancia_exata"] >= 0.95}
json.dump(out, open(A / "teste-de-mesa" / "aceitacao-v2-provisoria.json", "w"), ensure_ascii=False, indent=1)
print(json.dumps(out, ensure_ascii=False, indent=1))
