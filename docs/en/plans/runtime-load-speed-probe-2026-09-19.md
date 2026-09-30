# Runtime load/speed probe — 2026-09-19

Owner authorization: 2026-09-19T06:29:36Z. This record covers only model loading and one short decode probe. It is not a benchmark, does not run spec-wins, and does not compare quality.

All measurements used the LAN route `192.168.0.125:18087`, one runtime on the RTX 5090 at a time, `--ctx-size 32768`, `--n-gpu-layers 999`, `--flash-attn on`, `--parallel 1`, `--metrics`, and `--no-webui`. The decode probe used the same request shape: `temperature=0`, `seed=42`, `cache_prompt=false`, `n_predict=128`.

## Runtime and artifact identity

The Prism build was isolated at `/mnt/e/llm-bench-t87-runtimes/prism-build`, commit `9a9394a895b96003ca842a6041cb28ac49a108f7`, CUDA `120a-real`, and binary SHA-256 `36b64dfc62d077f99b65d4b6da0e1b906bfecde14285aa69647119d5fa4c32e7`.

The Codacus binary already present on the Ryzen9 was used for both Qwen artifacts. Its binary SHA-256 is `37acf8e80c85f91794d9fa0268d34b40dbfa2f4286527a92bdd13dfefdab689b`; its recorded CMake configuration is CUDA `120a-real`, CUDA graphs on, and flash attention on. The binary hash is the provenance anchor; no source commit was inferred for that pre-existing binary.

Each row has its own `series_key`; no rows are aggregate-compatible merely because they share a route or binary.

| Model | Runtime / artifact | series_key | Artifact SHA-256 | Load | Decode |
|---|---|---|---|---|---|
| Ternary Bonsai 2 27B PTQ1_0 | PrismML/llama.cpp + PTQ1_0 GGUF + Q8_0 mmproj | `load-speed-20260919|lan-192.168.0.125:18087|prismml-llama.cpp|artifact=bonsai-ptq1_0` | `53107f530aa52eb00912263ab1ee29bd199261c87cd7b4ad4ca1318c1fe33ee3` (model); `6807ede61d570bb86ba34b756a0fa109edc33668604de867c6ea6d8f1d631903` (mmproj) | **yes**, 32.797 s from server log | **111.79 tok/s** decode; prompt 44.44 tok/s |
| Qwen3.8 27B UD-Q5_K_XL | thecodacus/llama.cpp + standalone GGUF | `load-speed-20260919|lan-192.168.0.125:18087|thecodacus-llama.cpp|artifact=qwen38-27b-ud-q5-k-xl` | `8601193d3d5760c37fb8ce1b43afebc69df5fb24e1fbc5a547c32e2200305276` | **yes**, 153.540 s from server log | **62.16 tok/s** decode; prompt 40.31 tok/s |
| Qwen3.8 Flash-Next UD-IQ3_XXS | thecodacus/llama.cpp + 3-shard standalone GGUF | `load-speed-20260919|lan-192.168.0.125:18087|thecodacus-llama.cpp|artifact=qwen38-flash-next-ud-iq3-xxs` | `268f81fdedf3149a538f252308927a4d5d1f6e062c178568a51e3b519744f8a8` (shard 1); `cfe600b236b88c7fad1613a5ca5e83b9f2beb63cbd44c32b2be50a44747c695f` (shard 2); `f1912ba34c79427d2295a58dcb2b732b5931af5bef7a373c60557a57d9ee7250` (shard 3) | **no**: 215.653 s until literal CUDA OOM | not measured |

The Qwen3.8 Flash-Next row is a new load probe. It is not a reproduction of the published 17/17 result; provenance of that published artifact remains ambiguous.

## Observed resource state

For Bonsai, the loaded snapshot was 10,088 MiB VRAM used of 32,607 MiB; after the probe it was 10,094 MiB. System RAM went from 2,229,010,432 bytes used at load to 2,429,960,192 bytes after the probe. The server RSS after the probe was 1,185,272 KiB.

For Qwen3.8 27B, the loaded snapshot was 22,322 MiB VRAM used; after the probe it was 22,330 MiB. System RAM went from 2,087,063,552 bytes used at load to 2,301,157,376 bytes after the probe. The server RSS after the probe was 1,802,336 KiB.

Flash-Next began with 838 MiB VRAM used and 49,006,067,712 bytes free system RAM. It failed before model residency. After cleanup, VRAM was 838 MiB used and no llama-server process or listener remained.

## Flash-Next failure

The literal runtime evidence is:

```text
failed to fit params to free device memory: n_gpu_layers already set by user to 999, abort
allocating 50191.17 MiB on device 0: cudaMalloc failed: out of memory
failed to allocate CUDA0 buffer of size 52629255424
error loading model: unable to allocate CUDA0 buffer
```

No fallback layer count or alternate runtime was tried. This result answers only that the downloaded Flash-Next artifact did not load under the authorized Codacus configuration; it does not establish that the artifact cannot run with deliberate CPU/offload settings.

## Evidence

Raw per-model snapshots, commands, logs, requests, and responses are in [results/runtime-load-speed-20260919](../../../results/runtime-load-speed-20260919). The Qwen3.8 Flash-Next probe has no response artifact because no generation was issued after load failure.

The Ollama runtime is not part of this probe. The registry therefore contains distinct series for the Prism runtime and the Codacus runtime plus separate artifact keys; an Ollama or alternate Flash runtime must receive another `series_key` and cannot be aggregated with these rows.
