#!/usr/bin/env python3
"""Bounded serial performance arms for Ollama versus llama.cpp.

This runner deliberately executes one runtime at a time.  It records each arm
as its own runtime/route series; a comparison may report paired medians, but
must not merge the raw series as if they were one runtime.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import statistics
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


OLLAMA_BASE = "http://192.168.0.125:11434"
LLAMA_BASE = "http://192.168.0.125:18087"
OLLAMA_MODEL = "qwen3.6:35b-a3b"
LLAMA_MODEL = "/mnt/e/llm-bench-t87-p1/models/qwen3.6-35b-a3b-q4_k_m.gguf"
MODEL_LOGICAL_ID = "qwen3.6-35b-a3b-q4_k_m"
OLLAMA_TAG_DIGEST = "096fdbd02fe620fc10cbeb6537e080f8041aece851e5d696aed024d4f70f2e47"
LLAMA_GGUF_SHA256 = "d372de8e934898a59e6ccfabc3368474711384d8f1fd4d22d87a3f0a45400cdc"
LLAMA_BINARY_SHA256 = "37acf8e80c85f91794d9fa0268d34b40dbfa2f4286527a92bdd13dfefdab689b"
RUNTIME_COMPARISON = "runtime_plus_artifact_not_pure_runtime"
NUM_CTX = 32768
NUM_PREDICT = 256
CONTEXT_MARGIN = 1024
MAX_PROMPT_TOKENS = NUM_CTX - NUM_PREDICT - CONTEXT_MARGIN
TOKEN_COUNT_TOLERANCE = 128
TEMPERATURE = 0.0
SEED = 42
TOP_P = 1.0
TOP_K = 0


def offload_config(runtime: str) -> dict[str, str]:
    """Identity fields that make placement changes a new measurement series."""
    if runtime == "ollama":
        return {field: "not_applicable" for field in (
            "cpu_moe", "n_cpu_moe", "moe_cache_slots", "moe_cache_profile",
            "load_mode", "n_gpu_layers",
        )}
    return {
        "cpu_moe": os.environ.get("LLAMA_CPU_MOE", "unknown"),
        "n_cpu_moe": os.environ.get("LLAMA_N_CPU_MOE", "unknown"),
        "moe_cache_slots": os.environ.get("LLAMA_MOE_CACHE_SLOTS", "unknown"),
        "moe_cache_profile": os.environ.get("LLAMA_MOE_CACHE_PROFILE", "unknown"),
        "load_mode": os.environ.get("LLAMA_LOAD_MODE", "unknown"),
        "n_gpu_layers": os.environ.get("LLAMA_N_GPU_LAYERS", "unknown"),
    }


def now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def request_json(url: str, payload: dict[str, Any] | None = None, timeout: int = 300) -> dict[str, Any]:
    if payload is None:
        request = urllib.request.Request(url, method="GET")
    else:
        request = urllib.request.Request(
            url,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def canonical_prompt_set(prompts: dict[str, str]) -> str:
    return json.dumps(prompts, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def tokenize_with_llama(prompt: str) -> int:
    body = request_json(
        f"{LLAMA_BASE}/tokenize",
        {"content": prompt, "add_special": True},
        timeout=30,
    )
    tokens = body.get("tokens")
    if not isinstance(tokens, list):
        raise RuntimeError(f"llama.cpp tokenize response missing tokens: {body!r}")
    return len(tokens)


def build_prompts() -> dict[str, str]:
    def rows(count: int) -> str:
        return "\n".join(
            f"Registro {index:04d}: categoria={index % 7}; valor={index * 13}; status=observado."
            for index in range(1, count + 1)
        )

    return {
        "short": "Responda em uma linha: quais são as três cores primárias?",
        "medium": (
            "Leia os registros abaixo e responda apenas com a soma dos valores dos "
            "registros de categoria 3.\n\n" + rows(64)
        ),
        "long": (
            "Leia os registros abaixo. Responda apenas com a soma dos valores dos "
            "registros de categoria 5 e a quantidade desses registros.\n\n" + rows(512)
        ),
        "context_heavy": (
            "Leia os registros abaixo. Responda apenas com a soma dos valores dos "
            "registros de categoria 2 e a quantidade desses registros.\n\n" + rows(512)
        ),
    }


def prepare_prompt_manifest(output: Path) -> dict[str, Any]:
    prompts = build_prompts()
    entries: dict[str, Any] = {}
    for name, prompt in prompts.items():
        token_count = tokenize_with_llama(prompt)
        if token_count + NUM_PREDICT + CONTEXT_MARGIN > NUM_CTX:
            raise RuntimeError(
                f"prompt {name} exceeds common context budget: "
                f"{token_count} + {NUM_PREDICT} + {CONTEXT_MARGIN} > {NUM_CTX}"
            )
        entries[name] = {
            "sha256": sha256_text(prompt),
            "chars": len(prompt),
            "llama_token_count": token_count,
            "max_allowed_tokens": MAX_PROMPT_TOKENS,
        }
    manifest = {
        "schema_version": "qwen36-runtime-ab-prompt-manifest-v2",
        "created_at": now(),
        "tokenizer_runtime": "llama_cpp",
        "tokenizer_endpoint": f"{LLAMA_BASE}/tokenize",
        "num_ctx": NUM_CTX,
        "num_predict": NUM_PREDICT,
        "context_margin": CONTEXT_MARGIN,
        "max_prompt_tokens": MAX_PROMPT_TOKENS,
        "prompt_set_sha256": sha256_text(canonical_prompt_set(prompts)),
        "prompts": entries,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return manifest


def load_prompt_manifest(path: Path, prompts: dict[str, str]) -> dict[str, Any]:
    manifest = json.loads(path.read_text(encoding="utf-8"))
    expected = {
        name: {
            "sha256": sha256_text(prompt),
            "chars": len(prompt),
        }
        for name, prompt in prompts.items()
    }
    actual = {
        name: {
            "sha256": data.get("sha256"),
            "chars": data.get("chars"),
        }
        for name, data in manifest.get("prompts", {}).items()
    }
    if actual != expected:
        raise RuntimeError("prompt manifest does not match the prompts used by this harness")
    if manifest.get("num_ctx") != NUM_CTX or manifest.get("num_predict") != NUM_PREDICT:
        raise RuntimeError("prompt manifest context parameters do not match the harness")
    for name, data in manifest["prompts"].items():
        count = data.get("llama_token_count")
        if not isinstance(count, int) or count + NUM_PREDICT + CONTEXT_MARGIN > NUM_CTX:
            raise RuntimeError(f"prompt manifest is not within the common context budget: {name}")
    return manifest


def validate_observed_prompt_tokens(item: dict[str, Any], expected: int, runtime: str) -> None:
    observed = item.get("prompt_tokens")
    if observed is None:
        return
    if observed > MAX_PROMPT_TOKENS:
        raise RuntimeError(
            f"{runtime} reported prompt_tokens={observed}, above the common budget {MAX_PROMPT_TOKENS}"
        )
    if observed + TOKEN_COUNT_TOLERANCE < expected:
        raise RuntimeError(
            f"{runtime} appears to have truncated the input: observed {observed}, "
            f"expected at least {expected - TOKEN_COUNT_TOLERANCE}"
        )


def route(runtime: str) -> dict[str, Any]:
    if runtime == "ollama":
        return {"id": "lan", "scheme": "http", "host": "192.168.0.125", "port": 11434, "path": "/api/chat"}
    return {"id": "lan", "scheme": "http", "host": "192.168.0.125", "port": 18087, "path": "/v1/chat/completions"}


def preflight(runtime: str) -> dict[str, Any]:
    if runtime == "ollama":
        version = request_json(f"{OLLAMA_BASE}/api/version", timeout=15)
        tags = request_json(f"{OLLAMA_BASE}/api/tags", timeout=30)
        ps = request_json(f"{OLLAMA_BASE}/api/ps", timeout=15)
        model = next((item for item in tags.get("models", []) if item.get("name") == OLLAMA_MODEL), None)
        if model is None:
            raise RuntimeError(f"Ollama model not found: {OLLAMA_MODEL}")
        return {"version": version, "model": model, "residency": ps}

    health = request_json(f"{LLAMA_BASE}/health", timeout=15)
    models = request_json(f"{LLAMA_BASE}/v1/models", timeout=30)
    model = next((item for item in models.get("data", []) if item.get("id") == LLAMA_MODEL), None)
    if model is None:
        raise RuntimeError(f"llama.cpp model not found: {LLAMA_MODEL}")
    return {"health": health, "models": models, "model": model}


def call(runtime: str, prompt: str) -> tuple[dict[str, Any], float]:
    messages = [{"role": "user", "content": prompt}]
    started = time.perf_counter()
    if runtime == "ollama":
        body = request_json(
            f"{OLLAMA_BASE}/api/chat",
            {
                "model": OLLAMA_MODEL,
                "messages": messages,
                "stream": False,
                "keep_alive": "10m",
                "options": {
                    "temperature": TEMPERATURE,
                    "top_p": TOP_P,
                    "top_k": TOP_K,
                    "seed": SEED,
                    "num_ctx": NUM_CTX,
                    "num_predict": NUM_PREDICT,
                },
            },
        )
    else:
        body = request_json(
            f"{LLAMA_BASE}/v1/chat/completions",
            {
                "model": LLAMA_MODEL,
                "messages": messages,
                "stream": False,
                "temperature": TEMPERATURE,
                "top_p": TOP_P,
                "seed": SEED,
                "max_tokens": NUM_PREDICT,
            },
        )
    elapsed = time.perf_counter() - started
    return body, elapsed


def metrics(runtime: str, body: dict[str, Any], elapsed: float) -> dict[str, Any]:
    if runtime == "ollama":
        return {
            "wall_s": elapsed,
            "prompt_tokens": body.get("prompt_eval_count"),
            "completion_tokens": body.get("eval_count"),
            "prompt_tok_s": (
                body["prompt_eval_count"] / (body["prompt_eval_duration"] / 1e9)
                if body.get("prompt_eval_count") and body.get("prompt_eval_duration") else None
            ),
            "decode_tok_s": (
                body["eval_count"] / (body["eval_duration"] / 1e9)
                if body.get("eval_count") and body.get("eval_duration") else None
            ),
            "load_s": (body.get("load_duration", 0) or 0) / 1e9,
            "response_text": (body.get("message") or {}).get("content", ""),
        }

    choice = (body.get("choices") or [{}])[0]
    usage = body.get("usage") or {}
    timings = body.get("timings") or {}
    return {
        "wall_s": elapsed,
        "prompt_tokens": usage.get("prompt_tokens"),
        "completion_tokens": usage.get("completion_tokens"),
        "prompt_tok_s": timings.get("prompt_per_second"),
        "decode_tok_s": timings.get("predicted_per_second"),
        "load_s": None,
        "response_text": (choice.get("message") or {}).get("content", ""),
    }


def run_arm(runtime: str, output: Path, reps: int, manifest_path: Path) -> None:
    prompts = build_prompts()
    manifest = load_prompt_manifest(manifest_path, prompts)
    identity = preflight(runtime)
    series_key = json.dumps(
        {
            "runtime": runtime,
            "model": MODEL_LOGICAL_ID,
            "route": route(runtime),
            "offload_config": offload_config(runtime),
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    records: list[dict[str, Any]] = []

    for name, prompt in prompts.items():
        started = now()
        try:
            body, elapsed = call(runtime, prompt)
            item = metrics(runtime, body, elapsed)
            validate_observed_prompt_tokens(item, manifest["prompts"][name]["llama_token_count"], runtime)
            error = None
        except (urllib.error.URLError, OSError, ValueError, KeyError) as exc:
            item, error = {}, f"{type(exc).__name__}: {exc}"
        records.append({
            "phase": "warmup",
            "prompt": name,
            "prompt_sha256": sha256_text(prompt),
            "prompt_tokens_expected_llama": manifest["prompts"][name]["llama_token_count"],
            "started_at": started,
            "error": error,
            **item,
        })
        if error:
            raise RuntimeError(f"warmup failed for {runtime}/{name}: {error}")

    for rep in range(1, reps + 1):
        for name, prompt in prompts.items():
            started = now()
            try:
                body, elapsed = call(runtime, prompt)
                item = metrics(runtime, body, elapsed)
                validate_observed_prompt_tokens(item, manifest["prompts"][name]["llama_token_count"], runtime)
                error = None
            except (urllib.error.URLError, OSError, ValueError, KeyError) as exc:
                item, error = {}, f"{type(exc).__name__}: {exc}"
            records.append({
                "phase": "measurement",
                "rep": rep,
                "prompt": name,
                "prompt_sha256": sha256_text(prompt),
                "prompt_tokens_expected_llama": manifest["prompts"][name]["llama_token_count"],
                "started_at": started,
                "error": error,
                **item,
            })

    measurement_errors = [item["error"] for item in records if item["phase"] == "measurement" and item.get("error")]
    if measurement_errors:
        raise RuntimeError(f"measurement input or request validation failed: {measurement_errors[0]}")

    output.mkdir(parents=True, exist_ok=False)
    artifact = {
        "schema_version": "qwen36-runtime-ab-v1",
        "status": "measured",
        "created_at": now(),
        "runtime": runtime,
        "comparison_scope": RUNTIME_COMPARISON,
        "model_logical_id": MODEL_LOGICAL_ID,
        "artifact_identity": {
            "ollama_tag_digest": OLLAMA_TAG_DIGEST if runtime == "ollama" else None,
            "llama_gguf_sha256": LLAMA_GGUF_SHA256 if runtime == "llama_cpp" else None,
            "llama_binary_sha256": LLAMA_BINARY_SHA256 if runtime == "llama_cpp" else None,
        },
        "route": route(runtime),
        "series_key": series_key,
        "parameters": {
            "num_ctx": NUM_CTX,
            "num_predict": NUM_PREDICT,
            "context_margin": CONTEXT_MARGIN,
            "max_prompt_tokens": MAX_PROMPT_TOKENS,
            "temperature": TEMPERATURE,
            "top_p": TOP_P,
            "top_k": TOP_K,
            "seed": SEED,
            "repetitions": reps,
            "thinking_control": "default; not normalized across runtimes",
        },
        "preflight": identity,
        "prompt_manifest": manifest,
        "prompts": {name: {"sha256": sha256_text(prompt), "chars": len(prompt)} for name, prompt in prompts.items()},
        "records": records,
    }
    (output / f"{runtime}.json").write_text(json.dumps(artifact, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    measured = [item for item in records if item["phase"] == "measurement" and not item.get("error")]
    summary: dict[str, Any] = {"runtime": runtime, "route": route(runtime), "series_key": series_key, "prompts": {}}
    for name in prompts:
        rows = [item for item in measured if item["prompt"] == name]
        summary["prompts"][name] = {
            key: statistics.median([row[key] for row in rows if row.get(key) is not None]) if any(row.get(key) is not None for row in rows) else None
            for key in ("wall_s", "prompt_tok_s", "decode_tok_s", "prompt_tokens", "completion_tokens")
        }
    (output / f"{runtime}.summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime", choices=("ollama", "llama_cpp"), required=True)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--prepare-manifest", type=Path)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--reps", type=int, default=5)
    args = parser.parse_args()
    if args.prepare_manifest:
        if args.runtime != "llama_cpp":
            raise SystemExit("--prepare-manifest requires --runtime llama_cpp")
        prepare_prompt_manifest(args.prepare_manifest)
        print(args.prepare_manifest)
        return 0
    if args.out is None:
        raise SystemExit("--out is required when running an arm")
    if args.manifest is None:
        raise SystemExit("--manifest is required when running an arm")
    if args.reps != 5:
        raise SystemExit("this authorized A/B requires exactly 5 measured repetitions")
    run_arm(args.runtime, args.out, args.reps, args.manifest)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
