#!/usr/bin/env python3
"""Guardian synthesis, prompt `atual`, 5 models on WSL or Windows (argv[1], default wsl).

Same design as the existing qwen38-wsl runs: per snapshot, 1 call at t=0 (seed
42) + 3 at t=0.3 (seeds 42..44); enable_thinking=false; --max-tokens-auto.
Cells already on disk are skipped. Production is always restored at the end.
"""
import json
import subprocess
import sys
from pathlib import Path

import optimization_campaign as oc

ROOT = Path(__file__).resolve().parents[1]
RUNS = ROOT / "results/guardian-synthesis-20260921/runs"
SNAPS = ["mfc-exec~container~36e2a6ef93dc", "mfc-exec~Ryzen9~ff6b18a9aaf6",
         "mfc-exec~MT5~d77e0f52583f", "mfc-exec~Ryzen9+container~10a626094215"]
D = "/mnt/e/llm-bench-t87-runtimes/models/qwen38-35b-apex"
W = r"E:\llm-bench-t87-runtimes\models\qwen38-35b-apex"
OS = sys.argv[1] if len(sys.argv) > 1 else "wsl"
oc.MODELS["apex"] = {"wsl": f"{D}/Qwen3.8-35B-A3B-Distill.APEX-I-MiniPlus-V2.1.gguf",
                     "win": W + r"\Qwen3.8-35B-A3B-Distill.APEX-I-MiniPlus-V2.1.gguf",
                     "frag": "APEX-I-MiniPlus-V2.1.gguf", "mtp": True}
COMMON = "-ub 1024 -b 4096"
NV_MTP = "--spec-type draft-mtp --spec-draft-n-max 2"
AP_MTP = (f"-md {D}/mtp-Qwen3.8-35B-A3B-Distill-Q8_0.gguf {NV_MTP}" if OS == "wsl"
          else f"-md '{W}\\mtp-Qwen3.8-35B-A3B-Distill-Q8_0.gguf' {NV_MTP}")
# (run tag, model key, extra flags) — qwen38-wsl keeps the tag of the existing runs
PLAN = [(f"qwen38-{OS}", "q4", COMMON), (f"nvfp4-{OS}", "nvfp4", COMMON),
        (f"nvfp4-mtp-{OS}", "nvfp4", f"{COMMON} {NV_MTP}"), (f"hemmingway-{OS}", "hemmingway", COMMON),
        (f"apex-mtp-{OS}", "apex", f"{COMMON} {AP_MTP}")]
EP = ("http://127.0.0.1:18196" if OS == "wsl" else f"http://{oc.HOST}:18197") + "/v1/chat/completions"


def done(tag: str, snap: str, temp: str) -> int:
    return len(list(RUNS.glob(f"atual~{tag}~{snap}~base~t{temp}~*.json")))


def call(tag: str, snap: str, temp: float, repeats: int) -> None:
    subprocess.run([sys.executable, str(ROOT / "tools/guardian_synthesis_bench.py"), "run", "--arm", "atual",
                    "--snapshot", snap, "--endpoint", EP, "--model", tag, "--temperature", str(temp),
                    "--seed", "42", "--repeats", str(repeats), "--max-tokens-auto", "--timeout", "900",
                    "--chat-template-kwargs", json.dumps({"enable_thinking": False}), "--confirm-inference"],
                   timeout=900 * repeats + 120)


try:
    for tag, model, extra in PLAN:
        todo = [(s, t, n) for s in SNAPS for t, n in (("0p0", 1), ("0p3", 3)) if done(tag, s, t) < n]
        if not todo:
            oc.log(f"{tag}: completo, pulando")
            continue
        oc.stop_all()
        oc.log(f"{tag}: subindo [{extra}]")
        if not oc.start(OS, model, extra):
            oc.log(f"{tag}: NÃO SUBIU — {oc.ssh(f'tail -3 /tmp/opt-{model}-{OS}.log')[-300:]}")
            continue
        for snap, t, n in todo:
            call(tag, snap, 0.0 if t == "0p0" else 0.3, n)
        oc.log(f"{tag}: {sum(done(tag, s, t) for s in SNAPS for t in ('0p0', '0p3'))}/16 runs")
finally:
    oc.stop_all()
    oc.ssh(f"setsid nohup {oc.WSL_BIN} --model {oc.PROD} < /dev/null > /tmp/llama-18194.log 2>&1 &")
    back = oc.wait_health("http://127.0.0.1:18194")
    oc.log(f"PRODUÇÃO {'DE VOLTA' if back else 'NÃO VOLTOU — VERIFICAR'}")
