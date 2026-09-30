# T87 P1 — owner authorization accepted

Status: **accepted**

- Owner: `Breno`
- Accepted at: `2026-09-18T14:01:36Z`
- Scope source: `docs/en/plans/t87-p1-authorization-request-2026-09-18.md`
- Scope source SHA-256: `f4bcc4e68defcd9a9e1ed4035bd842e36da90b67d222adc0f59c62091b55d20b`

## Accepted scope

This authorization covers one bounded P1 package:

- 85 controlled generation calls: 5 complete `spec-wins` executions × 17
  tasks, using five distinct recorded seeds, against `qwen3.6:35b-a3b`;
- isolated build and execution of the thecodacus `llama.cpp` fork, including
  required local toolchain and artifacts;
- copying or downloading the exact GGUF artifact(s), including any explicitly
  required MTP/draft artifact;
- one dedicated OpenAI-compatible `llama-server` endpoint;
- exclusive RTX 5090 use by this runtime during the 85 calls;
- persistence of transcripts and metrics under llm-bench experiment artifacts.

## Preconditions and exclusions

- Runtime identity, model artifact identity, execution context and metric
  series must be hash-addressed before generation.
- The current Ollama/gateway path is not the P1 harness and must not be used
  as a seed substitute.
- No two runtimes may use the GPU concurrently.
- Ollama, the gateway and its profile are not replaced or reconfigured.
- Cleanup/reset of Herdr agents, unrelated live traffic, commit and push are
  outside this authorization.
- If GPU exclusivity requires unloading or stopping a resident Ollama process,
  that operation must be captured as part of the approved bounded packet; any
  cleanup/reset must preserve `gpt-5.6-luna` with
  `reasoning_effort=xhigh`, capture before/after state, and record `unknown`
  when unobservable.

This file is immutable after acceptance. Any scope change requires a new
versioned owner acceptance artifact.
