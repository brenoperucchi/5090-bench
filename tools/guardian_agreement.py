#!/usr/bin/env python3
"""Inter-rater agreement for the Guardian synthesis checklists.

Reads the two evaluators' filled-in forms, pairs them by blind id and criterion,
and reports Cohen's kappa per criterion and overall.

The gate comes from the campaign plan: **kappa below 0.60 sends the rubric back
for revision instead of producing a final number.** A criterion where both
raters always answer the same way has undefined kappa — that is reported as
such, never as 1.0, because unanimity on a constant is not agreement about a
judgement.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CAMPAIGN = ROOT / "results" / "guardian-synthesis-20260921"

# "- [x] C1: ..." / "- [ ] A3.1a-...: ..."
LINE = re.compile(r"^- \[( |x|X)\]\s*([A-Za-z0-9.\-]+)\s*:", re.M)
GRADE = re.compile(r"^\s*(forte|parcial|ausente)\s*$", re.I | re.M)
COUNT = re.compile(r"contagem\s*[:=]\s*(\d+)", re.I)


def faixa(n: int) -> str:
    """Faixas congeladas em GATE-REGRAS.json antes de ver contagens."""
    return "0" if n == 0 else "1-2" if n <= 2 else "3-5" if n <= 5 else ">=6"
NA = re.compile(r"^\s*n/a\b", re.I | re.M)


def parse_form(path: Path) -> dict[str, Any]:
    """Extract one answer per criterion. Unticked means 'não', not 'unanswered' —
    the protocol says so explicitly, so a blank box is a real answer."""
    text = path.read_text(encoding="utf-8")
    # Only the part before the evaluated response: the answer text can contain
    # anything, including lines that look like checklist items.
    head = text.split("## Resposta avaliada", 1)[0]
    out: dict[str, Any] = {}
    marks = list(LINE.finditer(head))
    for n, m in enumerate(marks):
        ticked = m.group(1).lower() == "x"
        key = m.group(2)
        # The annotation window must stop at the next criterion, or a grade
        # written under C2 gets attributed to C1.
        end = marks[n + 1].start() if n + 1 < len(marks) else len(head)
        segment = head[m.end():end]
        # A line explicitly marked n/a is excluded from agreement, not counted
        # as "não" — that distinction is what the protocol asks for.
        if NA.search(segment):
            out[key] = "n/a"
            continue
        cnt = COUNT.search(segment)
        if cnt:
            out[key] = faixa(int(cnt.group(1)))
            continue
        grade = GRADE.search(segment)
        out[key] = grade.group(1).lower() if grade else ("sim" if ticked else "nao")
    return out


def cohen_kappa(a: list[str], b: list[str]) -> tuple[float | None, str]:
    """Cohen's kappa, with the degenerate cases named instead of hidden."""
    assert len(a) == len(b)
    n = len(a)
    if n == 0:
        return None, "sem pares"
    labels = sorted(set(a) | set(b))
    if len(labels) == 1:
        return None, f"indefinido: os dois responderam sempre '{labels[0]}' ({n} pares)"
    po = sum(1 for x, y in zip(a, b) if x == y) / n
    pe = sum((a.count(l) / n) * (b.count(l) / n) for l in labels)
    if abs(1 - pe) < 1e-12:
        return None, f"indefinido: concordância esperada = 1 (po={po:.2f})"
    return (po - pe) / (1 - pe), f"po={po:.2f} pe={pe:.2f} n={n}"


def raw_count(path: Path, crit: str) -> int | None:
    """The integer count written under a counting criterion, before binning."""
    head = path.read_text(encoding="utf-8").split("## Resposta avaliada", 1)[0]
    m = re.search(r"^- \[[ xX]\]\s*" + re.escape(crit) + r"\s*:.*?(?=^- \[|\Z)", head, re.S | re.M)
    c = COUNT.search(m.group(0)) if m else None
    return int(c.group(1)) if c else None


def spearman(x: list[float], y: list[float]) -> float | None:
    def rank(v):
        order = sorted(range(len(v)), key=lambda i: v[i]); r = [0.0] * len(v); i = 0
        while i < len(order):
            j = i
            while j + 1 < len(order) and v[order[j + 1]] == v[order[i]]:
                j += 1
            for k in range(i, j + 1):
                r[order[k]] = (i + j) / 2 + 1
            i = j + 1
        return r
    if len(x) < 2:
        return None
    rx, ry = rank(x), rank(y)
    mx, my = sum(rx) / len(rx), sum(ry) / len(ry)
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    den = (sum((a - mx) ** 2 for a in rx) * sum((b - my) ** 2 for b in ry)) ** 0.5
    return None if den == 0 else num / den


def gwet_ac1(a: list[str], b: list[str]) -> float | None:
    """Gwet's AC1, k categories. Stable under extreme prevalence, where κ collapses."""
    n = len(a)
    if n == 0:
        return None
    labels = sorted(set(a) | set(b))
    k = len(labels)
    po = sum(1 for x, y in zip(a, b) if x == y) / n
    if k == 1:
        return 1.0
    pi = {l: (a.count(l) + b.count(l)) / (2 * n) for l in labels}
    pe = sum(p * (1 - p) for p in pi.values()) / (k - 1)
    return None if abs(1 - pe) < 1e-12 else (po - pe) / (1 - pe)


def gate_criterion(a: list[str], b: list[str], rules: dict) -> dict:
    n = len(a)
    k, knote = cohen_kappa(a, b)
    ac1 = gwet_ac1(a, b)
    po = sum(1 for x, y in zip(a, b) if x == y) / n if n else None
    allm = a + b
    dom = max(allm.count(l) for l in set(allm)) / len(allm) if allm else None
    g = rules["gate_por_criterio"]
    extrema = dom is not None and dom >= rules["prevalencia_extrema"]["limiar"]
    if n < g["piso_n"]:
        res, decidiu = "NOT_EVALUABLE", f"n < {g['piso_n']}"
    elif extrema:
        decidiu = "ac1"
        res = "PASS" if (ac1 is not None and ac1 >= g["limiar"]) else "FAIL"
    else:
        decidiu = "kappa"
        # constant answers with non-extreme prevalence cannot happen; a None κ here fails safe
        res = "PASS" if (k is not None and k >= g["limiar"]) else "FAIL"
    return {"n": n, "kappa": k, "kappa_nota": knote, "ac1": ac1, "concordancia_bruta": po,
            "desacordos": sum(1 for x, y in zip(a, b) if x != y),
            "prevalencia_dominante": dom, "prevalencia_extrema": extrema,
            "medida_que_decidiu": decidiu, "gate_result": res}


def cmd_report(a: argparse.Namespace) -> int:
    camp = Path(a.campaign)
    base = camp / "avaliacao"
    ids = json.loads((base / a.sample).read_text(encoding="utf-8"))["blind_ids"]
    forms = {}
    for who in a.rater:
        forms[who] = {}
        for bid in ids:
            p = base / who / f"{bid}.md"
            if p.exists():
                forms[who][bid] = parse_form(p)
    r1, r2 = a.rater
    done = [b for b in ids if b in forms[r1] and b in forms[r2]]
    print(f"pares completos: {len(done)}/{len(ids)}")
    if not done:
        return 1

    criteria = sorted({k for b in done for k in (set(forms[r1][b]) | set(forms[r2][b]))})
    rows = []
    all_a: list[str] = []
    all_b: list[str] = []
    for c in criteria:
        pa, pb = [], []
        for b in done:
            x, y = forms[r1][b].get(c), forms[r2][b].get(c)
            if x is None or y is None or x == "n/a" or y == "n/a":
                continue
            pa.append(x)
            pb.append(y)
        k, note = cohen_kappa(pa, pb)
        rows.append((c, len(pa), k, note))
        all_a += pa
        all_b += pb

    print(f"\n{'critério':26} {'n':>3} {'kappa':>7}  observação")
    for c, n, k, note in rows:
        ks = f"{k:.3f}" if k is not None else "  —  "
        flag = "" if k is None or k >= 0.6 else "  ⚠ abaixo do gate"
        print(f"{c:26} {n:>3} {ks:>7}  {note}{flag}")

    # Gate POR EIXO (owner, 2026-09-22 18:01). O kappa global passou (0,711)
    # enquanto os quatro critérios de fidelidade estavam entre 0,13 e 0,36: os
    # avaliadores concordavam sobre formato e discordavam justamente sobre
    # verdade. Global não libera nada sozinho; cada eixo passa ou falha.
    eixos = {"fidelidade": lambda c: c.startswith("A"),
             "estrutura": lambda c: c.startswith(("B", "C"))}
    gate_eixos = {}
    for nome, pert in eixos.items():
        ea, eb = [], []
        for c in criteria:
            if not pert(c):
                continue
            for b in done:
                x, y = forms[r1][b].get(c), forms[r2][b].get(c)
                if x in (None, "n/a") or y in (None, "n/a"):
                    continue
                ea.append(x)
                eb.append(y)
        ke, ne = cohen_kappa(ea, eb)
        abaixo = [r[0] for r in rows if pert(r[0]) and r[2] is not None and r[2] < 0.6]
        passou = ke is not None and ke >= 0.6 and not abaixo
        gate_eixos[nome] = {"kappa": ke, "nota": ne, "criterios_abaixo": abaixo, "passou": passou}
        print(f"\neixo {nome:10}: kappa={f'{ke:.3f}' if ke is not None else '—'}  "
              f"{'PASSOU' if passou else 'FALHOU'}" + (f"  (abaixo: {', '.join(abaixo)})" if abaixo else ""))

    k, note = cohen_kappa(all_a, all_b)
    print(f"\nglobal: kappa={f'{k:.3f}' if k is not None else '—'}  {note}  "
          "(informativo — NÃO libera número nenhum sozinho)")
    measurable = [r for r in rows if r[2] is not None]
    below = [r for r in measurable if r[2] < 0.6]
    if k is not None and k < 0.6:
        print("\n⚠ GATE: kappa global abaixo de 0,60 — a rubrica volta para revisão "
              "antes de qualquer número final.")
    elif below:
        print(f"\n⚠ {len(below)} critério(s) abaixo do gate individualmente: "
              + ", ".join(r[0] for r in below))
    if len(measurable) < len(rows):
        print(f"\nnota: {len(rows) - len(measurable)} critério(s) sem kappa definido "
              "(resposta constante) — unanimidade sobre uma constante não é concordância "
              "sobre um julgamento.")

    # ------------------------------------------------------------- gate v2
    rules = json.loads((camp / "avaliacao" / "GATE-REGRAS.json").read_text(encoding="utf-8"))
    gv2 = {}
    print(f"\n=== GATE v2 (regras congeladas: GATE-REGRAS.json)")
    print(f"{'critério':30}{'n':>3}{'κ':>8}{'AC1':>8}{'bruta':>7}{'desac':>6}{'dom':>6}  decide  resultado")
    for c in criteria:
        pa, pb = [], []
        for bb in done:
            x, y = forms[r1][bb].get(c), forms[r2][bb].get(c)
            if x in (None, "n/a") or y in (None, "n/a"):
                continue
            pa.append(x); pb.append(y)
        r = gate_criterion(pa, pb, rules); gv2[c] = r
        f = lambda v: "   —" if v is None else f"{v:.3f}"
        print(f"{c:30}{r['n']:>3}{f(r['kappa']):>8}{f(r['ac1']):>8}{f(r['concordancia_bruta']):>7}{r['desacordos']:>6}"
              f"{f(r['prevalencia_dominante']):>6}  {r['medida_que_decidiu'][:6]:6}  {r['gate_result']}")
    # Critérios de CONTAGEM decidem por Spearman sobre as contagens integrais
    # (GATE-REGRAS-v3.json). A regra é prospectiva: só vale para rodada nova.
    rules3_path = camp / "avaliacao" / "GATE-REGRAS-v3.json"
    if rules3_path.exists() and getattr(a, "gate_v3", False):
        r3 = json.loads(rules3_path.read_text(encoding="utf-8"))
        cc = r3["criterios_de_contagem"]
        for crit in cc["criterios"]:
            xs, ys = [], []
            for bb in done:
                x = raw_count(base / r1 / f"{bb}.md", crit); y = raw_count(base / r2 / f"{bb}.md", crit)
                if x is not None and y is not None:
                    xs.append(x); ys.append(y)
            rho = spearman(xs, ys)
            res = ("NOT_EVALUABLE" if len(xs) < cc["piso_n"] else
                   "PASS" if (rho is not None and rho >= 0.80) else "FAIL")
            import statistics as _st
            gv2[crit] = {**gv2.get(crit, {}), "n_contagens": len(xs), "spearman": rho,
                         "contagens": {r1: xs, r2: ys},
                         "razao_mediana": (_st.median(p / q for p, q in zip(xs, ys) if q) if xs else None),
                         "medida_que_decidiu": "spearman", "gate_result": res}
            print(f"{crit:30} contagem: n={len(xs)} ρ={rho if rho is None else round(rho,3)}  decide spearman  {res}")
    eixos_v2 = {}
    for nome, pert in (("fidelidade", lambda c: c.startswith("A")), ("estrutura", lambda c: c.startswith(("B", "C")))):
        rs = [gv2[c]["gate_result"] for c in gv2 if pert(c)]
        aval = [x for x in rs if x != "NOT_EVALUABLE"]
        eixos_v2[nome] = "NOT_EVALUABLE" if not aval else ("PASS" if all(x == "PASS" for x in aval) else "FAIL")
        falhas = [c for c in gv2 if pert(c) and gv2[c]["gate_result"] == "FAIL"]
        print(f"eixo {nome:10}: {eixos_v2[nome]}" + (f"  (FAIL: {', '.join(falhas)})" if falhas else ""))

    out = camp / "avaliacao" / a.out
    out.write_text(json.dumps({
        "schema": "guardian-agreement-v1",
        "raters": list(a.rater),
        "pairs": len(done),
        "per_criterion": [{"criterion": c, "n": n, "kappa": k, "note": note} for c, n, k, note in rows],
        "overall": {"kappa": k, "note": note, "papel": "informativo; não libera nada sozinho"},
        "gate_por_eixo": gate_eixos,
        "gate_v2": {"regras": "GATE-REGRAS.json", "por_criterio": gv2, "por_eixo": eixos_v2},
        "gate": "cada eixo com kappa >= 0.60 E nenhum critério do eixo abaixo de 0.60",
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"\nescrito: {out.relative_to(ROOT)}")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--campaign", default=str(DEFAULT_CAMPAIGN))
    p.add_argument("--rater", action="append", default=None,
                   help="evaluator folder name; pass twice (default: think, scout)")
    p.add_argument("--sample", default="amostra-16.json")
    p.add_argument("--out", default="concordancia.json")
    p.add_argument("--gate-v3", action="store_true",
                   help="aplica GATE-REGRAS-v3.json (A2 por Spearman) — só para rodada NOVA")
    a = p.parse_args(argv)
    if not a.rater:
        a.rater = ["think", "scout"]
    if len(a.rater) != 2:
        p.error("exatamente dois avaliadores")
    return cmd_report(a)


if __name__ == "__main__":
    raise SystemExit(main())
