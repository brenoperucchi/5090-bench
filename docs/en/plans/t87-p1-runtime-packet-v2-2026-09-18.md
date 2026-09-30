# T87 P1 runtime packet v2 — complete `spec-wins` sessions

Status: `executed_then_invalidated_before_grading`.

At packet creation no model generation POST had been sent. The subsequent v2
campaign used this packet, consumed 330 generations, and was invalidated
before grading because the prompt parser dropped task headings. No valid P1
result exists under this packet.

This packet is a new, immutable execution record. It does not amend the
accepted v1 authorization or the v1 runtime packet. The v2 protocol is
`docs/en/plans/t87-p1-protocol-v2-2026-09-18.md` with SHA-256
`e4c19e5d691cf6aa781dc66c0ba9e1925f459c52eaac397470596d455903ab20`.

## Scope

- Five complete executions of the published agentic `spec-wins` instrument.
- Three fresh task conversations per execution: `t1_ratelimit`, `t2_metrics`,
  `t3_pipeline`.
- Five seeds: `1000, 1017, 1034, 1051, 1068`.
- Seventeen grader checks per execution: `7 + 8 + 2`.
- At most 66 model generations per execution, 330 across the campaign, using
  reference caps `13/27/26` per task. A task that reaches its cap without a
  final report is incomplete, not a zero.
- No synthetic warm-up generation.

## Hash-addressed instrument

- Benchmark source: `thecodacus/spec-wins`, commit
  `776e799c7e0a24271e021aca2ea4b1c1b1f10017`.
- Published prompt packet SHA-256:
  `1219567023e57f07b268b3cf15f458e8810331efd33b1937d9bb327ab1a5082f`.
- Harness: `tools/t87_spec_wins_harness.py`.
- Harness SHA-256:
  `1185ec5b93b78cc21bc6629d0a703d3a0dad34c0736836656b822d70d8db5c8f`.
- Preparation packet:
  `results/t87-p1-v2-2026-09-18-preparation-7/preparation.json`.
- Preparation packet SHA-256:
  `53ab98a9fb8283d146b365a067bbb957df441d80b4842d96591b1217c005dfed`.
- Isolated benchmark dependency bundle SHA-256:
  `7293488bdf2c6ae0d9cdaef39dd8ef019c841f84641026624d8bc1263176aa7f`.
  It contains Flask 3.1.2 and its pinned transitive wheel contents; pytest
  9.0.3 is supplied by the target Python installation.

## Runtime and model

- Runtime: dedicated thecodacus `llama.cpp`, not Ollama and not the gateway.
- Fork commit: `27c54b4bbcefadedcec6397477cc2e866c1db716`.
- Binary SHA-256:
  `37acf8e80c85f91794d9fa0268d34b40dbfa2f4286527a92bdd13dfefdab689b`.
- Model endpoint: `http://100.88.95.78:18087`.
- Effective model: `/mnt/e/llm-bench-t87-p1/models/qwen3.6-35b-a3b-q4_k_m.gguf`.
- GGUF SHA-256:
  `d372de8e934898a59e6ccfabc3368474711384d8f1fd4d22d87a3f0a45400cdc`.
- Server configuration: `--ctx-size 32768 --n-gpu-layers all --parallel 1
  --no-webui`.
- OpenAI model id: the effective GGUF path above.
- Execution context: Debian 13 under WSL2 on `Ryzen9WSL`; native Windows
  session identity remains `unknown`.

## Sampling payload

Every request records and sends this fixed payload, with the run seed added:

```json
{
  "temperature": 0.6,
  "top_p": 0.95,
  "top_k": 20,
  "max_tokens": 4096,
  "cache_prompt": false,
  "stream": false
}
```

`num_ctx` is not an accepted per-request field in this fork's OpenAI schema;
the effective context is fixed by the server flag `--ctx-size 32768` and is
recorded as `server_context_size: 32768` in the preparation packet.

The published historical transcripts do not expose their complete sampling
payload. Results therefore identify the full tuple
`(model, runtime, benchmark commit, harness, sampling payload)` and are not
claimed to be byte-for-byte historical reproduction.

## Isolation and gates

- The model sees only the published preamble and one task block at a time.
- Each task runs in a persistent bwrap shell containing only a copy of that
  task. The hidden grader, answer key, solutions and benchmark source are not
  mounted in the model sandbox.
- Grading runs after the final report outside the model sandbox and its output
  is not returned to the model.
- Nested SSH, sudo, namespace control, path escape and non-localhost URLs are
  rejected by the tool boundary.
- Preparation GETs were healthy at `2026-09-18T15:57:40Z`; GPU snapshot was
  `NVIDIA GeForce RTX 5090, 22697 MiB, 32607 MiB, 0 %, 616.64` and the
  dedicated llama-server PID remained `794309`. The gate must be rechecked
  immediately before the first run; a changed/unknown GPU gate stops the
  campaign.
- No Ollama/gateway configuration change, Herdr cleanup/reset, production
  traffic, commit or push is part of this packet.

## Interpretation

The output estimates run-to-run spread for this pinned model/runtime/protocol
tuple. It does not select a production model, authorize watcher shadow mode,
or establish a byte-for-byte reproduction of the published Qwen3.6 14/17.
