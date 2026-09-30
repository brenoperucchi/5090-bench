#!/usr/bin/env python3
"""Redo the 8 pre-optimization qwen38-wsl cells (container, Ryzen9) with -ub 1024 -b 4096.

New tag qwen38-opt-wsl so the 2026-09-22 runs are kept, not overwritten.
Production is always restored at the end.
"""
import json
import subprocess
import sys
from pathlib import Path

import optimization_campaign as oc

ROOT = Path(__file__).resolve().parents[1]
RUNS = ROOT / "results/guardian-synthesis-20260921/runs"
SNAPS = ["mfc-exec~container~36e2a6ef93dc", "mfc-exec~Ryzen9~ff6b18a9aaf6"]
TAG, EP = "qwen38-opt-wsl", "http://127.0.0.1:18196/v1/chat/completions"

try:
    oc.stop_all()
    oc.log(f"{TAG}: subindo [-ub 1024 -b 4096]")
    if oc.start("wsl", "q4", "-ub 1024 -b 4096"):
        for snap in SNAPS:
            for temp, n in ((0.0, 1), (0.3, 3)):
                subprocess.run([sys.executable, str(ROOT / "tools/guardian_synthesis_bench.py"), "run",
                                "--arm", "atual", "--snapshot", snap, "--endpoint", EP, "--model", TAG,
                                "--temperature", str(temp), "--seed", "42", "--repeats", str(n),
                                "--max-tokens-auto", "--timeout", "900",
                                "--chat-template-kwargs", json.dumps({"enable_thinking": False}),
                                "--confirm-inference"], timeout=900 * n + 120)
        oc.log(f"{TAG}: {len(list(RUNS.glob(f'atual~{TAG}~*.json')))}/8 runs")
    else:
        oc.log(f"{TAG}: NÃO SUBIU")
finally:
    oc.stop_all()
    oc.ssh(f"setsid nohup {oc.WSL_BIN} --model {oc.PROD} < /dev/null > /tmp/llama-18194.log 2>&1 &")
    oc.log(f"PRODUÇÃO {'DE VOLTA' if oc.wait_health('http://127.0.0.1:18194') else 'NÃO VOLTOU — VERIFICAR'}")
