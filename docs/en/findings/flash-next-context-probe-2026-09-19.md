# Flash-Next context probe — suspended

Status: suspended by owner on 2026-09-19 after the context-scan priority was
withdrawn. No 32k/65k/131k/262k configurations were started.

Runtime: `/home/brenoperucchi/t87-runtime/codacus-build-new/bin/llama-server`
with the Flash-Next UD-IQ3_XXS GGUF, `--n-gpu-layers 999`, `--fit off`,
`--flash-attn on`, `--parallel 1`, `--verbosity 4`, and `--load-mode mmap`.

## Completed evidence

| MoE offload | Context | Load | KV reported | Memory at health | Generation |
|---|---:|---|---|---|---|
| `--n-cpu-moe 32` | 4096 | health OK after ~4m20s | main 96 MiB + indexer 36 MiB = 132 MiB; 12 layers, one slot | 22,165 MiB VRAM used / 10,026 MiB free; RSS ~17.8 GiB | 4 JSON responses complete; warmup 15.46 tok/s; hot median 26.74 tok/s; 1533 tokens; `stop` |
| `--n-cpu-moe 32` | 16384 | health OK after ~4m17s | main 384 MiB + indexer 144 MiB = 528 MiB; 12 layers, one slot | 22,165 MiB VRAM used / 10,026 MiB free; RSS ~17.8 GiB | generation 0 started, then scan was suspended; no valid 4-response throughput result |

The 4096 generation request recorded explicit `temperature=0`, `top_p=0.95`,
`top_k=20`, `seed=42`, and `max_tokens=2048`; prompt SHA-256 was
`6653ec984a1d4c4a798c88cd6e474d0a9bce7aab0886eaec8520bed57b686c84`.

The 16384 instance was stopped after the owner withdrew the scan priority. Its
load log and KV allocation are valid load evidence; the interrupted generation
is not a speed measurement.

## Interpretation boundary

These data do not establish the maximum context. The 16384 load was healthy,
but larger contexts were not tested. No context-scan conclusion should be
aggregated with throughput series until the owner reopens this probe.
