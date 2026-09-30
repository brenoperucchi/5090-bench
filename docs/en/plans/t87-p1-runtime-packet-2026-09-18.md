# T87 P1 runtime packet — 2026-09-18

Status: `ready_for_owner_review`; generation not started (`0/85` calls).

This packet is a separate, hash-addressed execution record. It does not mutate
the accepted authorization artifact
`docs/en/plans/t87-p1-authorization-accepted-2026-09-18.md` (SHA-256
`2e71c9f34f20d4c7b06cb6df0671e2d3d2c3960f30bbdde5aeaf9822bbb67600`).

## Runtime identity

- Runtime: isolated `thecodacus/llama.cpp` fork, not Ollama and not the
  `llm-gateway`.
- Source path on target: `/home/brenoperucchi/t87-runtime/codacus-llama.cpp`.
- Branch: `perf`.
- Commit: `27c54b4bbcefadedcec6397477cc2e866c1db716`.
- Build directory: `/home/brenoperucchi/t87-runtime/codacus-build-final2`.
- Binary: `llama-server`.
- Binary SHA-256:
  `37acf8e80c85f91794d9fa0268d34b40dbfa2f4286527a92bdd13dfefdab689b`.
- Toolchain: GCC 13.3.0 in an isolated prefix; CMake 3.31.6; CUDA 12.8.93
  (`nvcc`).
- CUDA architecture: `120a-real`.
- GPU: NVIDIA GeForce RTX 5090, 32607 MiB, driver 616.64.
- Execution context: Debian GNU/Linux 13 (trixie), WSL2 kernel
  `6.18.33.2-microsoft-standard-WSL2`, host `Ryzen9WSL`; process PID 794309,
  SID 794305, no TTY. Native Windows session identity is not observable from
  this WSL process and remains `unknown`.

## Build configuration

The final configure used:

```text
CMAKE_BUILD_TYPE=Release
GGML_CUDA=ON
CMAKE_CUDA_COMPILER=/home/brenoperucchi/t87-runtime/toolchain/cuda-12.8-min/prefix/usr/local/cuda-12.8/bin/nvcc
CMAKE_CUDA_HOST_COMPILER=/home/brenoperucchi/t87-runtime/toolchain/gcc-13/prefix/usr/bin/g++-13
CMAKE_CUDA_ARCHITECTURES=120a-real
CUDAToolkit_ROOT=/home/brenoperucchi/t87-runtime/toolchain/cuda-12.8-min/prefix/usr/local/cuda-12.8
GGML_NATIVE=OFF
LLAMA_BUILD_SERVER=ON
LLAMA_BUILD_TOOLS=ON
LLAMA_CURL=OFF
```

The linker was given the isolated CUDA library directory through `-L`,
`-Wl,-rpath` and `-Wl,-rpath-link`. The CUDA 12.8 header compatibility patch
was confined to the isolated toolchain header
`crt/math_functions.h`: patched SHA-256
`024ff8406766f26573a1fe842cfb8e66f2ae35652fc0adc5e38b68a758276de9`; original
preserved as `.orig` with SHA-256
`2f2189d1752d862e96122f985484c89e16bd03a485a01e1f114514f738a2ed4f`.

## Model and endpoint

- Main effective model:
  `/mnt/e/llm-bench-t87-p1/models/qwen3.6-35b-a3b-q4_k_m.gguf`.
- Main GGUF size: `21718480960` bytes.
- Main GGUF SHA-256:
  `d372de8e934898a59e6ccfabc3368474711384d8f1fd4d22d87a3f0a45400cdc`.
- Ollama tag digest is retained as provenance only; it is not used as the
  standalone GGUF file hash.
- The companion mmproj blob was identified separately
  (`a62390d25b4b4a2d8afd7cc3c90021c11935c1fdd48d7cb0723ab71cd02a598e`) and is
  not loaded for the text-only P1 tasks.
- Endpoint: `http://100.88.95.78:18087` (dedicated llama-server over the
  internal Tailnet path; server binds `0.0.0.0:18087`).
- Server command flags:
  `--ctx-size 32768 --n-gpu-layers all --parallel 1 --no-webui`.
- Endpoint GET checks before generation: `/health` returned `{"status":"ok"}`;
  `/v1/models` reported GGUF, `n_ctx=32768`, `n_params=35505251456`, and
  `Q4_K - Medium`.
- GPU residency gate: passed before generation; GPU memory was
  `22770 MiB / 32607 MiB`, and the compute process was PID 794309. Ollama
  `/api/ps` was `{"models":[]}`.
- No POST generation has been sent. Latency is therefore `unknown`.

## P1 seed plan and gate

Five distinct seeds are fixed for the five complete 17-task executions:

```text
1000, 1017, 1034, 1051, 1068
```

These are the existing five-seed set used by the repository's prior language
template harness; each request must echo the effective seed in its transcript
and metrics. The seed is sent to the llama.cpp OpenAI-compatible endpoint per
request, never through the gateway.

The packet is ready for owner review. Do not start the 85 calls until this
identity, endpoint, model hash, GPU-residency gate, and seed list have been
reviewed. Any runtime, binary, model, endpoint, or seed change creates a new
packet; it does not amend this record in place.
