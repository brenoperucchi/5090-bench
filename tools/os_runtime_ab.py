#!/usr/bin/env python3
"""Same model, same llama.cpp tag, same GGUF bytes: Windows native vs WSL.

The metric is the SERVER's own `timings` (prompt_ms / predicted_ms), not the
client wall clock: the WSL server is reached through an SSH tunnel and the
Windows one directly over the LAN, so client-side latency would measure the
network path, not the operating system. Wall clock is recorded as secondary.

Every call is persisted. The run refuses to start unless the server reports
the expected model file and the context size, so two runs cannot silently
compare different configurations.
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
SNAPS = {
    "curto": None,  # synthetic short prompt
    "medio": ROOT / "results/guardian-synthesis-20260921/snapshots/mfc-exec~MT5~d77e0f52583f.prompt.md",
    "longo": ROOT / "results/guardian-synthesis-20260921/snapshots/mfc-exec~Ryzen9+container~10a626094215.prompt.md",
}
SHORT = "Explique em três frases o que é um contêiner de software."


def get(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=15) as r:
        return json.loads(r.read().decode("utf-8"))


def call(base: str, prompt: str, max_tokens: int) -> dict:
    body = {"messages": [{"role": "user", "content": prompt}], "temperature": 0, "seed": 42,
            "max_tokens": max_tokens, "cache_prompt": False,
            "chat_template_kwargs": {"enable_thinking": False}}
    req = urllib.request.Request(base + "/v1/chat/completions", data=json.dumps(body, ensure_ascii=False).encode(),
                                 headers={"Content-Type": "application/json"})
    t0 = time.perf_counter()
    with urllib.request.urlopen(req, timeout=900) as r:
        d = json.loads(r.read().decode("utf-8"))
    return {"wall_s": round(time.perf_counter() - t0, 4), "timings": d.get("timings"), "usage": d.get("usage"),
            "finish_reason": d["choices"][0].get("finish_reason"),
            "content_sha256": hashlib.sha256((d["choices"][0]["message"].get("content") or "").encode()).hexdigest()}


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--label", required=True, help="windows | wsl")
    p.add_argument("--base", required=True, help="ex.: http://192.168.0.125:18197")
    p.add_argument("--expect-model-sha", default="f5f1dd8920d417aac2718b0bda3403da274301efdd6760b4f0f4b864ff2ad57d")
    p.add_argument("--expect-path", default=None, help="fragmento exato do caminho do modelo (substitui o sha)")
    p.add_argument("--repeats", type=int, default=3)
    p.add_argument("--max-tokens", type=int, default=256)
    p.add_argument("--out", required=True)
    a = p.parse_args()
    out = Path(a.out)
    if out.exists():
        raise SystemExit(f"recuso sobrescrever {out}")
    props = get(a.base + "/props")
    path = props.get("model_path") or ""
    n_ctx = (props.get("default_generation_settings") or {}).get("n_ctx")
    if (a.expect_path and a.expect_path not in path) or (not a.expect_path and a.expect_model_sha[:16] not in path.replace("-", "")):
        raise SystemExit(f"modelo inesperado: {path}")
    print(f"{a.label}: model={path[-40:]} n_ctx={n_ctx} build={props.get('build_info')} slots={props.get('total_slots')}")
    warm = call(a.base, SHORT, 8)  # load kernels; not measured
    calls = []
    for rep in range(1, a.repeats + 1):
        for size, src in SNAPS.items():
            prompt = SHORT if src is None else src.read_text(encoding="utf-8")
            r = call(a.base, prompt, a.max_tokens)
            t = r["timings"] or {}
            rec = {"label": a.label, "repeticao": rep, "tamanho": size,
                   "timestamp": datetime.now().astimezone().isoformat(timespec="milliseconds"),
                   "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(), **r}
            calls.append(rec)
            print(f"  rep{rep} {size:5} prompt_n={t.get('prompt_n')} pp={t.get('prompt_per_second', 0):8.1f} t/s "
                  f"gen_n={t.get('predicted_n')} tg={t.get('predicted_per_second', 0):6.1f} t/s wall={r['wall_s']}s")
    agg = {}
    for size in SNAPS:
        v = [c["timings"] for c in calls if c["tamanho"] == size and c["timings"]]
        agg[size] = {"pp_tps_mediana": statistics.median(x["prompt_per_second"] for x in v),
                     "tg_tps_mediana": statistics.median(x["predicted_per_second"] for x in v),
                     "prompt_n": v[0]["prompt_n"]}
    doc = {"schema": "os-runtime-ab-v1", "label": a.label, "base": a.base, "props": {
        "model_path": path, "n_ctx": n_ctx, "build_info": props.get("build_info"),
        "total_slots": props.get("total_slots")}, "aquecimento": warm, "chamadas": calls, "derivados": agg,
        "metrica_principal": "timings do servidor (prompt_per_second, predicted_per_second); wall clock é secundário"}
    out.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(agg, indent=2)); print(f"escrito: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
