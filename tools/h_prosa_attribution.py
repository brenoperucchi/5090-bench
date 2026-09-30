#!/usr/bin/env python3
"""H-PROSA-A2: locate each rater-cited A2 violation in the ledger block, the prose, or both.

Rules frozen in results/guardian-synthesis-20260921/avaliacao/H-PROSA-A2-REGRAS.json
BEFORE this ran. Prose attribution is a *candidate* until the manual validation.
"""
import json, re, sys, unicodedata, urllib.request
from pathlib import Path

B = Path(__file__).resolve().parents[1] / "results/guardian-synthesis-20260921"
A = B / "avaliacao"
KEY = json.load(open(B / "_blind-key.json"))
STOP = set("a o e de da do das dos em no na nos nas um uma que com para por se foi ao os as é está".split())
TS = re.compile(r"\[?(\d{2}/\d{2}) (\d{2}:\d{2})\]?")


def norm(s): return unicodedata.normalize("NFKD", s.lower()).encode("ascii", "ignore").decode()
def words(s): return {w for w in re.findall(r"[a-z0-9_.-]{3,}", norm(s)) if w not in STOP}
def overlap(item, text):
    w = words(item); return len(w & words(text)) / len(w) if w else 0.0


def annex(form: str):
    items = []
    for m in re.finditer(r"^- `(\d{2}/\d{2} \d{2}:\d{2})` \*\*\[([^\]]+)\]\*\* (.+)$", form, re.M):
        items.append({"ts": m.group(1), "res": m.group(2), "text": m.group(3).strip()})
    nv = [i for i in items if i["res"] == "não verificado"]
    return items, nv


def a2_block(form: str) -> str:
    head = form.split("## Resposta avaliada", 1)[0]
    m = re.search(r"^- \[[ xX]\]\s*A2\s*:.*?(?=^- \[|\Z)", head, re.S | re.M)
    return m.group(0).split("Marque o `[x]` se N ≥ 1.", 1)[-1] if m else ""


def resolve(block: str, nv: list, rater: str):
    """Return list of (item|None, raw citation). rev-1: '#n text'; rev-2: carimbo + keyword."""
    out = []
    if rater == "rev-1":
        for m in re.finditer(r"\[(\d{2}/\d{2} \d{2}:\d{2})\]\s*(?:#(\d+))?\s*([^;\]\n]*)", block):
            ts, n, txt = m.groups(); n = int(n) if n else 0
            it = nv[n - 1] if 0 < n <= len(nv) and nv[n - 1]["ts"] == ts else None
            if it is None:  # fall back to text prefix
                c = [i for i in nv if i["ts"] == ts and norm(i["text"]).startswith(norm(txt.strip())[:20])]
                it = c[0] if len(c) == 1 else None
            out.append((it, m.group(0)))
        return out
    # rev-2: split on carimbos; the text after each carimbo up to the next one is its label
    parts = list(TS.finditer(block))
    for k, m in enumerate(parts):
        ts = f"{m.group(1)} {m.group(2)}"
        label = block[m.end(): parts[k + 1].start() if k + 1 < len(parts) else len(block)]
        mult = re.search(r"×\s*(\d)", label)
        cand = [i for i in nv if i["ts"] == ts]
        labs = [l.strip(" ,;.:—-") for l in re.split(r",|;| e ", re.sub(r"×\s*\d", "", label)) if l.strip(" ,;.:—-")]
        labs = [l for l in labs if not re.match(r"^(em|na|no|nas|nos|pendências|forma visual|funcionou|tabela|corpo|resumo|árvore|ledger)\b", norm(l)) or len(words(l)) > 1][:1] if len(cand) > 1 else labs[:1]
        if len(cand) == 1 and not mult:
            out.append((cand[0], m.group(0) + label[:40])); continue
        if mult:  # "×2": every candidate counted, if exactly that many
            n = int(mult.group(1))
            for c in (cand if len(cand) == n else [None] * n):
                out.append((c, m.group(0) + label[:40]))
            continue
        lab = labs[0] if labs else ""
        sc = sorted(((len(words(lab) & words(c["text"])) / max(1, len(words(lab))), k) for k, c in enumerate(cand)), reverse=True) if lab else []
        best = cand[sc[0][1]] if sc and sc[0][0] > 0 and (len(sc) == 1 or sc[0][0] > sc[1][0]) else None
        out.append((best, m.group(0) + label[:40]))
    return out


def split_ledger(content: str):
    i = content.find("```json ledger")
    return (content, "") if i < 0 else (content[:i], content[i:])


def ledger_entries(led: str):
    ents = []
    for m in re.finditer(r"\{[^{}]*\"ref\"\s*:\s*\"([^\"]+)\"[^{}]*\"resultado\"\s*:\s*\"([^\"]+)\"[^{}]*\}", led):
        tre = re.search(r"\"trecho\"\s*:\s*\"([^\"]*)\"", m.group(0))
        afi = re.search(r"\"afirmacao\"\s*:\s*\"([^\"]*)\"", m.group(0))
        ents.append({"ref": m.group(1), "res": m.group(2), "trecho": tre.group(1) if tre else "",
                     "afirmacao": afi.group(1) if afi else "", "raw": m.group(0)})
    return ents


def prose_hits(prose: str, it: dict):
    hits = []
    for line in prose.splitlines():
        if not line.strip():
            continue
        has_ts = it["ts"] in line or it["ts"].split()[1] in line
        ov = overlap(it["text"], line)
        if (has_ts and ov >= 0.25) or ov >= 0.5:
            hits.append(line.strip()[:220])
    return hits


def tokens(text: str) -> int:
    if not text:
        return 0
    req = urllib.request.Request("http://127.0.0.1:18194/tokenize", data=json.dumps({"content": text}).encode(),
                                 headers={"Content-Type": "application/json"})
    return len(json.loads(urllib.request.urlopen(req, timeout=60).read())["tokens"])


def main():
    sets = {"primario": [l.strip() for l in open("/tmp/claude-hl.txt") if l.startswith("v3~")],
            "secundario": [l.strip() for l in open("/tmp/claude-bracos.txt") if l.startswith("v3~")]}
    inv = {v["run"]: k for k, v in KEY.items()}
    out = {"violacoes": [], "respostas": []}
    for sname, runs in sets.items():
        folders = {"primario": ("rev-1-h-ledger", "rev-2-h-ledger"), "secundario": ("rev-1-bracos", "rev-2-bracos")}[sname]
        for run in runs:
            bid = inv[run]; content = json.load(open(B / "runs" / run))["content"]
            prose, led = split_ledger(content); ents = ledger_entries(led)
            form = (B / "checklists" / f"{bid}.md").read_text(); _, nv = annex(form)
            out["respostas"].append({"conjunto": sname, "blind": bid, "run": run, "tokens_prosa": tokens(prose),
                                     "tokens_ledger": tokens(led), "ledger_entradas": len(ents),
                                     "ledger_truncado": bool(led) and not led.rstrip().endswith("```")})
            for folder in folders:
                rater = folder.split("-")[0] + "-" + folder.split("-")[1]
                block = a2_block((A / folder / f"{bid}.md").read_text())
                for it, raw in resolve(block, nv, rater):
                    v = {"conjunto": sname, "blind": bid, "avaliador": rater, "citacao": raw.strip()[:120]}
                    if it is None:
                        v.update(item=None, categoria="nao_resolvido"); out["violacoes"].append(v); continue
                    le = [e for e in ents if e["ref"].strip("[] ") == it["ts"] and overlap(e["trecho"] or e["afirmacao"], it["text"]) >= 0.3]
                    lv = [e for e in le if norm(e["res"]) != norm("não verificado")]
                    ph = prose_hits(prose, it)
                    cat = "ambos" if lv and ph else "ledger" if lv else "prosa" if ph else "ambiguo"
                    v.update(item=it, ledger_match=[{"res": e["res"], "afirmacao": e["afirmacao"][:160]} for e in le],
                             prosa_linhas=ph[:4], categoria=cat)
                    out["violacoes"].append(v)
    json.dump(out, open(A / "h-prosa" / "atribuicao-automatica.json", "w"), ensure_ascii=False, indent=1)
    import collections
    for s in ("primario", "secundario"):
        for r in ("rev-1", "rev-2"):
            c = collections.Counter(v["categoria"] for v in out["violacoes"] if v["conjunto"] == s and v["avaliador"] == r)
            print(s, r, sum(c.values()), dict(c))


if __name__ == "__main__":
    main()
