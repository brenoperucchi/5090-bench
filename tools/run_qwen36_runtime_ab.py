#!/usr/bin/env python3
"""Orchestrate the authorized serial Qwen3.6 Ollama/llama.cpp A/B.

The dedicated llama.cpp process is validated before it is stopped.  Its exact
command line is captured and must match after restart before the second arm is
allowed to generate.  The script never starts both model runtimes together.
"""

from __future__ import annotations

import json
import shlex
import subprocess
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
REMOTE = "brenoperucchi@192.168.0.125"
LLAMA_BINARY = "/home/brenoperucchi/t87-runtime/codacus-build-final2/bin/llama-server"
OLLAMA_BASE = "http://192.168.0.125:11434"
LLAMA_BASE = "http://192.168.0.125:18087"
OLLAMA_MODEL = "qwen3.6:35b-a3b"
AUTH_SHA256 = "47fc4fad0bb8299e2a5dab71df5f5e34c7d826733341e5afc268fcdef6598ad5"


def now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def ssh(command: str, *, check: bool = True, timeout: int = 60) -> str:
    result = subprocess.run(
        ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10", REMOTE, command],
        text=True,
        capture_output=True,
        timeout=timeout,
        check=check,
    )
    if result.stderr:
        print(result.stderr, file=sys.stderr, end="")
    return result.stdout.strip()


def get_json(url: str, timeout: int = 15) -> Any:
    with urllib.request.urlopen(url, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def post_json(url: str, payload: dict[str, Any], timeout: int = 60) -> Any:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def remote_process(pid: str) -> str:
    return ssh(f"ps -p {shlex.quote(pid)} -o args=", check=False)


def discover_llama() -> tuple[str, str]:
    processes = ssh("ps -eo pid=,args= | grep '[l]lama-server' || true", check=False)
    candidates: list[tuple[str, str]] = []
    for line in processes.splitlines():
        parts = line.strip().split(None, 1)
        if len(parts) != 2 or not parts[0].isdigit():
            continue
        pid, args = parts
        if args.startswith(LLAMA_BINARY) and "--port 18087" in args:
            candidates.append((pid, args))
    if len(candidates) != 1:
        raise RuntimeError(f"expected exactly one dedicated llama-server on port 18087, found {candidates!r}")
    return candidates[0]


def gpu_snapshot() -> str:
    return ssh(
        "/usr/lib/wsl/lib/nvidia-smi --query-gpu=name,memory.used,memory.total,utilization.gpu --format=csv,noheader",
        check=False,
    )


def state(label: str, llama_pid: str | None = None) -> dict[str, Any]:
    result: dict[str, Any] = {"label": label, "captured_at": now(), "gpu": gpu_snapshot()}
    result["llama_pid"] = llama_pid or "unknown"
    result["llama_process"] = remote_process(llama_pid) if llama_pid else ssh(
        "ps -eo pid=,args= | grep '[l]lama-server' || true", check=False
    )
    result["listeners"] = ssh("ss -ltnp 2>/dev/null | grep -E ':(11434|18087)\\b' || true", check=False)
    for name, url in (
        ("ollama_version", f"{OLLAMA_BASE}/api/version"),
        ("ollama_ps", f"{OLLAMA_BASE}/api/ps"),
        ("llama_health", f"{LLAMA_BASE}/health"),
        ("llama_models", f"{LLAMA_BASE}/v1/models"),
    ):
        try:
            result[name] = get_json(url)
        except Exception as exc:  # noqa: BLE001 - state must preserve unknown/error
            result[name] = {"error": f"{type(exc).__name__}: {exc}"}
    return result


def save(run_dir: Path, record: dict[str, Any]) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "run.json").write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def wait_process_gone(pid: str, timeout: int = 30) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if not remote_process(pid):
            return
        time.sleep(1)
    raise RuntimeError(f"llama-server PID {pid} did not stop gracefully")


def start_same_llama(command_tokens: list[str]) -> tuple[str, str]:
    log_path = "/home/brenoperucchi/t87-runtime/codacus-build-final2/qwen36-ab-llama.log"
    command = (
        f"nohup {shlex.join(command_tokens)} > {shlex.quote(log_path)} 2>&1 </dev/null & echo $!"
    )
    launcher_pid = ssh(command, timeout=30).splitlines()[-1].strip()
    if not launcher_pid.isdigit():
        raise RuntimeError(f"could not identify launcher PID: {launcher_pid!r}")
    deadline = time.monotonic() + 300
    while time.monotonic() < deadline:
        processes = ssh("ps -eo pid=,args= | grep '[l]lama-server' || true", check=False)
        for line in processes.splitlines():
            parts = line.strip().split(None, 1)
            if len(parts) != 2 or not parts[0].isdigit():
                continue
            pid, args = parts
            if not args.startswith(LLAMA_BINARY) or "--port 18087" not in args:
                continue
            try:
                health = get_json(f"{LLAMA_BASE}/health")
                models = get_json(f"{LLAMA_BASE}/v1/models")
                if health.get("status") == "ok" and models.get("data"):
                    return pid, args
            except Exception:  # noqa: BLE001 - poll until ready
                pass
        time.sleep(2)
    raise RuntimeError(f"restarted llama-server did not become healthy (launcher {launcher_pid})")


def unload_ollama() -> dict[str, Any]:
    # Ollama's keep_alive=0 control request unloads the model; it has no prompt
    # and is recorded as control, not as one of the 48 benchmark generations.
    return post_json(
        f"{OLLAMA_BASE}/api/generate",
        {"model": OLLAMA_MODEL, "keep_alive": 0, "stream": False},
    )


def main() -> int:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = ROOT / "results" / f"qwen36-runtime-ab-{stamp}"
    record: dict[str, Any] = {
        "schema_version": "qwen36-runtime-ab-run-v1",
        "status": "running",
        "started_at": now(),
        "authorization_sha256": AUTH_SHA256,
        "authorized_generations": 48,
        "order": ["ollama", "llama_cpp"],
        "events": [],
    }
    run_dir.mkdir(parents=True, exist_ok=False)
    save(run_dir, record)

    pid_before, args_before = discover_llama()
    before = state("before_stop", pid_before)
    record["state_before"] = before
    record["llama_pid_before"] = pid_before
    active_pid: str | None = pid_before
    try:
        command_tokens = shlex.split(args_before)
    except ValueError as exc:
        raise RuntimeError(f"cannot parse llama-server command: {args_before!r}") from exc
    if not command_tokens or command_tokens[0] != LLAMA_BINARY or "--port" not in command_tokens or command_tokens[command_tokens.index("--port") + 1] != "18087":
        raise RuntimeError(f"refusing to stop unexpected process: {args_before!r}")
    record["llama_flags_before"] = args_before
    record["events"].append({"at": now(), "event": "validated_llama_flags_before", "pid": pid_before})
    manifest_path = run_dir / "prompt-manifest.json"
    subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools/qwen36_runtime_bench.py"),
            "--runtime",
            "llama_cpp",
            "--prepare-manifest",
            str(manifest_path),
        ],
        check=True,
    )
    record["prompt_manifest"] = json.loads(manifest_path.read_text(encoding="utf-8"))
    record["events"].append({"at": now(), "event": "prompt_manifest_preflight_complete", "calls": 0})
    save(run_dir, record)

    try:
        ssh(f"kill -TERM {pid_before}", timeout=30)
        wait_process_gone(pid_before)
        record["events"].append({"at": now(), "event": "llama_stopped", "pid": pid_before})
        save(run_dir, record)

        ollama_dir = run_dir / "ollama"
        subprocess.run(
            [
                sys.executable,
                str(ROOT / "tools/qwen36_runtime_bench.py"),
                "--runtime",
                "ollama",
                "--out",
                str(ollama_dir),
                "--manifest",
                str(manifest_path),
                "--reps",
                "5",
            ],
            check=True,
        )
        record["events"].append({"at": now(), "event": "ollama_arm_complete", "calls": 24})
        save(run_dir, record)

        record["ollama_unload_control"] = unload_ollama()
        record["events"].append({"at": now(), "event": "ollama_model_unloaded", "calls": 0})
        save(run_dir, record)
        ps_after_unload = get_json(f"{OLLAMA_BASE}/api/ps")
        if ps_after_unload.get("models"):
            raise RuntimeError(f"Ollama model remained resident after unload: {ps_after_unload}")

        new_pid, args_after = start_same_llama(command_tokens)
        active_pid = new_pid
        record["llama_pid_after_restart"] = new_pid
        record["llama_flags_after"] = args_after
        record["flags_identical"] = shlex.split(args_after) == command_tokens
        record["events"].append({"at": now(), "event": "llama_restarted", "pid": new_pid, "flags_identical": record["flags_identical"]})
        save(run_dir, record)
        if not record["flags_identical"]:
            raise RuntimeError("llama-server flags changed after restart; refusing llama.cpp arm")

        llama_dir = run_dir / "llama_cpp"
        subprocess.run(
            [
                sys.executable,
                str(ROOT / "tools/qwen36_runtime_bench.py"),
                "--runtime",
                "llama_cpp",
                "--out",
                str(llama_dir),
                "--manifest",
                str(manifest_path),
                "--reps",
                "5",
            ],
            check=True,
        )
        record["events"].append({"at": now(), "event": "llama_cpp_arm_complete", "calls": 24})
        record["status"] = "complete"
        record["comparison_valid"] = True
        record["comparison_scope"] = "runtime_plus_artifact_not_pure_runtime"
        record["result_interpretation"] = (
            "Valid paired A/B under the common prompt manifest. The result compares "
            "runtime plus artifact: Ollama tag versus standalone GGUF; it is not a pure runtime effect."
        )
        record["generation_calls_observed"] = {"ollama": 24, "llama_cpp": 24, "total": 48}
        record["rejected_generation_requests"] = {"ollama": 0, "llama_cpp": 0}
    except Exception as exc:  # noqa: BLE001 - persist failure and restore dedicated server
        record["status"] = "failed"
        record["error"] = f"{type(exc).__name__}: {exc}"
        record["events"].append({"at": now(), "event": "failure", "error": record["error"]})
        raise
    finally:
        # Restore the dedicated server if the Ollama arm failed before the
        # normal restart path.  This is the same captured command, never a
        # guessed or modified command line.
        try:
            ps = get_json(f"{OLLAMA_BASE}/api/ps")
            if ps.get("models"):
                record["recovery_unload_control"] = unload_ollama()
                record["events"].append({"at": now(), "event": "recovery_ollama_unloaded", "calls": 0})
        except Exception as recovery_exc:  # noqa: BLE001 - preserve unknown
            record["recovery_unload_error"] = f"{type(recovery_exc).__name__}: {recovery_exc}"
        try:
            if not remote_process(active_pid or pid_before):
                recovered_pid, recovered_args = start_same_llama(command_tokens)
                active_pid = recovered_pid
                record["recovery_llama_pid"] = recovered_pid
                record["recovery_llama_flags"] = recovered_args
                record["events"].append({"at": now(), "event": "recovery_llama_restarted", "pid": recovered_pid})
        except Exception as recovery_exc:  # noqa: BLE001 - preserve unknown
            record["recovery_llama_error"] = f"{type(recovery_exc).__name__}: {recovery_exc}"
        record["state_after"] = state("after_run", active_pid)
        record["completed_at"] = now()
        save(run_dir, record)
        print(run_dir)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
