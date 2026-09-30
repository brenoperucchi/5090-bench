#!/usr/bin/env python3
"""Technical probe for the TypeSafe Jev System-One endpoint.

Validates the *path*, not the content: authentication, request/response shape,
per-call latency, per-call cost, and behaviour under error and timeout. The
question set for the Guardian's pending/resolution work is deliberately out of
scope — the ontology is being reworked on the claude-bridge side.

⚠️ The API key is read from the environment and is never written anywhere: not
to a result file, not to a filename, not to a URL, not to a log line. The
records this writes carry only the key's length, so a reader can tell *which*
credential shape was used without the credential leaking into the repo.
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ENDPOINT = "https://api.typesafe.ai/v1/systemone"
DEFAULT_MODEL = "jev-latest"

# The reference case claude-bridge already ran, kept verbatim so a drift in the
# service shows up as a difference against a known-good answer.
REFERENCE_STATE = (
    "PENDÊNCIA (21/09 17:15): Resolver o warmup do MN1 agora ou seguir para a Fase 4.\n"
    "ITEM POSTERIOR (21/09 20:29): O warmup MN1 passou de degraded para clean."
)
REFERENCE_QUESTIONS = {
    "resolve": {
        "type": "noul",
        "instructions": "O item posterior resolve a pendência descrita?",
    },
    "natureza": {
        "type": "choice",
        "instructions": "Qual a natureza do ITEM POSTERIOR?",
        "criteria": {
            "acao": "algo que foi executado",
            "constatacao": "algo que foi observado ou constatado",
            "intencao": "algo que se pretende fazer",
        },
    },
}
REFERENCE_EXPECTED = {"resolve_noul": 0.75, "natureza_choice": "constatacao", "natureza_confidence": 0.86}


def api_key() -> str:
    key = os.environ.get("TYPESAFE_API_KEY", "").strip()
    if not key:
        raise SystemExit(
            "TYPESAFE_API_KEY ausente. Carregue com:\n"
            "  set -a; . ~/.config/secrets/typesafe.env; set +a"
        )
    return key


def call(state: str, questions: dict[str, Any], *, model: str = DEFAULT_MODEL,
         timeout: float = 30.0, key: str | None = None) -> dict[str, Any]:
    """One request. Returns a record with timing and outcome, never the key."""
    payload = {"model": model, "state": state, "questions": questions}
    req = urllib.request.Request(
        ENDPOINT,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {key or api_key()}",
            "Content-Type": "application/json",
        },
    )
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body = json.loads(r.read().decode("utf-8"))
            return {"ok": True, "status": r.status, "latency_s": round(time.perf_counter() - t0, 3),
                    "body": body}
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:600]
        return {"ok": False, "status": e.code, "latency_s": round(time.perf_counter() - t0, 3),
                "error": "http", "detail": detail}
    except TimeoutError:
        return {"ok": False, "status": None, "latency_s": round(time.perf_counter() - t0, 3),
                "error": "timeout"}
    except urllib.error.URLError as e:
        return {"ok": False, "status": None, "latency_s": round(time.perf_counter() - t0, 3),
                "error": "url", "detail": str(e.reason)[:300]}


def usd_cost(usage: dict[str, Any] | None) -> float | None:
    """Cost implied by the estimate claude-bridge measured: US$0.0105 for 780
    boolean questions. Recorded as *derived*, never as a billed figure — the
    service's real price list is not in hand."""
    if not usage:
        return None
    return round(0.0105 / 780, 8)


def cmd_probe(a: argparse.Namespace) -> int:
    key = api_key()
    out: dict[str, Any] = {
        "schema": "jev-technical-probe-v1",
        "endpoint": ENDPOINT,
        "model_requested": a.model,
        "started_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "api_key_length": len(key),
        "note": "sonda técnica: autenticação, formato, latência, custo e erro. "
                "Não mede qualidade de decisão e não usa o conjunto de perguntas do Guardian.",
        "steps": {},
    }

    print("1. caso de referência (o mesmo que o claude-bridge rodou)")
    ref = call(REFERENCE_STATE, REFERENCE_QUESTIONS, model=a.model, key=key)
    out["steps"]["reference"] = _strip(ref)
    if ref["ok"]:
        ans = ref["body"].get("answers", {})
        got = {
            "resolve_noul": (ans.get("resolve") or {}).get("noul"),
            "natureza_choice": (ans.get("natureza") or {}).get("choice"),
            "natureza_confidence": (ans.get("natureza") or {}).get("confidence"),
        }
        out["steps"]["reference"]["expected"] = REFERENCE_EXPECTED
        out["steps"]["reference"]["got"] = got
        out["steps"]["reference"]["matches"] = {
            k: (got.get(k) == v) for k, v in REFERENCE_EXPECTED.items()
        }
        print(f"   http={ref['status']} {ref['latency_s']}s · modelo={ref['body'].get('model')}")
        for k, v in REFERENCE_EXPECTED.items():
            print(f"     {k:22} esperado={v!r:16} obtido={got.get(k)!r}")
        print(f"   usage: {ref['body'].get('usage')}")
    else:
        print(f"   FALHOU http={ref['status']} {ref.get('error')}: {str(ref.get('detail'))[:200]}")
        write_json(a, out)
        return 1

    print(f"\n2. latência em {a.repeats} chamadas booleanas simples")
    lats, usages = [], []
    one = {"resolve": REFERENCE_QUESTIONS["resolve"]}
    for i in range(a.repeats):
        r = call(REFERENCE_STATE, one, model=a.model, key=key)
        if r["ok"]:
            lats.append(r["latency_s"])
            usages.append(r["body"].get("usage"))
        else:
            print(f"   chamada {i}: FALHOU {r.get('error')} http={r['status']}")
    if lats:
        lats.sort()
        out["steps"]["latency"] = {
            "n": len(lats), "min_s": lats[0], "median_s": statistics.median(lats), "max_s": lats[-1],
            "usage_amostra": usages[0],
        }
        print(f"   n={len(lats)} min={lats[0]}s mediana={statistics.median(lats)}s max={lats[-1]}s")
        print(f"   usage (1 pergunta booleana): {usages[0]}")

    print("\n3. comportamento em erro — credencial inválida")
    bad = call(REFERENCE_STATE, one, model=a.model, key="ap" + "0" * 105)
    out["steps"]["bad_credential"] = _strip(bad)
    print(f"   http={bad['status']} {bad['latency_s']}s erro={bad.get('error')} "
          f"detalhe={str(bad.get('detail'))[:120]}")

    print("\n4. comportamento em erro — payload malformado (tipo inexistente)")
    malformed = call(REFERENCE_STATE, {"q": {"type": "nao_existe", "instructions": "x"}},
                     model=a.model, key=key)
    out["steps"]["malformed"] = _strip(malformed)
    print(f"   http={malformed['status']} erro={malformed.get('error')} "
          f"detalhe={str(malformed.get('detail'))[:160]}")

    print("\n5. comportamento em timeout — deadline de 0,001 s")
    to = call(REFERENCE_STATE, one, model=a.model, timeout=0.001, key=key)
    out["steps"]["timeout"] = _strip(to)
    print(f"   erro={to.get('error')} após {to['latency_s']}s")

    if lats and usages and usages[0]:
        per = usd_cost(usages[0])
        out["steps"]["cost"] = {
            "usd_por_pergunta_booleana_derivado": per,
            "base": "US$0,0105 / 780 perguntas, estimativa do claude-bridge",
            "input_tokens": usages[0].get("input_tokens"),
            "output_tokens": usages[0].get("output_tokens"),
            "aviso": "valor DERIVADO da estimativa recebida, não uma tarifa confirmada pelo fornecedor",
        }
        print(f"\n6. custo derivado: US$ {per} por pergunta booleana "
              f"(≈ US$ {round(per * 780, 5)} para 780)")

    write_json(a, out)
    return 0


def _strip(record: dict[str, Any]) -> dict[str, Any]:
    """Never persist anything that could carry a credential."""
    safe = {k: v for k, v in record.items() if k != "body"}
    if "body" in record:
        b = record["body"]
        safe["body"] = {"model": b.get("model"), "answers": b.get("answers"), "usage": b.get("usage")}
    return safe


def write_json(a: argparse.Namespace, out: dict[str, Any]) -> None:
    path = Path(a.out)
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(out, ensure_ascii=False, indent=2)
    key = os.environ.get("TYPESAFE_API_KEY", "")
    if key and key in text:  # belt and braces: refuse to write a leaked key
        raise SystemExit("ABORTADO: a chave apareceria no arquivo de resultado")
    path.write_text(text + "\n", encoding="utf-8")
    print(f"\nescrito: {path.relative_to(ROOT) if path.is_absolute() else path}")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--model", default=DEFAULT_MODEL)
    p.add_argument("--repeats", type=int, default=5)
    p.add_argument("--out", default=str(ROOT / "results/jev-technical-probe-20260922.json"))
    return cmd_probe(p.parse_args(argv))


if __name__ == "__main__":
    sys.exit(main())
