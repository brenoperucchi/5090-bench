#!/usr/bin/env python3
"""Evaluate typed-decision models against the owner's labelled typification batch.

⚠️ **Accuracy is meaningless on this batch and is never the headline.** With one
positive in twenty and one in seven, a model that always answers "no" scores 95%
and 86%. Every arm is therefore reported against the trivial "always no"
baseline, and a run with high accuracy and zero recall is labelled a failure in
so many words.

Two views are reported because a fixed threshold is brittle at n=2 positives:

* **threshold view** — recall, precision and the confusion matrix at 0.5, which
  is what a deployed rule would do;
* **ranking view** — where the true positive lands when cases are sorted by
  score. This does not depend on a threshold, so it separates "the model cannot
  see the difference" from "the model sees it but 0.5 is the wrong cut".
"""

from __future__ import annotations

import argparse
import json
import statistics
import subprocess
import sys
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
BATCH = Path("/home/brenoperucchi/Devs/claude-bridge/guardian/aval/lote-tipificacao.json")
HOST = "192.168.0.125"
# Overridable so a new checkpoint/package can be measured without touching the 22/09 setup.
LAYA_VENV = __import__("os").environ.get("LAYA_VENV", "/home/brenoperucchi/laya-venv")
LAYA_MODEL = __import__("os").environ.get("LAYA_MODEL", "convaiinnovations/laya-multilingual")

ADVERSARIAL = {
    "ace:mfc-exec:2026-09-21T20:15:17.000Z:2026-09-21T20:14:23.000Z": "diagnóstico (menciona MN1)",
    "rej:mfc-exec:2026-09-21T20:28:43.000Z:2026-09-21T20:14:23.000Z": "encerra (não menciona MN1)",
}


# --------------------------------------------------------------------- arms

def arm_trivial(cases: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The ruler. Always "no" — whatever an arm scores, it must beat this."""
    return [{"id": c["id"], "score": 0.0, "confidence": None, "latency_s": 0.0} for c in cases]


def arm_laya(cases: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Runs on the GPU host inside its own venv; returns one score per case."""
    payload = json.dumps([{"id": c["id"], "state": c["state"],
                           "instructions": c["instructions"], "criteria": c["criteria"]}
                          for c in cases], ensure_ascii=False)
    script = f'''
import json, sys, time, torch, laya
cases = json.load(sys.stdin)
agent = laya.load({LAYA_MODEL!r})
agent.predict({{"x": "aquecimento"}}, {{"q": {{"type": "noul", "instructions": "teste"}}}})
out = []
for c in cases:
    t0 = time.perf_counter()
    r = agent.predict({{"contexto": c["state"]}},
                      {{"q": {{"type": "noul", "instructions": c["instructions"],
                               "criteria": c["criteria"]}}}})
    torch.cuda.synchronize()
    a = r["answers"]["q"]
    out.append({{"id": c["id"], "score": a.get("noul"), "confidence": a.get("confidence"),
                 "latency_s": round(time.perf_counter() - t0, 4)}})
print("@@JSON@@" + json.dumps(out, ensure_ascii=False))
'''
    # The script travels base64-encoded: inline quoting through ssh+bash+python
    # mangles newlines and backslashes, and the failure is a confusing SyntaxError.
    import base64
    b64 = base64.b64encode(script.encode()).decode()
    remote = (f"source {LAYA_VENV}/bin/activate && "
              f"printf %s {b64} | base64 -d > /tmp/_laya_arm.py && python /tmp/_laya_arm.py")
    cmd = ["ssh", "-o", "BatchMode=yes", HOST, remote]
    p = subprocess.run(cmd, input=payload, capture_output=True, text=True, timeout=900)
    marker = "@@JSON@@"
    if marker not in p.stdout:
        raise SystemExit(f"laya falhou:\n{p.stdout[-800:]}\n{p.stderr[-800:]}")
    return json.loads(p.stdout.split(marker, 1)[1].strip())


def arm_jev(cases: list[dict[str, Any]]) -> list[dict[str, Any]]:
    import os
    import time
    # SYSTEMONE_URL points the same arm at any TypeSafe-compatible server (e.g. a local
    # Eikos); the hosted Jev is the default and the only one that needs the key.
    url = os.environ.get("SYSTEMONE_URL", "https://api.typesafe.ai/v1/systemone")
    key = os.environ.get("TYPESAFE_API_KEY", "").strip()
    if not key and "typesafe.ai" in url:
        raise SystemExit("TYPESAFE_API_KEY ausente (set -a; . ~/.config/secrets/typesafe.env; set +a)")
    out = []
    for c in cases:
        body = {"model": "jev-latest", "state": c["state"],
                "questions": {"q": {"type": "noul", "instructions": c["instructions"],
                                    "criteria": c["criteria"]}}}
        req = urllib.request.Request(
            url, data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
            headers={"Authorization": f"Bearer {key or 'local'}", "Content-Type": "application/json"})
        t0 = time.perf_counter()
        with urllib.request.urlopen(req, timeout=60) as r:
            d = json.loads(r.read().decode("utf-8"))
        a = d.get("answers", {}).get("q", {})
        out.append({"id": c["id"], "score": a.get("noul"), "confidence": a.get("confidence"),
                    "latency_s": round(time.perf_counter() - t0, 4), "usage": d.get("usage")})
    return out


def arm_qwen(cases: list[dict[str, Any]], endpoint: str) -> list[dict[str, Any]]:
    """The big local model, asked for a single letter so the answer is parseable."""
    import time
    out = []
    for c in cases:
        prompt = (f"{c['instructions']}\n\n"
                  f"A = {c['criteria']['true']}\n"
                  f"B = {c['criteria']['false']}\n\n"
                  f"{c['state']}\n\n"
                  "Responda apenas com a letra A ou B.")
        body = {"model": "qwen3-coder-30b", "messages": [{"role": "user", "content": prompt}],
                "temperature": 0, "max_tokens": 2, "logprobs": True, "top_logprobs": 5}
        req = urllib.request.Request(endpoint, data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
                                     headers={"Content-Type": "application/json"})
        t0 = time.perf_counter()
        with urllib.request.urlopen(req, timeout=120) as r:
            d = json.loads(r.read().decode("utf-8"))
        ch = d["choices"][0]
        txt = (ch["message"].get("content") or "").strip().upper()
        score = 1.0 if txt.startswith("A") else 0.0
        conf = None
        try:  # turn the A/B logprobs into a probability, when the server gives them
            import math
            tops = ch["logprobs"]["content"][0]["top_logprobs"]
            pa = sum(math.exp(t["logprob"]) for t in tops if t["token"].strip().upper().startswith("A"))
            pb = sum(math.exp(t["logprob"]) for t in tops if t["token"].strip().upper().startswith("B"))
            if pa + pb > 0:
                score = pa / (pa + pb)
                conf = max(pa, pb) / (pa + pb)
        except Exception:  # noqa: BLE001 — logprobs are a bonus, not the measurement
            pass
        out.append({"id": c["id"], "score": score, "confidence": conf,
                    "latency_s": round(time.perf_counter() - t0, 4)})
    return out


# --------------------------------------------------------------------- metrics

def evaluate(cases: list[dict[str, Any]], preds: list[dict[str, Any]], threshold: float) -> dict[str, Any]:
    gold = {c["id"]: bool(c["gold"]) for c in cases}
    tipo = {c["id"]: c["tipo"] for c in cases}
    by_id = {p["id"]: p for p in preds}
    out: dict[str, Any] = {"threshold": threshold, "por_pergunta": {}}

    for t in sorted({c["tipo"] for c in cases}):
        ids = [c["id"] for c in cases if c["tipo"] == t]
        tp = fp = fn = tn = 0
        for i in ids:
            s = by_id.get(i, {}).get("score")
            pred = (s is not None) and (s >= threshold)
            if gold[i] and pred:
                tp += 1
            elif gold[i] and not pred:
                fn += 1
            elif not gold[i] and pred:
                fp += 1
            else:
                tn += 1
        n, pos = len(ids), sum(1 for i in ids if gold[i])
        recall = tp / pos if pos else None
        precision = tp / (tp + fp) if (tp + fp) else None
        # Ranking: where does the true positive land, sorted by score descending?
        def sc(i: str) -> float:
            v = by_id.get(i, {}).get("score")
            return -1.0 if v is None else float(v)
        # Ties must be reported, not broken arbitrarily: a positive that shares its
        # score with a negative is NOT ranked above it, and no threshold separates
        # them. Average rank is used so a tie cannot look like an ordering.
        pos_ranks = []
        for i in ids:
            if not gold[i]:
                continue
            v = sc(i)
            melhores = sum(1 for j in ids if sc(j) > v)
            empatados = [j for j in ids if sc(j) == v and j != i]
            emp_neg = sum(1 for j in empatados if not gold[j])
            pos_ranks.append({
                "rank_medio": melhores + 1 + len(empatados) / 2,
                "estritamente_acima": melhores,
                "empatado_com": len(empatados),
                "empatado_com_negativos": emp_neg,
                "separavel_por_limiar": emp_neg == 0,
                "score": v,
            })
        out["por_pergunta"][t] = {
            "n": n, "positivos": pos,
            "tp": tp, "fp": fp, "fn": fn, "tn": tn,
            "recall_positivo": recall, "precisao": precision,
            "accuracy": round((tp + tn) / n, 4),
            "accuracy_baseline_sempre_nao": round((n - pos) / n, 4),
            "rank_do_positivo": pos_ranks,
            "algum_positivo_inseparavel": any(not r["separavel_por_limiar"] for r in pos_ranks),
        }
    # Calibration: is it as confident when wrong as when right?
    # ⚠️ NÃO é calibração, e não é comparável entre modelos se as fontes diferirem.
    # A MESMA transformação é aplicada a todos os braços — margem = |2*score - 1| —
    # para que a comparação seja entre grandezas iguais. O `confidence` que o modelo
    # reporta fica registrado à parte, nunca misturado com a margem derivada.
    acertos, erros = [], []
    conf_proprio = {"acertos": [], "erros": []}
    for c in cases:
        p = by_id.get(c["id"], {})
        s = p.get("score")
        if s is None:
            continue
        correto = (s >= threshold) == bool(c["gold"])
        margem = abs(2 * float(s) - 1)
        (acertos if correto else erros).append(margem)
        if p.get("confidence") is not None:
            conf_proprio["acertos" if correto else "erros"].append(p["confidence"])
    med = lambda v: round(statistics.mean(v), 4) if v else None
    out["margem"] = {
        "definicao": "margem = |2*score - 1|, derivada do score; MESMA fórmula em todos os braços",
        "nao_e_calibracao": "nenhum ECE foi medido neste corpus; com 2 positivos não há binning possível",
        "margem_media_acertos": med(acertos), "margem_media_erros": med(erros),
        "n_acertos": len(acertos), "n_erros": len(erros),
    }
    out["confidence_do_modelo"] = {
        "disponivel": bool(conf_proprio["acertos"] or conf_proprio["erros"]),
        "media_acertos": med(conf_proprio["acertos"]), "media_erros": med(conf_proprio["erros"]),
        "aviso": "campo próprio do modelo; NÃO comparável com braço que não o reporta",
    }
    lat = [p["latency_s"] for p in preds if p.get("latency_s") is not None]
    out["latencia_s"] = {"mediana": round(statistics.median(lat), 4), "total": round(sum(lat), 2)} if lat else None

    # ⚠️ Estrato de evidência: um caso cujo desfecho exige conhecimento que NÃO está
    # em nenhum item da cronologia não mede a mesma coisa que os demais. Ali,
    # abster-se é defensável e acertar é sorte — medir os dois juntos pune a
    # abstenção justificada e premia o palpite (owner, 2026-09-22 16:22).
    ctx = {c["id"]: c.get("contexto_necessario_disponivel") for c in cases}
    grupos: dict[str, Any] = {}
    for rot, sel in (("contexto_disponivel", True), ("contexto_ausente", False), ("nao_rotulado", None)):
        ids = [c["id"] for c in cases if ctx.get(c["id"]) is sel]
        if not ids:
            continue
        pos = [i for i in ids if gold[i]]
        tp = sum(1 for i in pos if (by_id.get(i, {}).get("score") or 0) >= threshold)
        fp = sum(1 for i in ids if not gold[i] and (by_id.get(i, {}).get("score") or 0) >= threshold)
        grupos[rot] = {"n": len(ids), "positivos": len(pos), "tp": tp, "fp": fp,
                       "recall_positivo": (tp / len(pos)) if pos else None}
    out["por_disponibilidade_de_contexto"] = grupos or {
        "aviso": "nenhum caso traz `contexto_necessario_disponivel`; métricas não estratificadas"}

    out["par_adversarial"] = {
        i: {"papel": papel, "gold": gold.get(i), "score": by_id.get(i, {}).get("score"),
            "predito": (by_id.get(i, {}).get("score") or 0) >= threshold,
            "acertou": ((by_id.get(i, {}).get("score") or 0) >= threshold) == gold.get(i)}
        for i, papel in ADVERSARIAL.items() if i in gold
    }
    out["par_adversarial_ambos_certos"] = all(v["acertou"] for v in out["par_adversarial"].values())
    return out


def verdict(res: dict[str, Any]) -> list[str]:
    """Say plainly when a high accuracy is hiding a total miss."""
    notes = []
    for t, m in res["por_pergunta"].items():
        if m["positivos"] and m["recall_positivo"] == 0:
            notes.append(
                f"⚠️ {t}: accuracy {m['accuracy']:.0%} com recall ZERO — não achou nenhum dos "
                f"{m['positivos']} positivo(s). Isto é FRACASSO, não sucesso: a baseline trivial "
                f"'sempre não' faz {m['accuracy_baseline_sempre_nao']:.0%} sem modelo nenhum.")
        elif m["accuracy"] <= m["accuracy_baseline_sempre_nao"] and m["recall_positivo"]:
            notes.append(f"{t}: achou o positivo, mas a accuracy ({m['accuracy']:.0%}) não supera a "
                         f"baseline trivial ({m['accuracy_baseline_sempre_nao']:.0%}) — pagou em falsos positivos.")
    m = res["margem"]
    if m["margem_media_erros"] is not None and m["margem_media_acertos"] is not None:
        if m["margem_media_erros"] >= m["margem_media_acertos"]:
            notes.append("⚠️ margem: a margem média nos ERROS é igual ou maior que nos acertos — o score "
                         "não separa o que o modelo acerta do que erra. (Margem, não calibração: "
                         "nenhum ECE foi medido aqui.)")
    for t, mm in res["por_pergunta"].items():
        if mm.get("algum_positivo_inseparavel"):
            notes.append(f"⚠️ {t}: o positivo EMPATA em score com ao menos um negativo — nenhum limiar "
                         f"separa o estrato. O rank não é ordenação, é desempate arbitrário.")
        if mm["precisao"] is not None and mm["recall_positivo"] and mm["precisao"] < 0.2:
            notes.append(f"{t}: recall {mm['recall_positivo']:.0%} é REAL — os positivos foram achados. "
                         f"O problema é a PRECISÃO ({mm['precisao']:.2f}): {mm['fp']} falsos positivos.")
    return notes



# --------------------------------------------------------------------- repetições

def run_jev_repeats(cases: list[dict[str, Any]], repeats: int, out_path: Path, batch_path: Path) -> int:
    """Stability measurement: every call is persisted on its own.

    Owner's stated goal: three months from now, be able to tell whether these
    were really equivalent calls. So each record carries the full payload, its
    sha256, the effective parameters, the raw response and the call timestamp.
    Aggregates are derived afterwards and never replace the individual calls.
    No threshold is chosen or tuned from this data.
    """
    import hashlib
    import os
    import time
    # SYSTEMONE_URL points the same arm at any TypeSafe-compatible server (e.g. a local
    # Eikos); the hosted Jev is the default and the only one that needs the key.
    url = os.environ.get("SYSTEMONE_URL", "https://api.typesafe.ai/v1/systemone")
    key = os.environ.get("TYPESAFE_API_KEY", "").strip()
    if not key and "typesafe.ai" in url:
        raise SystemExit("TYPESAFE_API_KEY ausente (set -a; . ~/.config/secrets/typesafe.env; set +a)")
    batch_bytes = batch_path.read_bytes()
    calls: list[dict[str, Any]] = []
    for rep in range(1, repeats + 1):
        for c in cases:
            payload = {"model": "jev-latest", "state": c["state"],
                       "questions": {"q": {"type": "noul", "instructions": c["instructions"],
                                           "criteria": c["criteria"]}}}
            raw_payload = json.dumps(payload, ensure_ascii=False, sort_keys=True)
            rec: dict[str, Any] = {
                "case_id": c["id"], "gold": bool(c["gold"]), "repeticao": rep,
                "timestamp": datetime.now().astimezone().isoformat(timespec="milliseconds"),
                "endpoint": "https://api.typesafe.ai/v1/systemone",
                "parametros_efetivos": {"model": payload["model"], "question_type": "noul",
                                         "question_id": "q", "timeout_s": 60},
                "payload": payload,
                "payload_sha256": hashlib.sha256(raw_payload.encode("utf-8")).hexdigest(),
            }
            req = urllib.request.Request(
                "https://api.typesafe.ai/v1/systemone",
                data=raw_payload.encode("utf-8"),
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
            t0 = time.perf_counter()
            try:
                with urllib.request.urlopen(req, timeout=60) as r:
                    raw = r.read().decode("utf-8")
                body = json.loads(raw)
                a = body.get("answers", {}).get("q", {})
                score = a.get("noul")
                rec.update({
                    "http_status": 200, "latency_s": round(time.perf_counter() - t0, 4),
                    "score": score,
                    "confidence_retornada_pelo_jev": a.get("confidence"),
                    "margem_padronizada": None if score is None else round(abs(2 * float(score) - 1), 6),
                    "model_retornado": body.get("model"), "usage": body.get("usage"),
                    "resposta_bruta": body, "erro": None,
                })
            except urllib.error.HTTPError as e:
                rec.update({"http_status": e.code, "latency_s": round(time.perf_counter() - t0, 4),
                            "score": None, "erro": {"tipo": "http",
                                                    "detalhe": e.read().decode("utf-8", "replace")[:600]}})
            except (TimeoutError, urllib.error.URLError) as e:
                rec.update({"http_status": None, "latency_s": round(time.perf_counter() - t0, 4),
                            "score": None, "erro": {"tipo": "timeout_ou_rede", "detalhe": str(e)[:300]}})
            calls.append(rec)
            print(f"  rep {rep} {c['id'][:34]:34} gold={str(c['gold']):5} score={rec.get('score')}")

    # Derivados — por caso, a partir das chamadas acima; nunca os substituem.
    por_caso: dict[str, Any] = {}
    for c in cases:
        v = [x["score"] for x in calls if x["case_id"] == c["id"] and x["score"] is not None]
        por_caso[c["id"]] = {"gold": bool(c["gold"]), "n": len(v),
                             "media": round(statistics.mean(v), 4) if v else None,
                             "min": min(v) if v else None, "max": max(v) if v else None,
                             "amplitude": round(max(v) - min(v), 4) if v else None}
    pos_min = min((x["score"] for x in calls if x["gold"] and x["score"] is not None), default=None)
    neg_max = max((x["score"] for x in calls if not x["gold"] and x["score"] is not None), default=None)
    for cid, d in por_caso.items():
        if d["gold"] and d["min"] is not None and neg_max is not None:
            d["separavel_por_limiar"] = d["min"] > neg_max
    usage_in = sum((x.get("usage") or {}).get("input_tokens", 0) for x in calls)
    usage_out = sum((x.get("usage") or {}).get("output_tokens", 0) for x in calls)

    doc = {
        "schema": "jev-repeticoes-v1",
        "proposito": "medir a estabilidade da distribuição de scores entre repetições da mesma chamada",
        "nao_e": "otimização de limiar — nenhum limiar foi escolhido ou reajustado a partir destes dados",
        "autorizacao": "owner, 2026-09-22, custo aprovado ~US$0,0004 (28 chamadas)",
        "relacao_com_evidencia_anterior": ("medição NOVA e independente; não substitui a transcrição de tela "
                                           "da sessão anterior (Evidência 2 de H-JEV-JUDGE)"),
        "lote": str(batch_path), "lote_sha256": hashlib.sha256(batch_bytes).hexdigest(),
        "estrato": "encerra", "n_casos": len(cases), "repeticoes": repeats,
        "instrumento": "tools/typification_eval.py --mode jev-repeats",
        "instrumento_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "iniciado_em": calls[0]["timestamp"] if calls else None,
        "terminado_em": calls[-1]["timestamp"] if calls else None,
        "chamadas": calls,
        "derivados": {
            "por_caso": por_caso,
            "positivo_score_minimo": pos_min, "negativo_score_maximo": neg_max,
            "estrato_separavel_em_todas_as_repeticoes": (pos_min is not None and neg_max is not None
                                                        and pos_min > neg_max),
            "usage_total": {"input_tokens": usage_in, "output_tokens": usage_out},
            "erros": sum(1 for x in calls if x.get("erro")),
        },
    }
    text = json.dumps(doc, ensure_ascii=False, indent=2)
    if key and key in text:
        raise SystemExit("ABORTADO: a chave apareceria no arquivo")
    if out_path.exists():
        raise SystemExit(f"recuso sobrescrever {out_path}")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(text + "\n", encoding="utf-8")
    print(f"\nescrito: {out_path}")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--batch", default=str(BATCH))
    p.add_argument("--arm", action="append", choices=["trivial", "laya", "jev", "qwen"], default=None)
    p.add_argument("--threshold", type=float, default=0.5)
    p.add_argument("--qwen-endpoint", default="http://127.0.0.1:18194/v1/chat/completions")
    p.add_argument("--out", default=str(ROOT / "results/tipificacao-20260922.json"))
    p.add_argument("--mode", choices=["compare", "jev-repeats"], default="compare")
    p.add_argument("--repeats", type=int, default=1)
    p.add_argument("--tipo", default=None, help="restringe a um estrato (ex.: encerra)")
    a = p.parse_args(argv)
    if a.mode == "jev-repeats":
        batch = json.loads(Path(a.batch).read_text(encoding="utf-8"))
        cases = [c for c in batch["casos"] if a.tipo is None or c["tipo"] == a.tipo]
        return run_jev_repeats(cases, a.repeats, Path(a.out), Path(a.batch))
    arms = a.arm or ["trivial", "laya", "jev"]

    batch = json.loads(Path(a.batch).read_text(encoding="utf-8"))
    cases = batch["casos"]
    runners: dict[str, Callable[[list[dict[str, Any]]], list[dict[str, Any]]]] = {
        "trivial": arm_trivial, "laya": arm_laya, "jev": arm_jev,
        "qwen": lambda c: arm_qwen(c, a.qwen_endpoint),
    }

    report: dict[str, Any] = {
        "schema": "typification-eval-v1",
        "batch_origem": batch.get("origem"), "batch_gerado": batch.get("geradoEm"),
        "n_casos": len(cases), "positivos": sum(1 for c in cases if c["gold"]),
        "rodado_em": datetime.now().astimezone().isoformat(timespec="seconds"),
        "aviso": "accuracy não é a métrica aqui; leia recall do positivo contra a baseline trivial",
        "bracos": {},
    }
    for name in arms:
        print(f"\n=== {name}")
        try:
            preds = runners[name](cases)
        except Exception as e:  # noqa: BLE001 — one arm failing must not lose the others
            print(f"  FALHOU: {e}")
            report["bracos"][name] = {"erro": str(e)[:400]}
            continue
        res = evaluate(cases, preds, a.threshold)
        res["predicoes"] = preds
        report["bracos"][name] = res
        for t, m in res["por_pergunta"].items():
            print(f"  {t:12} recall={m['recall_positivo']} precisao={m['precisao']} "
                  f"acc={m['accuracy']:.2f} (baseline {m['accuracy_baseline_sempre_nao']:.2f}) "
                  f"rank_do_positivo={m['rank_do_positivo']} de {m['n']}")
        print(f"  par adversarial: ambos certos = {res['par_adversarial_ambos_certos']}")
        for n in verdict(res):
            print(f"  {n}")

    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    import os
    text = json.dumps(report, ensure_ascii=False, indent=2)
    key = os.environ.get("TYPESAFE_API_KEY", "")
    if key and key in text:
        raise SystemExit("ABORTADO: a chave apareceria no arquivo")
    Path(a.out).write_text(text + "\n", encoding="utf-8")
    print(f"\nescrito: {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
