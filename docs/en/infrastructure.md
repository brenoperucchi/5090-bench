# Benchmark infrastructure

**English** | [Português (Brasil)](../infraestrutura.md) · [English index](README.md)

> **Historical operational snapshot — through 2026-09-12.**
> This document describes the earlier Windows/Ollama production baseline.
> For the current Guardian research campaign and the WSL/llama.cpp environment,
> see [the current public record](findings/public-record-llm-bench-2026-09-20.md).

This page describes the state recorded in the [September 12, 2026 handoff](../history/handoff-2026-09-12.md)
and the [production decision](../../results/DECISAO-producao-2026-09-09.md).
Ollama was not queried while organizing this archive.

| Component | Recorded state |
|---|---|
| GPU | NVIDIA GeForce RTX 5090, 32 GB; approximately 30.3 GiB usable in the documented scenario |
| Server | Ryzen9, native Windows, Ollama 0.33.3 |
| Startup | `OllamaServer` task running as SYSTEM |
| Access from this workstation | SSH tunnel with local endpoint `127.0.0.1:11434` |
| Model store | `E:\ollama\models`; old copies on C: and D: removed |
| Default model | `qwen3:14b` |
| Configured second resident model | `qwen3.5:9b` |
| `OLLAMA_MAX_LOADED_MODELS` | `2` |
| `OLLAMA_NUM_PARALLEL` | `2` |
| `OLLAMA_KV_CACHE_TYPE` | `q8_0` |
| `OLLAMA_CONTEXT_LENGTH` | Unset; automatic context depends on the environment and is not a per-request guarantee |
| `OLLAMA_FLASH_ATTENTION` | Unset |

The [original runbook](../../MIGRACAO-windows-nativo-2026-09-04.md) preserves the
migration from WSL2 to native Windows, diagnostics, and task configuration.
The [PowerShell script](../../ollama-restart.ps1) changes server processes and
should not be treated as a generic installation command.

## Memory and interference between measurements

`gemma4:26b` does not coexist with `qwen3:14b` in the available VRAM: loading one
evicted the other. On the shared benchmark server, the recorded agreement
requires arranging a window with `llm-exec` **before** loading Gemma.
`qwen3.5:9b` fits alongside the default. After a measurement that changed
residency, the recorded procedure is to unload the temporary model with
`keep_alive:0` and reload `qwen3:14b`.
[Source](../../results/RESULTADO-juiz-familia-2026-09-10.md).

For the speculative Gemma model, `/api/ps` reports only approximately 1.38 GiB,
omitting the main cost. The Phase 6 spill check still has a TODO; equality
between `size` and `size_vram` does not validate that residency. Layer counts
in the log were the evidence used.
[Code and caveat](../../baseline-3080ti/repro/fase6_concurrency.py).

## Long context

The observed case records 111,288 input tokens, a limit of 49,154, and
`keep=4`, with 98,304-token slots. Requested `num_ctx`, allocation per slot,
input limit, and tokens actually evaluated are distinct quantities.
The [Phase 6b correction](../../results/RESULTADO-fase6b-numparallel-contexto-longo-2026-09-12.md)
leaves the causal mechanism unresolved. The proposed configuration change to
test it requires a separate decision; it is not part of this documentation work.

## Portability

The endpoints, task names, and Windows paths in historical scripts describe
this benchmark environment. Old tool-calling scripts also import an external
`llm-gateway` checkout. Consult the [methodology](methodology.md) before reusing a
harness. Data from the older GPU and CPU are identified in the
[catalog](benchmarks.md).
