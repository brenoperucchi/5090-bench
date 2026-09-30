# Qwen3.6 runtime A/B — owner authorization

Status: **accepted**

- Owner: `Breno`
- Accepted at: `2026-09-18T18:21:20Z`
- Scope: bounded serial comparison of the Ollama and dedicated `llama.cpp`
  arms for Qwen3.6-35B-A3B.

## Authorized workload

- 48 generation calls total;
- 24 calls per arm: 4 discarded warm-ups plus 4 prompt classes × 5 measured
  repetitions;
- Ollama arm: own tag `qwen3.6:35b-a3b` at LAN
  `192.168.0.125:11434`;
- llama.cpp arm: standalone Q4_K_M GGUF at LAN
  `192.168.0.125:18087`;
- `temperature=0`, `seed=42`, `num_ctx=32768`, `num_predict=256`;
- no cloud calls.

## GPU sequence and state changes

The dedicated llama.cpp process currently resident on the RTX 5090 is stopped
before the Ollama arm. Ollama is then allowed to load its model, after which
the model is explicitly unloaded. The same llama.cpp command line and flags
captured before the stop are restarted and checked byte-for-byte at the flag
level before the llama.cpp arm. The two runtimes must never be resident on the
GPU concurrently.

The run records before/after process, listener, endpoint, model-residency and
GPU state. It changes no gateway or profile, does not touch the model catalog,
does not reset or clean up Herdr agents, and does not commit or push. The 330
generation P1 remains a separate blocked scope.

## Interpretation boundary

Ollama uses its tag artifact and llama.cpp uses the standalone GGUF artifact;
their catalog/tag identities are not byte-identical. The result is therefore
explicitly a comparison of **runtime plus artifact**, not an effect estimate
of runtime alone. Internal runtime metrics are retained separately; only
explicitly comparable client-wall metrics may be compared.
