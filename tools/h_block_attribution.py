#!/usr/bin/env python3
"""A2 per block (H-PROSA-COMPACT). Rules frozen in avaliacao/H-PROSA-COMPACT-REGRAS.json.

Usage: h_block_attribution.py <runs-list> <rev-1-folder> <rev-2-folder> <out.json>
"""
import collections, json, re, sys
import h_prosa_attribution as h

CAVEAT = re.compile(r"não verificad|nao verificad|não confirmad|nao confirmad|sem confirma|não se sabe|nao se sabe|\?|⚠")
KW = [("pendencias", ("decis", "pendent")), ("lacunas", ("nao da para saber", "lacuna")),
      ("regra_de_negocio", ("regra de negocio", "sendo construido", "problema")), ("so_cabecalho", ("cabecalho",)),
      ("tres_listas", ("funcionou", "falhou", "nao verificado", "tres listas")),
      ("arvore_textual", ("estrutura", "arvore", "tronco", "ramo", "linha do tempo")),
      ("forma_visual", ("visual", "diagrama", "fluxo", "mapa"))]
HEAD = re.compile(r"^\s*(#{1,6}\s.*|\*\*[^*]+\*\*:?\s*|\*\*\d+\..*)$")


def classify(title):
    t = h.norm(title)
    for name, kws in KW:
        if any(k in t for k in kws):
            return name
    return "outro"


def segment(content):
    """[(block, sublist, line)] for every line; ledger from ```json ledger to the end."""
    out, block, sub = [], "outro", None
    i = content.find("```json ledger")
    prose, led = (content, "") if i < 0 else (content[:i], content[i:])
    for line in prose.splitlines():
        if HEAD.match(line) and len(line.strip()) < 160:
            nb = classify(line)
            if nb == "tres_listas" and block == "tres_listas" or nb == "tres_listas":
                sub = "nao_verificado" if "nao verificado" in h.norm(line) else ("funcionou" if "funcionou" in h.norm(line) else ("falhou" if "falhou" in h.norm(line) else sub))
            else:
                sub = None
            block = nb if not (nb == "outro" and block == "tres_listas" and sub) else block
        out.append((block, sub, line))
    return out, led


def main():
    runs, f1, f2, dest = sys.argv[1:5]
    inv = {v["run"]: k for k, v in h.KEY.items()}
    res = {"violacoes": [], "respostas": []}
    for run in [l.strip() for l in open(runs)]:
        bid = inv[run]; content = json.load(open(h.B / "runs" / run))["content"]
        lines, led = segment(content); ents = h.ledger_entries(led)
        form = (h.B / "checklists" / f"{bid}.md").read_text(); _, nv = h.annex(form)
        blocks_present = sorted({b for b, _, _ in lines} | ({"ledger"} if led else set()))
        res["respostas"].append({"blind": bid, "run": run, "blocos": blocks_present,
                                 "tokens_prosa": h.tokens(content[:len(content) - len(led)] if led else content), "tokens_ledger": h.tokens(led)})
        for folder in (f1, f2):
            rater = "rev-1" if "rev-1" in folder else "rev-2"
            block = h.a2_block((h.A / folder / f"{bid}.md").read_text())
            for it, raw in h.resolve(block, nv, rater):
                v = {"blind": bid, "braco": run.split("~")[0], "avaliador": rater, "citacao": raw.strip()[:120]}
                if it is None:
                    v["blocos"] = ["nao_resolvido"]; res["violacoes"].append(v); continue
                hit = collections.OrderedDict()
                for b, sub, line in lines:
                    if b == "tres_listas" and sub == "nao_verificado":
                        continue
                    has_ts = it["ts"] in line or it["ts"].split()[1] in line
                    ov = h.overlap(it["text"], line)
                    if ((has_ts and ov >= 0.25) or ov >= 0.5) and not CAVEAT.search(line):
                        hit.setdefault(b, line.strip()[:200])
                if any(e["ref"].strip("[] ") == it["ts"] and h.overlap(e["trecho"] or e["afirmacao"], it["text"]) >= 0.3
                       and h.norm(e["res"]) != h.norm("não verificado") for e in ents):
                    hit["ledger"] = "resultado ≠ não verificado"
                v.update(item=it, blocos=list(hit) or ["nao_localizado"], linhas=hit)
                res["violacoes"].append(v)
    json.dump(res, open(dest, "w"), ensure_ascii=False, indent=1)
    for arm in sorted({v["braco"] for v in res["violacoes"]}):
        for r in ("rev-1", "rev-2"):
            V = [v for v in res["violacoes"] if v["braco"] == arm and v["avaliador"] == r]
            c = collections.Counter(b for v in V for b in v["blocos"])
            nb = collections.Counter(len(v["blocos"]) for v in V if v["blocos"][0] not in ("nao_resolvido", "nao_localizado"))
            print(f"{arm:11} {r} n={len(V):3} por bloco={dict(c)} | blocos por violação={dict(sorted(nb.items()))}")


if __name__ == "__main__":
    main()
