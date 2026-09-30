#!/usr/bin/env python3
"""Blind rubric-4 forms for LOTE-SHADOW-V1 (the 20 COMPACT shadow responses).

Source of truth: claude-bridge/guardian/aval/lote-shadow-v1.json + analyses/<id>.json
(+ prompts/<promptHash>.md, verbatim). Items are parsed from the prompt the model
actually received; each item is labelled by what it carries — its Resultado
(funcionou / FALHOU / não verificado) or, when it has none, its Natureza
(observação / pendente). No gold anchors exist for these slices, so A3 lines are absent.
"""
import hashlib, json, re, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import guardian_synthesis_bench as gb

CB = Path("/home/brenoperucchi/Devs/claude-bridge")
LOT = CB / "guardian/aval" / (sys.argv[1] if len(sys.argv) > 1 else "lote-shadow-v1.json")
AN = CB / ".herdr/guardian/analyses"
CAMP = Path(__file__).resolve().parents[1] / "results" / (sys.argv[2] if len(sys.argv) > 2 else "guardian-shadow-lote-v1")
ITEM = re.compile(r"^### (\d{2}/\d{2} \d{2}:\d{2})[^\n]*\n(.*?)(?=^### |\Z)", re.S | re.M)


def items_from_prompt(p: str):
    body = p.split("## Cronologia", 1)[1]
    out = []
    for n, m in enumerate(ITEM.finditer(body)):
        stamp, blk = m.group(1), m.group(2)
        texto = " ".join(l.strip() for l in blk.split("\n- **")[0].strip().splitlines() if l.strip())
        res = re.search(r"- \*\*Resultado:\*\* ([^\n]+)", blk)
        nat = re.search(r"- \*\*Natureza:\*\* (\w+)", blk)
        pq = re.search(r"- \*\*Por quê:\*\* ([^\n]+)", blk)
        r = res.group(1).strip() if res else None
        rot = {"funcionou": "funcionou", "FALHOU": "falhou", "falhou": "falhou", "não verificado": "nao_verificado"}.get(r, None)
        out.append({"n": n, "stamp": stamp, "texto": texto, "porque": pq.group(1).strip() if pq else None,
                    "resultado": rot or (nat.group(1).lower() if nat else "sem_rotulo")})
    return out


LBL = {"funcionou": "funcionou", "falhou": "FALHOU", "nao_verificado": "não verificado",
       "observação": "observação", "observacao": "observação", "pendente": "pendente"}


def fix_annex(path, items):
    """The shared writer labels anything not funcionou/falhou as 'não verificado'; items
    that only carry a Natureza must keep their own label (same fix applied to V1)."""
    head, annex = path.read_text().split("## Anexo", 1)
    pre = annex.split("\n- `", 1)[0]
    lines = []
    for e in items:
        lines.append(f"- `{e['stamp']}` **[{LBL.get(e['resultado'], e['resultado'])}]** {e['texto']}")
        if e.get("porque"):
            lines.append(f"    - _por quê:_ {e['porque']}")
    path.write_text(head + "## Anexo" + pre + "\n" + "\n".join(lines) + "\n")


def main():
    lot = json.load(open(LOT))
    (CAMP / "checklists").mkdir(parents=True, exist_ok=True)
    rows = []
    for t in [t for t in lot["tentativas"] if t["status"] == "coletado"]:
        a = json.load(open(AN / f"{t['sombra']}.json"))
        assert a["variant"] == "v3-compact" and a["shadowOf"] == t["producao"]
        prompt = (AN / "prompts" / f"{a['promptHash']}.md").read_text()
        items = items_from_prompt(prompt)
        gold = {"items": items}
        run = {"arm": "v3-compact", "variant": "base", "snapshot": f"{a['project']}~{a['subject']}~{a['sliceHash']}",
               "model": a["model"], "sampling": {"id": a["id"]}, "repeat": 0, "content": a["text"],
               "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
               "prompt_sha256_12": hashlib.sha256(prompt.encode()).hexdigest()[:12], "_path": f"{a['id']}.json"}
        gb._write_checklist(CAMP, run, gold, a["text"], None)
        bid = gb._blind_id(run, CAMP)
        fix_annex(CAMP / "checklists" / f"{bid}.md", items)
        rows.append({"blind": bid, "id": a["id"], "producao": t["producao"], "sliceHash": a["sliceHash"],
                     "projeto": a["project"], "itens": len(items),
                     "nao_verificado": sum(i["resultado"] == "nao_verificado" for i in items),
                     "finish": a["finishReason"], "outputTokens": a.get("outputTokens")})
    json.dump(rows, open(CAMP / "lote.json", "w"), ensure_ascii=False, indent=1)
    print(len(rows), "formulários;", sum(r["itens"] for r in rows), "itens;", [ (r["projeto"][:10], r["itens"], r["nao_verificado"]) for r in rows])


if __name__ == "__main__":
    main()
