#!/usr/bin/env python3
"""Run the MFC comprehension benchmark through the llm-gateway (OpenRouter route) instead of a local Strata.

The MFC script (`v04_compreensao_autonomo.py`, owned by the MFC project) checks model identity with the Strata
`/props` endpoint, which an OpenRouter route does not have. This adapter imports that script unchanged and only
replaces its `chamar` (one call): same request body plus `user` for the gateway's accounting, and identity taken
from the gateway's `x_gateway` block instead of `/props`:

  valid identity = x_gateway.model_resolved == --caminho-pesos (e.g. "qwen/qwen3.8-flash")
                   and provider_execution.requested_provider == "Alibaba"
                   and provider_execution.reported_provider in ("Alibaba", None)
  reported_provider None  -> answer kept, marked identidade_incerta (same rule the script uses for a /props outage)

Everything else (bank loading, resume, records, grading) is the MFC script's own code.

Usage (same flags as the MFC script; --props is unused but kept so the recorded config stays comparable):
  python3 tools/mfc_bench_gateway_adapter.py --script <path to v04_compreensao_autonomo.py> rodar \
      --banco <bank> --saida <out.jsonl> --url http://127.0.0.1:8080/openai/v1/chat/completions \
      --modelo comprehension-openrouter/openrouter-qwen38-flash-alibaba --props none \
      --caminho-pesos qwen/qwen3.8-flash --repeticoes 3
"""
import importlib.util
import json
import sys
import time
import urllib.error
import urllib.request
import uuid

PROJECT = "llm-bench"


def load(path):
    spec = importlib.util.spec_from_file_location("mfc_bench", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


PAUSE_S = float(__import__("os").environ.get("MFC_GATEWAY_PAUSE_S", "0"))
# The MFC script asks for 800 output tokens. A reasoning arm (e.g. Qwen3.8 Max with mandatory reasoning) counts the
# reasoning in the output budget, so its run raises this; the default keeps the MFC request unchanged.
MAX_TOKENS = int(__import__("os").environ.get("MFC_GATEWAY_MAX_TOKENS", "800"))
# On this route a gateway 502 is an upstream failure; on 2026-10-01 its diagnostic showed them to be OpenRouter
# rate limits (upstream 429, openrouter_rate_limited). Retry the same call after growing waits.
BACKOFF_S = (20, 40, 80, 160)


def make_chamar():
    def chamar(url, modelo, prompt, props, caminho):
        r = None
        for wait in (0,) + BACKOFF_S:
            if wait:
                print(f"  502 do provedor (limite de taxa provável): espera {wait}s", flush=True)
                time.sleep(wait)
            time.sleep(PAUSE_S)
            r = _uma(url, modelo, prompt, caminho)
            if r["http"] != 502:
                break
        return r
    return chamar


THINKING = __import__("os").environ.get("MFC_THINKING", "0") == "1"
REASONING_BUDGET = int(__import__("os").environ.get("MFC_REASONING_BUDGET", "0"))


def _get_props(url):
    try:
        k = __import__("os").environ.get("STRATA_API_KEY", "").strip()   # 0.1.40+: /props exige a chave
        req = urllib.request.Request(url, headers={"Authorization": f"Bearer {k}"} if k else {})
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read().decode())
    except Exception as ex:  # noqa: BLE001 - /props outage, same rule as the MFC script
        return {"erro": repr(ex)[:200]}


def make_chamar_strata():
    """Local Strata with thinking ON (MFC_THINKING=1); identity by /props model_path, as in the MFC script."""
    def chamar(url, modelo, prompt, props, caminho):
        pa = _get_props(props)
        corpo = {"model": modelo,
                 "messages": [{"role": "system", "content": "Return only JSON as the consumer contract asks."},
                              {"role": "user", "content": prompt}],
                 "temperature": 0, "seed": 42, "max_tokens": MAX_TOKENS, "stream": False,
                 "chat_template_kwargs": {"enable_thinking": THINKING}}
        if REASONING_BUDGET:
            corpo["reasoning_budget_tokens"] = REASONING_BUDGET
        t0, http, b, erro = time.time(), None, None, None
        try:
            k = __import__("os").environ.get("STRATA_API_KEY", "").strip()   # nunca impressa nem gravada
            req = urllib.request.Request(url, data=json.dumps(corpo).encode(),
                                         headers={"Content-Type": "application/json",
                                                  "X-Request-ID": str(uuid.uuid4()),
                                                  **({"Authorization": f"Bearer {k}"} if k else {})})
            with urllib.request.urlopen(req, timeout=900) as r:
                http, b = r.status, json.loads(r.read().decode())
        except urllib.error.HTTPError as ex:
            http, erro = ex.code, ex.read().decode(errors="replace")[:500]
        except Exception as ex:  # noqa: BLE001
            erro = repr(ex)[:300]
        pd_ = _get_props(props)
        ch = ((b or {}).get("choices") or [{}])[0]
        msg = ch.get("message") or {}
        txt, fim = msg.get("content") or "", ch.get("finish_reason")
        fora = [p for p in (pa, pd_) if "erro" in p]
        ident = all(p.get("model_path") == caminho for p in (pa, pd_) if "erro" not in p)
        motivo = ("http " + str(http) if http != 200 else "finish " + str(fim) if fim != "stop" else
                  "tool_calls" if msg.get("tool_calls") else "sem texto" if not txt.strip() else
                  "identidade" if not ident else None)
        rc = msg.get("reasoning_content") or msg.get("reasoning") or ""
        return {"valida": motivo is None, "motivo_invalida": motivo, "identidade_incerta": bool(fora) and http == 200,
                "texto": txt, "http": http, "erro": erro, "finish_reason": fim, "uso": (b or {}).get("usage"),
                "props_antes": pa, "props_depois": pd_, "raciocinio_chars": len(rc),
                "latencia_s": round(time.time() - t0, 1)}
    return chamar


def _uma(url, modelo, prompt, caminho):
    """One call through the gateway; identity from x_gateway instead of /props."""
    if True:
        corpo = {"model": modelo, "user": PROJECT,
                 "messages": [{"role": "system", "content": "Return only JSON as the consumer contract asks."},
                              {"role": "user", "content": prompt}],
                 "temperature": 0, "seed": 42, "max_tokens": MAX_TOKENS, "stream": False,
                 "chat_template_kwargs": {"enable_thinking": False}}
        t0, http, b, erro = time.time(), None, None, None
        try:
            req = urllib.request.Request(url, data=json.dumps(corpo).encode(),
                                         headers={"Content-Type": "application/json",
                                                  "X-Request-ID": str(uuid.uuid4())})
            with urllib.request.urlopen(req, timeout=620) as r:
                http, b = r.status, json.loads(r.read().decode())
        except urllib.error.HTTPError as ex:
            http, erro = ex.code, ex.read().decode(errors="replace")[:500]
        except Exception as ex:  # noqa: BLE001 - recorded as transport, retried by the script on resume
            erro = repr(ex)[:300]
        ch = ((b or {}).get("choices") or [{}])[0]
        msg = ch.get("message") or {}
        txt, fim = msg.get("content") or "", ch.get("finish_reason")
        xg = (b or {}).get("x_gateway") or {}
        pe = xg.get("provider_execution") or {}
        reported = pe.get("reported_provider")
        ident = (xg.get("model_resolved") == caminho and pe.get("requested_provider") == "Alibaba"
                 and reported in ("Alibaba", None))
        motivo = ("http " + str(http) if http != 200 else "finish " + str(fim) if fim != "stop" else
                  "tool_calls" if msg.get("tool_calls") else "sem texto" if not txt.strip() else
                  "identidade" if not ident else None)
        return {"valida": motivo is None, "motivo_invalida": motivo,
                "identidade_incerta": http == 200 and ident and reported is None,
                "texto": txt, "http": http, "erro": erro, "finish_reason": fim, "uso": (b or {}).get("usage"),
                "props_antes": {"x_gateway": xg}, "props_depois": {},
                "latencia_s": round(time.time() - t0, 1)}


if __name__ == "__main__":
    if len(sys.argv) < 3 or sys.argv[1] != "--script":
        raise SystemExit(__doc__)
    mod = load(sys.argv[2])
    mod.chamar = make_chamar_strata() if __import__("os").environ.get("MFC_TARGET") == "strata" else make_chamar()
    sys.argv = [sys.argv[2]] + sys.argv[3:]
    import argparse  # noqa: E402 - reuse the MFC script's own CLI
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest="cmd", required=True)
    r = sp.add_parser("rodar")
    for k in ("--banco", "--saida", "--url", "--modelo", "--props", "--caminho-pesos"):
        r.add_argument(k, required=True)
    r.add_argument("--repeticoes", type=int, default=3)
    c = sp.add_parser("corrigir")
    c.add_argument("--banco", required=True)
    c.add_argument("--saida", required=True)
    c.add_argument("--repeticoes", type=int, default=3)
    a = ap.parse_args(sys.argv[1:])
    mod.rodar(a) if a.cmd == "rodar" else mod.corrigir(a)
