#!/usr/bin/env python3
"""Bounded, hash-addressed agentic harness for T87 P1 protocol v2.

The default operation is preparation only.  Generation requires ``run`` and
is intentionally separate so that the runtime packet can be inspected before
any POST reaches llama-server.

The model never receives the benchmark checkout.  Its only shell tool is
translated from the published ``ssh lab 'cd ~/lab/<task> && ...'`` shape into
an isolated bwrap sandbox containing that task's files.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shlex
import signal
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ENDPOINT = "http://192.168.0.125:18087"
REMOTE_HOST = "192.168.0.125"
LAB_USER = "labuser"
LAB_HOME = f"/home/{LAB_USER}"
LAB_VENV = f"{LAB_HOME}/venv"
LAB_TASK_ROOT = f"{LAB_HOME}/lab"
LAB_SOURCE = "/opt/spec-wins"
PRIVILEGED_RESET = "/opt/spec-wins/scripts/reset-lab.sh"
PRIVILEGED_GRADER = "/opt/spec-wins/scripts/verify-lab.sh"
LAB_KEY_PATH = Path(__file__).resolve().parent.parent / ".secrets/labuser_key"
SETUP_SCRIPT = "/home/brenoperucchi/t87-runtime/spec-wins/scripts/setup-labuser.sh"
DEPENDENCY_LOCK = f"{LAB_HOME}/requirements.lock"
ROUTE = {
    "id": "lan",
    "scheme": "http",
    "host": "192.168.0.125",
    "port": 18087,
    "request_path": "/v1/chat/completions",
}
REMOTE_SOURCE = "/home/brenoperucchi/t87-runtime/spec-wins"
MODEL = "/mnt/e/llm-bench-t87-p1/models/qwen3.6-35b-a3b-q4_k_m.gguf"
BENCHMARK_COMMIT = "776e799c7e0a24271e021aca2ea4b1c1b1f10017"
BINARY_SHA256 = "37acf8e80c85f91794d9fa0268d34b40dbfa2f4286527a92bdd13dfefdab689b"
MODEL_SHA256 = "d372de8e934898a59e6ccfabc3368474711384d8f1fd4d22d87a3f0a45400cdc"
SEEDS = (1000, 1017, 1034, 1051, 1068)
TASKS = ("t1_ratelimit", "t2_metrics", "t3_pipeline")
REFERENCE_TURNS = {"t1_ratelimit": 13, "t2_metrics": 27, "t3_pipeline": 26}
MAX_OUTPUT_TOKENS = 4096
GPU_FREE_THRESHOLD_MIB = 8000
RESPONSE_CHANNEL_PROBE_TURNS = 5
RESPONSE_CHANNEL_DEFECT_FRACTION_LIMIT = 0.5
SAMPLING = {
    "temperature": 0.6,
    "top_p": 0.95,
    "top_k": 20,
    "max_tokens": MAX_OUTPUT_TOKENS,
    "cache_prompt": False,
}
SERVER_CONTEXT_SIZE = 32768
RUNTIME_ID = "thecodacus/llama.cpp"
HARNESS_VERSION = "t87-p1-harness-v10"
CONTROL_SSH_OPTIONS = [
    "-o", "BatchMode=yes",
    "-o", "ConnectTimeout=30",
    "-o", "TCPKeepAlive=yes",
    "-o", "ServerAliveInterval=15",
    "-o", "ServerAliveCountMax=3",
]
LAB_SSH_OPTIONS = CONTROL_SSH_OPTIONS + [
    "-i", str(LAB_KEY_PATH),
    "-o", "IdentitiesOnly=yes",
]
SERIES_KEY: str | None = None


def offload_config() -> dict[str, str]:
    """Return the server placement identity used by this campaign.

    The endpoint is managed outside this harness, so an unobserved flag is
    deliberately recorded as ``unknown``.  Such a series may be preserved,
    but the fail-closed aggregator below will not combine it with another
    series until all placement fields are observable.
    """
    return {
        "cpu_moe": os.environ.get("LLAMA_CPU_MOE", "unknown"),
        "n_cpu_moe": os.environ.get("LLAMA_N_CPU_MOE", "unknown"),
        "moe_cache_slots": os.environ.get("LLAMA_MOE_CACHE_SLOTS", "unknown"),
        "moe_cache_profile": os.environ.get("LLAMA_MOE_CACHE_PROFILE", "unknown"),
        "load_mode": os.environ.get("LLAMA_LOAD_MODE", "unknown"),
        "n_gpu_layers": os.environ.get("LLAMA_N_GPU_LAYERS", "unknown"),
    }


def assert_single_series(records: list[dict[str, Any]]) -> str:
    """Fail closed if runtime, route, or placement identity is mixed/unknown."""
    keys = {record.get("series_key") for record in records}
    if len(keys) != 1 or None in keys:
        raise ValueError("refusing to aggregate mixed or unidentified series")
    key = next(iter(keys))
    try:
        identity = json.loads(key)
        placement = identity["offload_config"]
        expected = {
            "cpu_moe",
            "n_cpu_moe",
            "moe_cache_slots",
            "moe_cache_profile",
            "load_mode",
            "n_gpu_layers",
        }
        if set(placement) != expected or any(placement[field] == "unknown" for field in expected):
            raise ValueError
    except (TypeError, json.JSONDecodeError, KeyError, ValueError):
        raise ValueError("refusing to aggregate series with unknown offload identity") from None
    return key


def now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def run_ssh(
    command: str,
    *,
    lab: bool = False,
    timeout: int = 30,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    if lab:
        if not LAB_KEY_PATH.is_file():
            raise RuntimeError(f"dedicated labuser key is missing: {LAB_KEY_PATH}")
        options = LAB_SSH_OPTIONS
        target = f"{LAB_USER}@{REMOTE_HOST}"
    else:
        options = CONTROL_SSH_OPTIONS
        target = REMOTE_HOST
    return subprocess.run(
        ["ssh", *options, target, command],
        text=True,
        capture_output=True,
        timeout=timeout,
        check=check,
    )


def remote_text(path: str) -> str:
    result = run_ssh(f"sed -n '1,2000p' {shlex.quote(path)}")
    return result.stdout


def endpoint_get(path: str) -> Any:
    with urllib.request.urlopen(ENDPOINT + path, timeout=30) as response:
        return json.load(response)


def lab_environment_identity() -> dict[str, str]:
    """Read the effective labuser environment without changing it."""
    checks = {
        "execution_user": "whoami",
        "python_version": f"{shlex.quote(LAB_VENV)}/bin/python --version",
        "dependency_fingerprint": f"sha256sum {shlex.quote(DEPENDENCY_LOCK)}",
        "installed_dependency_fingerprint": f"{shlex.quote(LAB_VENV)}/bin/pip freeze | sha256sum",
    }
    identity: dict[str, str] = {
        "venv_path": LAB_VENV,
        "reset_path": PRIVILEGED_RESET,
        "reset_sha256": "unknown",
        "task_root": LAB_TASK_ROOT,
        "source_path": LAB_SOURCE,
    }
    for key, command in checks.items():
        result = run_ssh(command, lab=True, timeout=30, check=False)
        if result.returncode != 0:
            raise RuntimeError(f"lab environment check failed: {key}: {result.stderr.strip()}")
        value = result.stdout.strip()
        if key.endswith("fingerprint") or key.endswith("sha256"):
            value = value.split()[0]
        if key == "python_version":
            value = value.removeprefix("Python ")
        identity[key] = value
    setup_result = run_ssh(f"sha256sum {shlex.quote(SETUP_SCRIPT)}", timeout=30, check=False)
    if setup_result.returncode != 0:
        raise RuntimeError(f"control setup hash failed: {setup_result.stderr.strip()}")
    identity["setup_sha256"] = setup_result.stdout.split()[0]
    if identity["execution_user"] != LAB_USER:
        raise RuntimeError(f"unexpected lab execution user: {identity['execution_user']}")
    return identity


def build_series_key(environment: dict[str, str]) -> str:
    return json.dumps(
        {
            "runtime": RUNTIME_ID,
            "harness_version": HARNESS_VERSION,
            "model_sha256": MODEL_SHA256,
            "benchmark_commit": BENCHMARK_COMMIT,
            "route": ROUTE,
            "offload_config": offload_config(),
            "gpu_free_threshold_mib": GPU_FREE_THRESHOLD_MIB,
            "execution_user": environment["execution_user"],
            "python_version": environment["python_version"],
            "venv_path": environment["venv_path"],
            "dependency_fingerprint": environment["dependency_fingerprint"],
            "installed_dependency_fingerprint": environment["installed_dependency_fingerprint"],
            "setup_sha256": environment["setup_sha256"],
            "reset_sha256": environment["reset_sha256"],
            "suite_path": LAB_SOURCE,
            "suite_mode": "0700",
            "suite_owner": "root:root",
            "answer_key_protected": "true",
            "hidden_protected": "true",
            "grader_command": PRIVILEGED_GRADER,
            "reset_command": PRIVILEGED_RESET,
            "grader_privilege": "sudo -n",
            "response_channel_probe_turns": RESPONSE_CHANNEL_PROBE_TURNS,
            "response_channel_defect_fraction_limit": RESPONSE_CHANNEL_DEFECT_FRACTION_LIMIT,
        },
        sort_keys=True,
        separators=(",", ":"),
    )


def gpu_snapshot() -> str:
    return gpu_snapshot_from_state(gpu_state())


def gpu_snapshot_from_state(state: dict[str, Any]) -> str:
    if not state.get("observable"):
        return "unknown"
    return (
        f"{state.get('name', 'unknown')}, {state.get('memory_used_mib')} MiB, "
        f"{state.get('memory_total_mib')} MiB, {state.get('utilization_gpu_percent')} %, "
        f"{state.get('driver_version', 'unknown')}"
    )


def gpu_state() -> dict[str, Any]:
    """Capture GPU residency and compute processes without touching inference."""
    command = (
        "/usr/lib/wsl/lib/nvidia-smi "
        "--query-gpu=name,memory.used,memory.free,memory.total,utilization.gpu,driver_version "
        "--format=csv,noheader,nounits; "
        "printf '__T87_GPU_PROCESSES__\\n'; "
        "/usr/lib/wsl/lib/nvidia-smi "
        "--query-compute-apps=pid,process_name,used_memory --format=csv,noheader,nounits"
    )
    result = run_ssh(command, lab=True, timeout=30, check=False)
    captured = now()
    raw = result.stdout.strip()
    state: dict[str, Any] = {
        "captured_at": captured,
        "threshold_mib": GPU_FREE_THRESHOLD_MIB,
        "observable": False,
        "query_exit_code": result.returncode,
        "name": None,
        "memory_used_mib": None,
        "memory_free_mib": None,
        "memory_total_mib": None,
        "utilization_gpu_percent": None,
        "driver_version": None,
        "processes": [],
        "raw": raw,
        "stderr": result.stderr,
        "contaminated": False,
        "gate_passed": False,
    }
    gpu_text, _, process_text = raw.partition("__T87_GPU_PROCESSES__")
    fields = [field.strip() for field in gpu_text.splitlines()[0].split(",")] if gpu_text.splitlines() else []
    try:
        if len(fields) < 6:
            raise ValueError("nvidia-smi returned fewer than six GPU fields")
        state.update({
            "name": fields[0],
            "memory_used_mib": int(fields[1]),
            "memory_free_mib": int(fields[2]),
            "memory_total_mib": int(fields[3]),
            "utilization_gpu_percent": int(fields[4]),
            "driver_version": fields[5],
            "observable": result.returncode == 0,
        })
        for line in process_text.splitlines():
            line = line.strip()
            if not line or line.lower().startswith("no running processes"):
                continue
            process_fields = [field.strip() for field in line.split(",")]
            if len(process_fields) >= 3:
                try:
                    state["processes"].append({
                        "pid": int(process_fields[0]),
                        "process_name": process_fields[1],
                        "used_memory_mib": int(process_fields[2]),
                    })
                except ValueError:
                    state["processes"].append({
                        "pid": process_fields[0],
                        "process_name": process_fields[1],
                        "used_memory_mib": process_fields[2],
                    })
    except (ValueError, IndexError):
        state["observable"] = False
    free_mib = state.get("memory_free_mib")
    state["contaminated"] = isinstance(free_mib, int) and free_mib < GPU_FREE_THRESHOLD_MIB
    state["gate_passed"] = bool(state["observable"] and isinstance(free_mib, int) and not state["contaminated"])
    return state


def endpoint_post(payload: dict[str, Any]) -> dict[str, Any]:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        ENDPOINT + "/v1/chat/completions",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=360) as response:
        return json.load(response)


def parse_prompts(text: str) -> dict[str, str]:
    preamble_match = re.search(r"^## Preamble\n(?P<body>.*?)(?=^## Task 1)", text, re.M | re.S)
    if not preamble_match:
        raise ValueError("published preamble not found")
    prompts = {"preamble": preamble_match.group("body").strip()}
    for number, task in enumerate(TASKS, 1):
        match = re.search(
            rf"^## Task {number} — (?P<title>.*?)\n(?P<body>.*?)(?=^## Task {number + 1} —|\Z)",
            text,
            re.M | re.S,
        )
        if not match:
            raise ValueError(f"published task block not found: {task}")
        # Pi's published transcript contains the task heading as text
        # (``Task — cd ~/lab/<task>``), so retain the heading's operational
        # directory instruction instead of silently dropping it.
        title = match.group("title").strip().replace("`", "")
        prompts[task] = f"Task — {title}\n{match.group('body').strip()}"
    return prompts


def fetch_prompt_packet() -> tuple[dict[str, str], str]:
    text = remote_text(f"{REMOTE_SOURCE}/docs/prompts.md")
    return parse_prompts(text), sha256_bytes(text.encode("utf-8"))


def server_identity(environment: dict[str, str]) -> dict[str, Any]:
    if SERIES_KEY is None:
        raise RuntimeError("series key has not been initialized")
    captured_gpu = gpu_state()
    return {
        "health": endpoint_get("/health"),
        "models": endpoint_get("/v1/models"),
        "captured_at": now(),
        "endpoint": ENDPOINT,
        "route": ROUTE,
        "model": MODEL,
        "model_sha256": MODEL_SHA256,
        "binary_sha256": BINARY_SHA256,
        "gpu_snapshot": gpu_snapshot_from_state(captured_gpu),
        "gpu_state": captured_gpu,
        "execution_user": environment["execution_user"],
        "python_version": environment["python_version"],
        "venv_path": environment["venv_path"],
        "dependency_fingerprint": environment["dependency_fingerprint"],
        "installed_dependency_fingerprint": environment["installed_dependency_fingerprint"],
        "setup_sha256": environment["setup_sha256"],
        "reset_sha256": environment["reset_sha256"],
        "suite_path": LAB_SOURCE,
        "suite_mode": "0700",
        "suite_owner": "root:root",
        "answer_key_protected": True,
        "hidden_protected": True,
        "grader_command": PRIVILEGED_GRADER,
        "reset_command": PRIVILEGED_RESET,
        "grader_privilege": "sudo -n",
        "response_channel_probe_turns": RESPONSE_CHANNEL_PROBE_TURNS,
        "response_channel_defect_fraction_limit": RESPONSE_CHANNEL_DEFECT_FRACTION_LIMIT,
        "runtime": RUNTIME_ID,
        "harness_version": HARNESS_VERSION,
        "benchmark_commit": BENCHMARK_COMMIT,
        "series_key": SERIES_KEY,
    }


def reset_lab(run_id: str) -> tuple[dict[str, str], dict[str, Any]]:
    """Reset the protected lab through the allowlisted root wrapper."""
    command = f"LLAMA_SERVER={shlex.quote(ENDPOINT)} sudo -n {shlex.quote(PRIVILEGED_RESET)}"
    result = run_ssh(command, timeout=180, check=False)
    reset_record = {
        "run_id": run_id,
        "reset_path": PRIVILEGED_RESET,
        "source_path": LAB_SOURCE,
        "llama_server": ENDPOINT,
        "command": command,
        "privilege": "sudo -n",
        "exit_code": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "captured_at": now(),
    }
    if result.returncode != 0:
        raise RuntimeError(f"lab reset failed: {result.stderr.strip()}")
    task_dirs = {task: f"{LAB_TASK_ROOT}/{task}" for task in TASKS}
    verify = run_ssh(
        " && ".join(f"test -d {shlex.quote(path)}" for path in task_dirs.values()),
        lab=True,
        timeout=30,
        check=False,
    )
    if verify.returncode != 0:
        raise RuntimeError(f"lab reset did not produce all task directories: {verify.stderr.strip()}")
    return task_dirs, reset_record


def parse_model_command(value: Any) -> tuple[str, str]:
    if not isinstance(value, str):
        raise ValueError("bash.command must be a string")
    try:
        argv = shlex.split(value)
    except ValueError as exc:
        raise ValueError("bash.command is not shell-parseable") from exc
    if len(argv) != 3 or argv[:2] != ["ssh", "lab"]:
        raise ValueError("only the published ssh lab command shape is allowed")
    match = re.fullmatch(r"cd ~/lab/(t[123]_[a-z]+) && (.*)", argv[2], re.S)
    if not match or match.group(1) not in TASKS:
        raise ValueError("command must start with cd ~/lab/<published-task> &&")
    inner = match.group(2)
    if re.search(r"\b(?:ssh|sudo|su|runuser|unshare|bwrap|nsenter)\b", inner):
        raise ValueError("nested privilege or namespace control is not allowed")
    for url in re.findall(r"https?://[^\s'\"]+", inner):
        if not re.match(r"https?://(?:127\.0\.0\.1|localhost)(?::\d+)?(?:/|$)", url):
            raise ValueError("network access is restricted to localhost")
    return match.group(1), inner


def run_sandbox_command(task: str, inner: str, task_dir: str, *, timeout: int = 300) -> dict[str, Any]:
    visible_task = f"{LAB_TASK_ROOT}/{task}"
    command = f"cd {shlex.quote(visible_task)} && {inner}"
    args = [
        "bwrap",
        "--die-with-parent",
        "--unshare-pid",
        "--unshare-uts",
        "--unshare-ipc",
        "--ro-bind", "/usr", "/usr",
        "--ro-bind", "/usr/local", "/usr/local",
        "--ro-bind", "/bin", "/bin",
        "--ro-bind", "/sbin", "/sbin",
        "--ro-bind", "/lib", "/lib",
        "--ro-bind", "/lib64", "/lib64",
        "--ro-bind", "/etc", "/etc",
        "--dev", "/dev",
        "--proc", "/proc",
        "--tmpfs", "/tmp",
        "--tmpfs", "/home",
        "--dir", LAB_HOME,
        "--dir", LAB_TASK_ROOT,
        "--ro-bind", LAB_VENV, LAB_VENV,
        "--bind", task_dir, visible_task,
        "--setenv", "HOME", LAB_HOME,
        "--setenv", "PATH", f"{LAB_VENV}/bin:/usr/local/bin:/usr/bin:/bin",
        "--chdir", visible_task,
        "/bin/bash", "-c", command,
    ]
    started = time.monotonic()
    # The sandbox and the dedicated llama-server are on the Ryzen9 WSL host;
    # do not try to bind a remote path into the local Herdr host namespace.
    completed = run_ssh(shlex.join(args), lab=True, timeout=timeout, check=False)
    elapsed_ms = round((time.monotonic() - started) * 1000, 3)
    output = (completed.stdout + ("\n[stderr]\n" + completed.stderr if completed.stderr else ""))
    return {
        "task": task,
        "exit_code": completed.returncode,
        "timed_out": False,
        "elapsed_ms": elapsed_ms,
        "output": output,
        "stderr": completed.stderr,
    }


def append_checkpoint(path: Path, record: dict[str, Any]) -> None:
    """Append and fsync one event so a later sandbox failure cannot erase it."""
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def process_diagnostic(process: subprocess.Popen[bytes], stdout: bytes, stderr: bytes) -> dict[str, Any]:
    returncode = process.poll()
    signal_number = -returncode if returncode is not None and returncode < 0 else None
    try:
        signal_name = signal.Signals(signal_number).name if signal_number is not None else None
    except ValueError:
        signal_name = "unknown"
    return {
        "captured_at": now(),
        "ssh": {
            "pid": process.pid,
            "alive": returncode is None,
            "returncode": returncode,
            "signal": signal_number,
            "signal_name": signal_name,
        },
        "bwrap": {
            "state": "unknown",
            "reason": "bwrap runs inside the remote PID namespace and has no independent observable handle after SSH EOF",
        },
        "stdout_tail": stdout[-32768:].decode("utf-8", errors="replace"),
        "stderr": stderr[-32768:].decode("utf-8", errors="replace"),
    }


class RemoteSandboxFailure(RuntimeError):
    def __init__(self, message: str, diagnostic: dict[str, Any]) -> None:
        super().__init__(message)
        self.diagnostic = diagnostic


class GPUGateFailure(RuntimeError):
    def __init__(self, phase: str, state: dict[str, Any]) -> None:
        free_mib = state.get("memory_free_mib", "unknown")
        reason = "below threshold" if state.get("contaminated") else "unobservable"
        super().__init__(f"GPU gate failed during {phase}: free_mib={free_mib} ({reason})")
        self.phase = phase
        self.state = state


class ResponseChannelGateFailure(RuntimeError):
    def __init__(self, state: dict[str, Any]) -> None:
        super().__init__(
            "response channel gate failed: "
            f"defect_fraction={state.get('defect_fraction')} "
            f"limit={RESPONSE_CHANNEL_DEFECT_FRACTION_LIMIT}"
        )
        self.state = state


class RemoteSandbox:
    """One persistent shell per task, so background services survive turns."""

    def __init__(self, task: str, task_dir: str) -> None:
        self.task = task
        self.task_dir = task_dir
        self.visible_task = f"{LAB_TASK_ROOT}/{task}"
        args = [
            "bwrap",
            "--die-with-parent",
            "--unshare-pid",
            "--unshare-uts",
            "--unshare-ipc",
            "--ro-bind", "/usr", "/usr",
            "--ro-bind", "/usr/local", "/usr/local",
            "--ro-bind", "/bin", "/bin",
            "--ro-bind", "/sbin", "/sbin",
            "--ro-bind", "/lib", "/lib",
            "--ro-bind", "/lib64", "/lib64",
            "--ro-bind", "/etc", "/etc",
            "--dev", "/dev",
            "--proc", "/proc",
            "--tmpfs", "/tmp",
            "--tmpfs", "/home",
            "--dir", LAB_HOME,
            "--dir", LAB_TASK_ROOT,
            "--ro-bind", LAB_VENV, LAB_VENV,
            "--bind", task_dir, self.visible_task,
            "--setenv", "HOME", LAB_HOME,
            "--setenv", "PATH", f"{LAB_VENV}/bin:/usr/local/bin:/usr/bin:/bin",
            "--chdir", self.visible_task,
            "/bin/bash", "-s",
        ]
        remote_command = shlex.join(args)
        self.process = subprocess.Popen(
            ["ssh", *LAB_SSH_OPTIONS, f"{LAB_USER}@{REMOTE_HOST}", remote_command],
            text=False,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=0,
        )
        self.stderr_chunks: list[bytes] = []
        self.stderr_lock = threading.Lock()
        self.stderr_thread = threading.Thread(target=self._drain_stderr, daemon=True)
        self.stderr_thread.start()

    def _drain_stderr(self) -> None:
        if self.process.stderr is None:
            return
        while True:
            chunk = self.process.stderr.read(65536)
            if not chunk:
                return
            with self.stderr_lock:
                self.stderr_chunks.append(chunk)

    def _stderr_snapshot(self) -> bytes:
        with self.stderr_lock:
            return b"".join(self.stderr_chunks)

    def _diagnostic(self, stdout: bytes) -> dict[str, Any]:
        return process_diagnostic(self.process, stdout, self._stderr_snapshot())

    def run(self, inner: str, *, timeout: int = 300) -> dict[str, Any]:
        if self.process.stdin is None or self.process.stdout is None:
            raise RuntimeError("sandbox pipes unavailable")
        marker = f"__T87_DONE_{time.time_ns()}__"
        # Quote the model command as one eval argument.  This keeps shell
        # syntax such as ``command &`` valid instead of generating the
        # invalid ``&;`` sequence that killed v5.  eval runs in this
        # persistent shell so background services still survive subsequent
        # tool turns; ordinary non-zero/syntax errors return a tool result.
        script = (
            f"{{ cd {shlex.quote(self.visible_task)} && eval {shlex.quote(inner)}; rc=$?; "
            f"printf '\\n{marker}:%s\\n' \"$rc\"; }}\n"
        )
        stderr_before = len(self._stderr_snapshot())
        started = time.monotonic()
        try:
            self.process.stdin.write(script.encode("utf-8"))
            self.process.stdin.flush()
        except (BrokenPipeError, OSError) as exc:
            raise RemoteSandboxFailure(
                "remote sandbox stdin failed",
                self._diagnostic(b"") | {"failure_type": "stdin_error", "error": repr(exc)},
            ) from exc
        lines: list[bytes] = []
        deadline = time.monotonic() + timeout
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                stdout = b"".join(lines)
                raise RemoteSandboxFailure(
                    "remote sandbox command timed out",
                    self._diagnostic(stdout) | {"failure_type": "timeout", "timeout_seconds": timeout},
                )
            import select
            ready, _, _ = select.select([self.process.stdout], [], [], remaining)
            if not ready:
                stdout = b"".join(lines)
                raise RemoteSandboxFailure(
                    "remote sandbox command timed out",
                    self._diagnostic(stdout) | {"failure_type": "timeout", "timeout_seconds": timeout},
                )
            line = self.process.stdout.readline()
            if line == b"":
                stdout = b"".join(lines)
                try:
                    self.process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    pass
                self.stderr_thread.join(timeout=1)
                raise RemoteSandboxFailure(
                    "remote sandbox exited before command marker",
                    self._diagnostic(stdout) | {"failure_type": "eof_before_marker"},
                )
            if line.startswith((marker + ":").encode("utf-8")):
                exit_code = int(line.rstrip().split(b":", 1)[1])
                break
            lines.append(line)
        stderr_after = self._stderr_snapshot()[stderr_before:]
        stderr_text = stderr_after.decode("utf-8", errors="replace")
        output = b"".join(lines).decode("utf-8", errors="replace")
        if stderr_text:
            output += "\n[stderr]\n" + stderr_text
        return {
            "task": self.task,
            "exit_code": exit_code,
            "timed_out": False,
            "elapsed_ms": round((time.monotonic() - started) * 1000, 3),
            "output": output,
            "stderr": stderr_text,
        }

    def close(self) -> None:
        if self.process.poll() is not None:
            return
        try:
            if self.process.stdin is not None:
                self.process.stdin.write(b"exit\n")
                self.process.stdin.flush()
                self.process.stdin.close()
            self.process.wait(timeout=15)
        except (BrokenPipeError, OSError, subprocess.TimeoutExpired):
            self.process.kill()
            self.process.wait(timeout=15)

    def __enter__(self) -> "RemoteSandbox":
        return self

    def __exit__(self, _type: Any, _value: Any, _traceback: Any) -> None:
        self.close()


def run_tool(tool_call: dict[str, Any], sandbox: RemoteSandbox | dict[str, str]) -> dict[str, Any]:
    function = tool_call.get("function") or {}
    try:
        arguments = json.loads(function.get("arguments", "{}"))
        task, inner = parse_model_command(arguments.get("command"))
        if isinstance(sandbox, RemoteSandbox):
            if task != sandbox.task:
                raise ValueError("tool task differs from the active sandbox task")
            return sandbox.run(inner)
        return run_sandbox_command(task, inner, sandbox[task])
    except (ValueError, KeyError, json.JSONDecodeError) as exc:
        return {
            "exit_code": 126,
            "timed_out": False,
            "elapsed_ms": 0,
            "output": f"harness rejected command: {exc}",
            "stderr": "",
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "exit_code": 124,
            "timed_out": True,
            "elapsed_ms": None,
            "output": f"harness timeout: {exc}",
            "stderr": "",
        }


def message_text(message: dict[str, Any]) -> tuple[str, str]:
    """Return final text, falling back to reasoning only when no content exists."""
    content = message.get("content")
    if isinstance(content, str) and content.strip():
        return content, "content"
    reasoning = message.get("reasoning_content")
    if isinstance(reasoning, str) and reasoning.strip():
        return reasoning, "reasoning_content_fallback"
    return "", "none"


def response_channel_class(message: dict[str, Any]) -> str:
    """Classify response transport without parsing reasoning as executable text."""
    content = message.get("content")
    has_content = isinstance(content, str) and bool(content.strip())
    reasoning = message.get("reasoning_content")
    has_reasoning = isinstance(reasoning, str) and bool(reasoning.strip())
    has_tool_calls = bool(message.get("tool_calls") or [])
    if has_tool_calls and not has_content and has_reasoning:
        return "empty_content_reasoning_with_tool_call"
    if has_tool_calls and has_content:
        return "content_with_tool_call"
    if has_tool_calls:
        return "tool_call_without_text"
    if has_content and has_reasoning:
        return "content_with_reasoning_no_tool_call"
    if has_content:
        return "content_no_tool_call"
    if has_reasoning:
        return "reasoning_only_no_tool_call"
    return "empty_response_no_tool_call"


CHANNEL_DEFECT_CLASSES = {
    "reasoning_only_no_tool_call",
    "empty_response_no_tool_call",
}


def assistant_message(message: dict[str, Any]) -> dict[str, Any]:
    # Structured tool_calls is authoritative.  reasoning_content is retained
    # for context and diagnostics, never parsed as an executable command.
    result = {"role": "assistant", "content": message.get("content")}
    if message.get("reasoning_content") is not None:
        result["reasoning_content"] = message["reasoning_content"]
    if message.get("tool_calls"):
        result["tool_calls"] = message["tool_calls"]
    return result


def grade(task: str) -> dict[str, Any]:
    """Run the root-only wrapper so grading sees the protected checkout."""
    if task not in TASKS:
        raise ValueError(f"unknown task: {task}")
    command = f"sudo -n {shlex.quote(PRIVILEGED_GRADER)} {shlex.quote(task)}"
    result = run_ssh(command, timeout=300, check=False)
    return {
        "task": task,
        "command": command,
        "privilege": "sudo -n",
        "exit_code": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }


def run_task(task: str, prompt: str, seed: int, task_dirs: dict[str, str], out: Path) -> dict[str, Any]:
    user_prompt = prompt
    messages: list[dict[str, Any]] = [{"role": "user", "content": user_prompt}]
    tools = [{
        "type": "function",
        "function": {
            "name": "bash",
            "description": "Run one shell command on the writable lab task sandbox.",
            "parameters": {
                "type": "object",
                "properties": {"command": {"type": "string"}},
                "required": ["command"],
                "additionalProperties": False,
            },
        },
    }]
    raw: list[dict[str, Any]] = []
    response_channel_counts: dict[str, int] = {}
    cap = REFERENCE_TURNS[task]
    final_content: str | None = None
    status = "incomplete"
    checkpoint_path = out / f"{task}.checkpoint.jsonl"
    transcript_path = out / f"{task}.json"
    failure_path = out / f"{task}.failure.json"

    def persist_transcript(current_status: str) -> None:
        transcript = {
            "schema_version": "t87-p1-v2-transcript-v1",
            "harness_version": HARNESS_VERSION,
            "task": task,
            "seed": seed,
            "runtime": RUNTIME_ID,
            "route": ROUTE,
            "series_key": SERIES_KEY,
            "sampling": SAMPLING,
            "server_context_size": SERVER_CONTEXT_SIZE,
            "gpu_free_threshold_mib": GPU_FREE_THRESHOLD_MIB,
            "status": current_status,
            "generation_count": len(raw),
            "response_channel_counts": response_channel_counts,
            "response_channel_probe": {
                "probe_turns": RESPONSE_CHANNEL_PROBE_TURNS,
                "defect_fraction_limit": RESPONSE_CHANNEL_DEFECT_FRACTION_LIMIT,
                "defect_classes": sorted(CHANNEL_DEFECT_CLASSES),
            },
            "final_content": final_content,
            "turns": raw,
        }
        transcript_path.write_text(json.dumps(transcript, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    def require_gpu(phase: str, turn: int) -> dict[str, Any]:
        state = gpu_state()
        state["phase"] = phase
        state["turn"] = turn
        if not state.get("gate_passed"):
            raise GPUGateFailure(phase, state)
        return state

    def record_gpu_failure(exc: GPUGateFailure, turn: int) -> None:
        state = exc.state
        current_status = "contaminated_gpu" if state.get("contaminated") else "failed_gpu_gate"
        if raw:
            raw[-1]["gpu_gate_failure"] = state
        append_checkpoint(checkpoint_path, {
            "schema_version": "t87-p1-gpu-checkpoint-v1",
            "harness_version": HARNESS_VERSION,
            "event": "gpu_gate_failure",
            "task": task,
            "turn": turn,
            "generation_count": len(raw),
            "phase": exc.phase,
            "gpu_state": state,
            "captured_at": now(),
        })
        persist_transcript(current_status)
        failure_path.write_text(
            json.dumps({
                "schema_version": "t87-p1-gpu-failure-v1",
                "harness_version": HARNESS_VERSION,
                "task": task,
                "seed": seed,
                "turn": turn,
                "generation_count": len(raw),
                "phase": exc.phase,
                "status": current_status,
                "gpu_state": state,
            }, indent=2) + "\n",
            encoding="utf-8",
        )

    def record_response_channel_failure(exc: ResponseChannelGateFailure, turn: int) -> None:
        state = exc.state
        if raw:
            raw[-1]["response_channel_gate_failure"] = state
        append_checkpoint(checkpoint_path, {
            "schema_version": "t87-p1-response-channel-checkpoint-v1",
            "harness_version": HARNESS_VERSION,
            "event": "response_channel_gate_failure",
            "task": task,
            "turn": turn,
            "generation_count": len(raw),
            "response_channel": state,
            "captured_at": now(),
        })
        persist_transcript("failed_response_channel_gate")
        failure_path.write_text(
            json.dumps({
                "schema_version": "t87-p1-response-channel-failure-v1",
                "harness_version": HARNESS_VERSION,
                "task": task,
                "seed": seed,
                "turn": turn,
                "generation_count": len(raw),
                "status": "failed_response_channel_gate",
                "response_channel": state,
            }, indent=2) + "\n",
            encoding="utf-8",
        )

    with RemoteSandbox(task, task_dirs[task]) as sandbox:
        for turn in range(1, cap + 1):
            try:
                gpu_before = require_gpu("before_post", turn)
            except GPUGateFailure as exc:
                record_gpu_failure(exc, turn)
                raise
            payload = {
                "model": MODEL,
                "messages": messages,
                "tools": tools,
                "tool_choice": "auto",
                "seed": seed,
                **SAMPLING,
                "stream": False,
            }
            started = now()
            try:
                response = endpoint_post(payload)
            except (urllib.error.URLError, TimeoutError, OSError) as exc:
                raw.append({
                    "turn": turn,
                    "request": payload,
                    "error": repr(exc),
                    "started_at": started,
                    "gpu_before": gpu_before,
                })
                append_checkpoint(checkpoint_path, {
                    "schema_version": "t87-p1-post-checkpoint-v1",
                    "harness_version": HARNESS_VERSION,
                    "event": "post_error",
                    "turn": turn,
                    "generation_count": len(raw),
                    "request": payload,
                    "error": repr(exc),
                    "gpu_before": gpu_before,
                    "started_at": started,
                    "finished_at": now(),
                })
                break
            finished = now()
            raw.append({
                "turn": turn,
                "request": payload,
                "response": response,
                "started_at": started,
                "finished_at": finished,
                "gpu_before": gpu_before,
            })
            append_checkpoint(checkpoint_path, {
                "schema_version": "t87-p1-post-checkpoint-v1",
                "harness_version": HARNESS_VERSION,
                "event": "post_completed",
                "turn": turn,
                "generation_count": len(raw),
                "request": payload,
                "response": response,
                "gpu_before": gpu_before,
                "started_at": started,
                "finished_at": finished,
            })
            choices = response.get("choices") or []
            if not choices or not isinstance(choices[0].get("message"), dict):
                raw[-1]["response_channel"] = "invalid_response_shape"
                response_channel_counts["invalid_response_shape"] = response_channel_counts.get("invalid_response_shape", 0) + 1
                try:
                    gpu_after = require_gpu("after_turn", turn)
                except GPUGateFailure as exc:
                    record_gpu_failure(exc, turn)
                    raise
                raw[-1]["gpu_after"] = gpu_after
                append_checkpoint(checkpoint_path, {
                    "schema_version": "t87-p1-gpu-checkpoint-v1",
                    "harness_version": HARNESS_VERSION,
                    "event": "turn_completed",
                    "task": task,
                    "turn": turn,
                    "generation_count": len(raw),
                    "gpu_state": gpu_after,
                    "captured_at": now(),
                })
                break
            message = choices[0]["message"]
            channel_class = response_channel_class(message)
            response_channel_counts[channel_class] = response_channel_counts.get(channel_class, 0) + 1
            defect_count = sum(response_channel_counts.get(name, 0) for name in CHANNEL_DEFECT_CLASSES)
            channel_state = {
                "class": channel_class,
                "defect_count": defect_count,
                "turns_observed": turn,
                "defect_fraction": defect_count / turn,
                "probe_turns": RESPONSE_CHANNEL_PROBE_TURNS,
                "defect_fraction_limit": RESPONSE_CHANNEL_DEFECT_FRACTION_LIMIT,
                "action_source": "tool_calls" if message.get("tool_calls") else "none",
            }
            raw[-1]["response_channel"] = channel_state
            if turn <= RESPONSE_CHANNEL_PROBE_TURNS and channel_state["defect_fraction"] > RESPONSE_CHANNEL_DEFECT_FRACTION_LIMIT:
                try:
                    raise ResponseChannelGateFailure(channel_state)
                except ResponseChannelGateFailure as exc:
                    record_response_channel_failure(exc, turn)
                    raise
            messages.append(assistant_message(message))
            tool_calls = message.get("tool_calls") or []
            if not tool_calls:
                final_content, final_content_source = message_text(message)
                raw[-1]["final_content_source"] = final_content_source
                status = "incomplete_response_channel" if channel_class in CHANNEL_DEFECT_CLASSES else "complete"
                try:
                    gpu_after = require_gpu("after_turn", turn)
                except GPUGateFailure as exc:
                    record_gpu_failure(exc, turn)
                    raise
                raw[-1]["gpu_after"] = gpu_after
                append_checkpoint(checkpoint_path, {
                    "schema_version": "t87-p1-gpu-checkpoint-v1",
                    "harness_version": HARNESS_VERSION,
                    "event": "turn_completed",
                    "task": task,
                    "turn": turn,
                    "generation_count": len(raw),
                    "gpu_state": gpu_after,
                    "captured_at": now(),
                })
                break
            for tool_call in tool_calls:
                try:
                    result = run_tool(tool_call, sandbox)
                except RemoteSandboxFailure as exc:
                    raw[-1]["sandbox_failure"] = exc.diagnostic
                    append_checkpoint(checkpoint_path, {
                        "schema_version": "t87-p1-post-checkpoint-v1",
                        "harness_version": HARNESS_VERSION,
                        "event": "sandbox_failure",
                        "turn": turn,
                        "generation_count": len(raw),
                        "diagnostic": exc.diagnostic,
                        "captured_at": now(),
                    })
                    persist_transcript("failed_sandbox")
                    failure_path.write_text(
                        json.dumps({
                            "schema_version": "t87-p1-sandbox-failure-v1",
                            "harness_version": HARNESS_VERSION,
                            "task": task,
                            "seed": seed,
                            "turn": turn,
                            "generation_count": len(raw),
                            "diagnostic": exc.diagnostic,
                        }, indent=2) + "\n",
                        encoding="utf-8",
                    )
                    raise
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.get("id", "unknown"),
                    "content": json.dumps(result, ensure_ascii=False),
                })
            try:
                gpu_after = require_gpu("after_turn", turn)
            except GPUGateFailure as exc:
                record_gpu_failure(exc, turn)
                raise
            raw[-1]["gpu_after"] = gpu_after
            append_checkpoint(checkpoint_path, {
                "schema_version": "t87-p1-gpu-checkpoint-v1",
                "harness_version": HARNESS_VERSION,
                "event": "turn_completed",
                "task": task,
                "turn": turn,
                "generation_count": len(raw),
                "gpu_state": gpu_after,
                "captured_at": now(),
            })
    persist_transcript(status)
    grade_result = grade(task)
    return {"task": task, "status": status, "generation_count": len(raw), "grade": grade_result, "transcript": str(transcript_path)}


def write_preparation(out: Path) -> None:
    out.mkdir(parents=True, exist_ok=False)
    global SERIES_KEY
    environment = lab_environment_identity()
    SERIES_KEY = build_series_key(environment)
    prompts, prompt_sha = fetch_prompt_packet()
    identity = server_identity(environment)
    harness_path = Path(__file__).resolve()
    protocol_path = harness_path.parent.parent / "docs/en/plans/t87-p1-protocol-v2-2026-09-18.md"
    (out / "published-prompts.md").write_text(
        remote_text(f"{REMOTE_SOURCE}/docs/prompts.md"), encoding="utf-8"
    )
    packet = {
        "schema_version": "t87-p1-v2-preparation-v1",
        "harness_version": HARNESS_VERSION,
        "status": "prepared_no_generation",
        "created_at": now(),
        "endpoint_identity": identity,
        "route": ROUTE,
        "series_key": SERIES_KEY,
        "environment": environment,
        "benchmark_commit": BENCHMARK_COMMIT,
        "harness_sha256": sha256_file(harness_path),
        "protocol_sha256": sha256_file(protocol_path),
        "dependency_fingerprint": environment["dependency_fingerprint"],
        "installed_dependency_fingerprint": environment["installed_dependency_fingerprint"],
        "setup_sha256": environment["setup_sha256"],
        "reset_sha256": environment["reset_sha256"],
        "prompt_sha256": prompt_sha,
        "task_count": len(TASKS),
        "grader_denominator": 17,
        "seeds": list(SEEDS),
        "reference_turn_caps": REFERENCE_TURNS,
        "max_generation_count": sum(REFERENCE_TURNS.values()) * len(SEEDS),
        "sampling": SAMPLING,
        "server_context_size": SERVER_CONTEXT_SIZE,
        "gpu_free_threshold_mib": GPU_FREE_THRESHOLD_MIB,
        "response_channel_probe_turns": RESPONSE_CHANNEL_PROBE_TURNS,
        "response_channel_defect_fraction_limit": RESPONSE_CHANNEL_DEFECT_FRACTION_LIMIT,
        "response_channel_defect_classes": sorted(CHANNEL_DEFECT_CLASSES),
        "response_action_source": "message.tool_calls; reasoning_content is never parsed as executable text",
        "model_post_sent": False,
        "prompts": {task: sha256_bytes(prompts[task].encode("utf-8")) for task in TASKS},
    }
    (out / "preparation.json").write_text(json.dumps(packet, indent=2) + "\n", encoding="utf-8")
    (out / "preparation.sha256").write_text(sha256_file(out / "preparation.json") + "  preparation.json\n", encoding="utf-8")
    for task in TASKS:
        (out / f"{task}.prompt.sha256").write_text(packet["prompts"][task] + "  {task}\n".format(task=task), encoding="utf-8")
    print(json.dumps(packet, indent=2))


def run_campaign(out: Path) -> None:
    global SERIES_KEY
    preparation = json.loads((out / "preparation.json").read_text(encoding="utf-8"))
    if preparation.get("model_post_sent"):
        raise SystemExit("refusing to reuse a preparation packet that already records POSTs")
    environment = lab_environment_identity()
    current_series_key = build_series_key(environment)
    if current_series_key != preparation.get("series_key"):
        raise SystemExit("preflight failed: labuser environment or series key changed after preparation")
    SERIES_KEY = current_series_key
    current_identity = server_identity(environment)
    expected_identity = preparation.get("endpoint_identity", {})
    if current_identity.get("health", {}).get("status") != "ok":
        raise SystemExit("preflight failed: endpoint health is not ok")
    current_ids = [item.get("id") for item in current_identity.get("models", {}).get("data", [])]
    if MODEL not in current_ids:
        raise SystemExit("preflight failed: expected GGUF is not the active model")
    if current_identity.get("model_sha256") != expected_identity.get("model_sha256"):
        raise SystemExit("preflight failed: model hash changed")
    if current_identity.get("binary_sha256") != expected_identity.get("binary_sha256"):
        raise SystemExit("preflight failed: binary hash changed")
    gpu = current_identity.get("gpu_state", {})
    if not gpu.get("gate_passed"):
        raise SystemExit(
            "preflight failed: GPU free-memory gate did not pass "
            f"(free_mib={gpu.get('memory_free_mib', 'unknown')}, "
            f"threshold_mib={GPU_FREE_THRESHOLD_MIB}, observable={gpu.get('observable')})"
        )
    (out / "preflight.json").write_text(
        json.dumps({"schema_version": "t87-p1-v2-preflight-v1", "captured_at": now(), "identity": current_identity}, indent=2) + "\n",
        encoding="utf-8",
    )
    prompts, prompt_sha = fetch_prompt_packet()
    if prompt_sha != preparation["prompt_sha256"]:
        raise SystemExit("published prompts changed after preparation")
    campaign_id = f"{HARNESS_VERSION}-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{os.getpid()}"
    (out / "campaign-start.json").write_text(
        json.dumps({
            "schema_version": "t87-p1-campaign-start-v1",
            "campaign_id": campaign_id,
            "harness_version": HARNESS_VERSION,
            "series_key": SERIES_KEY,
            "created_at": now(),
            "gpu_free_threshold_mib": GPU_FREE_THRESHOLD_MIB,
            "new_generation_budget": sum(REFERENCE_TURNS.values()) * len(SEEDS),
        }, indent=2) + "\n",
        encoding="utf-8",
    )
    all_runs: list[dict[str, Any]] = []
    for index, seed in enumerate(SEEDS, 1):
        run_id = f"{campaign_id}-run-{index}-{seed}"
        run_out = out / run_id
        run_out.mkdir()
        task_dirs, reset_record = reset_lab(run_id)
        (run_out / "reset.json").write_text(json.dumps(reset_record, indent=2) + "\n", encoding="utf-8")
        run_record = {
            "run_id": run_id,
            "campaign_id": campaign_id,
            "seed": seed,
            "harness_version": HARNESS_VERSION,
            "runtime": RUNTIME_ID,
            "route": ROUTE,
            "series_key": SERIES_KEY,
            "environment": environment,
            "gpu_free_threshold_mib": GPU_FREE_THRESHOLD_MIB,
            "task_dirs": task_dirs,
            "tasks": [],
        }
        for task in TASKS:
            run_record["tasks"].append(run_task(task, prompts["preamble"] + "\n\n" + prompts[task], seed, task_dirs, run_out))
        (run_out / "run.json").write_text(json.dumps(run_record, indent=2) + "\n", encoding="utf-8")
        all_runs.append(run_record)
    assert_single_series(all_runs)
    result = {
        "schema_version": "t87-p1-v2-result-v1",
        "harness_version": HARNESS_VERSION,
        "completed_at": now(),
        "runtime": RUNTIME_ID,
        "route": ROUTE,
        "series_key": SERIES_KEY,
        "runs": all_runs,
    }
    (out / "result.json").write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    prep = sub.add_parser("prepare")
    prep.add_argument("--out", type=Path, required=True)
    run = sub.add_parser("run")
    run.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "prepare":
        write_preparation(args.out)
    else:
        run_campaign(args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
