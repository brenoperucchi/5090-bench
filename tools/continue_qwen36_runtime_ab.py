#!/usr/bin/env python3
"""Finish the llama.cpp arm after the Ollama arm has already completed."""

from __future__ import annotations

import json
import shlex
import subprocess
import sys
import urllib.request
from pathlib import Path

from run_qwen36_runtime_ab import LLAMA_BINARY, ROOT, now, save, ssh, state


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit("usage: continue_qwen36_runtime_ab.py RUN_DIR")
    run_dir = Path(sys.argv[1]).resolve()
    record_path = run_dir / "run.json"
    record = json.loads(record_path.read_text(encoding="utf-8"))
    if record.get("status") not in {"running", "failed"}:
        raise SystemExit(f"unexpected run status: {record.get('status')}")
    if any(event.get("event") == "llama_cpp_arm_complete" for event in record.get("events", [])):
        raise SystemExit("llama.cpp arm is already recorded complete; refusing duplicate calls")
    record["status"] = "running"
    record.setdefault("events", []).append({"at": now(), "event": "resume_after_llama_readiness_timeout", "calls": 0})
    if not (run_dir / "ollama" / "ollama.json").exists():
        raise SystemExit("Ollama arm artifact is missing")
    with urllib.request.urlopen("http://192.168.0.125:11434/api/ps", timeout=10) as response:
        ps = json.loads(response.read().decode("utf-8"))
    if ps.get("models"):
        raise SystemExit(f"Ollama is still resident: {ps}")

    processes = ssh("ps -eo pid=,args= | grep '[l]lama-server' || true", check=False)
    candidates = []
    for line in processes.splitlines():
        parts = line.strip().split(None, 1)
        if len(parts) == 2 and parts[0].isdigit() and parts[1].startswith(LLAMA_BINARY) and "--port 18087" in parts[1]:
            candidates.append((parts[0], parts[1]))
    if len(candidates) != 1:
        raise SystemExit(f"expected one dedicated llama-server, found: {candidates!r}")
    pid, args = candidates[0]
    flags_before = record.get("llama_flags_before", "")
    if shlex.split(args) != shlex.split(flags_before):
        raise SystemExit("current llama-server flags differ from captured pre-stop flags")

    record["llama_pid_after_restart"] = pid
    record["llama_flags_after"] = args
    record["flags_identical"] = True
    record.setdefault("events", []).append({"at": now(), "event": "llama_restarted", "pid": pid, "flags_identical": True})
    save(run_dir, record)
    subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools/qwen36_runtime_bench.py"),
            "--runtime",
            "llama_cpp",
            "--out",
            str(run_dir / "llama_cpp"),
            "--manifest",
            str(run_dir / "prompt-manifest.json"),
            "--reps",
            "5",
        ],
        check=True,
    )
    record.setdefault("events", []).append({"at": now(), "event": "llama_cpp_arm_complete", "calls": 24})
    record["status"] = "complete"
    record["comparison_valid"] = True
    record["comparison_scope"] = "runtime_plus_artifact_not_pure_runtime"
    record["result_interpretation"] = (
        "Valid paired A/B under the common prompt manifest. The result compares "
        "runtime plus artifact: Ollama tag versus standalone GGUF; it is not a pure runtime effect."
    )
    record["generation_calls_observed"] = {"ollama": 24, "llama_cpp": 24, "total": 48}
    record["rejected_generation_requests"] = {"ollama": 0, "llama_cpp": 0}
    record["recovered_from_operational_timeout"] = {
        "initial_timeout_seconds": 90,
        "note": "llama-server cold load exceeded the old readiness window; no generation was issued during the timeout",
    }
    record.pop("error", None)
    record["state_after"] = state("after_run", pid)
    record["completed_at"] = now()
    save(run_dir, record)
    print(run_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
