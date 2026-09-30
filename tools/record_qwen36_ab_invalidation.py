#!/usr/bin/env python3
"""Record the fail-closed invalidation of the first runtime A/B attempt."""

from __future__ import annotations

import json
import shlex
import sys
from pathlib import Path

from run_qwen36_runtime_ab import LLAMA_BINARY, now, save, ssh, state


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit("usage: record_qwen36_ab_invalidation.py RUN_DIR")
    run_dir = Path(sys.argv[1]).resolve()
    path = run_dir / "run.json"
    record = json.loads(path.read_text(encoding="utf-8"))
    processes = ssh("ps -eo pid=,args= | grep '[l]lama-server' || true", check=False)
    candidates = []
    for line in processes.splitlines():
        parts = line.strip().split(None, 1)
        if len(parts) == 2 and parts[0].isdigit() and parts[1].startswith(LLAMA_BINARY) and "--port 18087" in parts[1]:
            candidates.append((parts[0], parts[1]))
    pid, args = candidates[0] if len(candidates) == 1 else ("unknown", "unknown")
    before = record.get("llama_flags_before", "")
    record["status"] = "invalidated_before_comparison"
    record["comparison_valid"] = False
    record["validity_reason"] = "same prompt was not delivered to both arms"
    record["invalidation"] = {
        "at": now(),
        "reason": "context_heavy prompt exceeded llama.cpp n_ctx=32768 (50384 tokens); llama.cpp returned HTTP 400, while Ollama accepted/truncated the request to prompt_eval_count=16386",
        "llama_cpp_error": "request (50384 tokens) exceeds the available context size (32768 tokens)",
        "ollama_observed_prompt_eval_count": 16386,
        "retry": "not performed; authorized 48-call budget not extended",
    }
    record["generation_calls_observed"] = {"ollama": 24, "llama_cpp": 3, "total": 27}
    record["rejected_generation_requests"] = {"llama_cpp": 1}
    record["non_generation_controls"] = {"ollama_unload": 1}
    record["llama_cpp_warmup_successful"] = 3
    record["llama_cpp_measurements"] = 0
    record["llama_pid_after_restart"] = pid
    record["llama_flags_after"] = args
    record["flags_identical"] = bool(args != "unknown" and shlex.split(args) == shlex.split(before))
    record.setdefault("events", []).append({
        "at": now(),
        "event": "ab_invalidated_before_comparison",
        "calls": 0,
        "flags_identical": record["flags_identical"],
    })
    record["state_at_invalidation"] = state("after_invalidation", pid if pid != "unknown" else None)
    record["completed_at"] = now()
    save(run_dir, record)
    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
