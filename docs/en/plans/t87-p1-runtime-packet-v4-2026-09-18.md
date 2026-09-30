# T87 P1 runtime packet v4 — LAN route

Status: `owner_confirmation_required`; no generation POST has been sent under
this packet.

This packet supersedes the unexecuted v3 retry packet only because the
transport route is now explicit and selected as `lan`. The runtime, model,
protocol, task set, seeds, and bounded retry scope are unchanged. The v3
packet remains historical and is not mutated.

## Selected route

- Runtime: thecodacus `llama.cpp`, dedicated `llama-server`.
- Endpoint: `http://192.168.0.125:18087`.
- Route identity: `id=lan`, `scheme=http`, `host=192.168.0.125`,
  `port=18087`, request path `/v1/chat/completions`.
- Tailnet endpoint `100.88.95.78:18087` is a distinct route and must not be
  aggregated with this LAN series.
- Read-only confirmation at packet preparation: `/health` returned `200`,
  and the endpoint reported the expected GGUF and `n_ctx=32768`.

## Retry scope

The retry preserves the accepted v2 measurement shape:

- five complete executions of the unmodified `spec-wins` source;
- fresh `t1_ratelimit`, `t2_metrics`, and `t3_pipeline` sessions per execution;
- seeds `1000, 1017, 1034, 1051, 1068`;
- 17 grader checks per execution (`7 + 8 + 2`);
- maximum 330 model generations using reference caps `13/27/26`;
- no synthetic warm-up generation.

The retry includes the v3 prompt-preservation correction and records
`runtime`, `route`, and `series_key` in preparation, preflight, run, and
transcript artifacts. A consumer must fail closed if records have different
`series_key` values; it must not sum LAN and Tailnet observations.

## Question answered and question not answered

This P1 answers the narrower sequencing question:

> How much run-to-run variance does the pinned `spec-wins` instrument exhibit
> when exercised five times with the available Qwen3.6-35B-A3B model through
> the same hash-addressed `llama.cpp` runtime, protocol, and route?

It can therefore invalidate or qualify the reliability of the published
17/17-versus-14/17 comparison as an instrument-level premise. It does **not**
reproduce the Qwen3.8-Flash-Next 17/17 result, estimate that model's variance,
select a 125B/177B candidate, or establish that the 35B is equivalent to the
Flash-Next model. The 35B comes first by sequencing: its exact GGUF and
runtime are already available for a cheaper falseability check. That is not a
scientific substitution for the Flash-Next arm.

## Flash-Next artifact boundary

The historical scorecard identifies only `Qwen3.8-Flash-Next 125B IQ3_XXS`;
the exact repository, shard filenames, and SHA-256 used for that scorecard
are not present in the local evidence and remain `unknown`.

The current public artifact matching the fork README's `UD-IQ3_XXS` label is
`unsloth/Qwen3.8-Flash-Next-GGUF`, directory `UD-IQ3_XXS`, split into three
shards totaling `81,961,823,936` bytes (`76.33 GiB`, `81.96 GB`). Its public
model identity is `177B`/`qwen4exp`, so it must not be silently substituted for
the historical `125B IQ3_XXS` scorecard artifact. No Flash-Next shard has been
downloaded or included in this P1 packet.

Source references: [public model card](https://huggingface.co/unsloth/Qwen3.8-Flash-Next-GGUF)
and [public shard listing](https://huggingface.co/unsloth/Qwen3.8-Flash-Next-GGUF/tree/main/UD-IQ3_XXS).

The 32-GiB RTX 5090 cannot hold that weight set entirely in VRAM. A Flash-Next
run would require host-memory/offload behavior and a separately verified
expert-cache configuration; the fork source contains `qwen4exp` support and
expert-cache code, but this does not yet prove the exact artifact loads or
performs correctly on this host. Those are a later, separately identified
Flash-Next gate.

## Hashes

- Protocol: `t87-p1-protocol-v2-2026-09-18.md`, SHA-256
  `e4c19e5d691cf6aa781dc66c0ba9e1925f459c52eaac397470596d455903ab20`.
- Harness: `tools/t87_spec_wins_harness.py`, SHA-256
  `ff889f991fe77e726cb8cf7c8b848b87d3d9f8b8473aa74faf9d94c6d2b8d745`.
- Preparation: `results/t87-p1-v3-2026-09-18-preparation-lan/preparation.json`,
  SHA-256
  `34ebf84542babcb85d12b0f71b64e305adb158781da233dcd1ae2791a3cd0561`.
- Benchmark commit: `776e799c7e0a24271e021aca2ea4b1c1b1f10017`.
- Runtime commit: `27c54b4bbcefadedcec6397477cc2e866c1db716`.
- Runtime binary SHA-256:
  `37acf8e80c85f91794d9fa0268d34b40dbfa2f4286527a92bdd13dfefdab689b`.
- GGUF SHA-256:
  `d372de8e934898a59e6ccfabc3368474711384d8f1fd4d22d87a3f0a45400cdc`.
- Dependency bundle SHA-256:
  `7293488bdf2c6ae0d9cdaef39dd8ef019c841f84641026624d8bc1263176aa7f`.

Sampling, server context (`32768`), persistent sandbox, grading boundary and
interpretation remain those recorded in the accepted v2 protocol. The
preparation snapshot observed `NVIDIA GeForce RTX 5090, 22817 MiB, 32607 MiB,
0 %, 616.64`.

## Gate

Owner confirmation is required before
`tools/t87_spec_wins_harness.py run` is invoked with this packet. Confirmation
authorizes only the bounded retry above; it does not authorize any
gateway/Ollama change, Herdr cleanup/reset, production traffic, commit or
push.
