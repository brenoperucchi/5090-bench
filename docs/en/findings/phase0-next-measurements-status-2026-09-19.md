# Phase 0 follow-up measurements — status

## KL divergence

The Codacus build now contains `llama-perplexity`; it was built locally on
2026-09-19 with binary SHA-256
`b4147ba3762a66e657927ffaf044665b9d9e06d589cad63b72dcac296eaea2dd`.
The tool's contract computes KL divergence against a logits file supplied with
`--kl-divergence-base`; it does not create a higher-precision reference by
itself.

The local model inventory contains Bonsai PTQ1_0 and no Bonsai PQ2_0 or other
higher-precision Bonsai artifact. It also contains only the Qwen3.8-27B
UD-Q5_K_XL artifact for that model family. Therefore no valid same-model,
higher-precision baseline is available locally. No cross-model KL value was
produced and no model was downloaded.

## Context probe suspension

The Flash-Next context scan was suspended by owner before 32k/65k/131k/262k.
The completed load evidence is recorded separately in
`flash-next-context-probe-2026-09-19.md`.

## Qwen3.6-35B load/speed probe

The fourth candidate was available locally and was measured on the Codacus
CUDA 13 build, LAN route `192.168.0.125:18087`, `--n-gpu-layers 999`,
`--fit off`, `--ctx-size 32768`, `--flash-attn on`, `--parallel 1`.

- GGUF: `qwen3.6-35b-a3b-q4_k_m.gguf`, 21,718,480,960 bytes,
  SHA-256 `d372de8e934898a59e6ccfabc3368474711384d8f1fd4d22d87a3f0a45400cdc`.
- Load: health OK after approximately 2m20s; 42/42 layers offloaded; CUDA
  buffer 19,902.74 MiB; CPU-mapped buffer 272.81 MiB; KV 640 MiB.
- Residency: 22,093 MiB VRAM used / 10,098 MiB free; RSS approximately
  0.94 GiB after load.
- Request: explicit `temperature=0`, `top_k=20`, `top_p=0.95`, `seed=42`,
  `max_tokens=2048`; prompt hash
  `6653ec984a1d4c4a798c88cd6e474d0a9bce7aab0886eaec8520bed57b686c84`.
- Decode: warmup 241.55 tok/s; three hot values 236.44, 234.47, and
  231.35 tok/s; hot median 234.47 tok/s.
- All four responses ended with `finish_reason=length` at 2048 tokens. This is
  a throughput result under the output cap, not a complete-answer quality
  result.

## Remaining measurements

The p95-with-cold-starts and Qwen3.8-27B versus Qwen3-14B paired measurements
remain unrun. Their raw outputs must carry explicit sampling fields and
separate `series_key` values for runtime, artifact, route, and offload.

They also need two owner-facing inputs before a defensible result can be
claimed: the cold-start event/cadence and sample count for the six-hour p95
loop, and a frozen paired coding-task packet plus independent labels if the
Qwen3.8-versus-Qwen3-14B result is meant to answer quality rather than only
latency. The repository's coding contract is currently non-executable and
explicitly has no approved workload or labels.

## Owner decision: remove Qwen3-14B criterion

The owner discarded `qwen3:14b`; it must not be downloaded or measured. The
previous acceptance criterion “code understanding better than qwen3-14b” is
therefore not verifiable and cannot be used to promote or reject a candidate.
The battery must define a replacement rejection criterion before it can decide
the guardian model.

The last-round candidates are Qwen3-Coder-30B-A3B and Ternary Bonsai 2 27B;
Qwen3.8-27B and Qwen3.6-35B-A3B remain comparison records.

Owner-authorized downloads are in progress on the Ryzen9 WSL under
`/mnt/e/llm-bench-t87-runtimes/models/last-round/`: Qwen3-Coder UD-Q5_K_XL
(candidate), Qwen3-Coder UD-Q6_K_XL (KL reference), Bonsai F16 (KL reference),
and Bonsai PQ2_0 (intermediate point). Each has an expected byte count and
Hugging Face LFS SHA-256 in the remote `download-manifest.json`; no Qwen3-14B
download was started.

## Bonsai guardian T1/T2 probe — PTQ1_0

The frozen, label-free input packet is
`results/guardian-probe-20260919/input-manifest.json`. It contains five real
review/ask packets, `labels_loaded=false`, explicit `temperature=0`, `top_k=20`,
`top_p=0.95`, `seed=42`, and a hash for the schema and every packet. The output
contract is `watcher-guardian-output-v1`; its full schema hash is
`37d5e5e1cece7f444e7a68e5956941fcadbc06639a22d42d16cd1f983f6237ab`.

The first unconstrained T2 attempt used 8192 tokens and was intentionally
aborted after the server consumed the full cap in reasoning without returning
structured content; it is recorded as a protocol diagnostic, not a result.
The comparable T2 run used 2048:

| PTQ1_0 condition | content JSON valid | reasoning JSON valid | `finish_reason=stop` |
| --- | ---: | ---: | ---: |
| unconstrained, 2048 | 0/5 | 0/5 | 0/5 |
| explicit GBNF, 2048 | 0/5 | 3/5 | 5/5 |

The explicit GBNF was required after the Prism build's
`--json-schema-file` path failed before generation with literal
`HTTP Error 400: Bad Request`; its server log reports
`Failed to initialize samplers: std::exception` after an incomplete
conversion warning for the schema `pattern`. The same failure was recorded for
T2 at 2048 and T1 at 8192, five requests each; neither consumes model output.

T1 used the five-task packet with `max_tokens=8192`:

| PTQ1_0 condition | completed (`stop`) | content JSON valid | reasoning JSON valid | completed token counts |
| --- | ---: | ---: | ---: | --- |
| unconstrained, 8192 | 4/5 | 4/5 | 0/5 | 7275, 3113, 3443, 3956 |
| explicit GBNF, 8192 | 5/5 | 0/5 | 3/5 | 132, 701, 85, 697, 85 |
| `--json-schema-file`, 8192 | 0/5 (request error) | 0/5 | 0/5 | none |

The GBNF output was structurally valid only in `reasoning_content` for 3/5
responses; the consumer rule is fail-closed and does not promote reasoning to
the usable `content` channel. All three reasoning-valid GBNF outputs had an
empty `evidence` array. The four content-valid unconstrained T1 outputs had no
empty evidence arrays. This makes the `evidence` minimum a measured follow-up
risk, not an assumption; `minItems` remains unchanged pending owner approval.

Interpretation correction: earlier Bonsai (121 tok/s) and Qwen3.6-35B
(234 tok/s) observations at `max_tokens=2048` cannot support a quality or
completion claim. They measured a caller-imposed output ceiling, not the
model's ability to finish the task. The PTQ1_0 T1 result is the first result in
this series using the generous budget requested for conclusion testing.

The explicit GBNF and JSON-schema-file runs are distinct protocol conditions;
they are not silently pooled with unconstrained output. No tok/s value is
reported in this section; speed is a separate measurement with hot-median and
cold/p95 columns, and download contention is recorded separately.

## Bonsai F16 KL pilot: native disk versus `/mnt/e`

The owner authorized one controlled relocation pilot before choosing the number
of chunks for the full KL pass. The F16 reference was copied from
`/mnt/e/llm-bench-t87-runtimes/models/last-round/bonsai-f16-reference/` to the
native Linux path
`/home/brenoperucchi/t87-runtime/kl-native/Ternary-Bonsai-2-27B-F16.gguf`.
The destination was checked at exactly `53,808,408,928` bytes and its real
SHA-256 is
`f6f3b2c9b41956c34b379ec7c301dc936bc38d79b3c24c83388dd7d76000c180`.

The pilot changed only the model path from the prior `ngl24` pilot. Both used
the same Codacus `llama-perplexity` binary, corpus, `--chunks 1`, `--ctx-size
2048`, `--n-gpu-layers 24`, `--fit off`, `--load-mode mmap`, `--batch-size 512`,
`--ubatch-size 256`, `--threads 16`, and `--threads-batch 16`. The corpus SHA is
`aa7703458a24847657d224734d0c4827a79a319139364515ef3bce65bb3de68c` and the
binary SHA is
`b4147ba3762a66e657927ffaf044665b9d9e06d589cad63b72dcac296eaea2dd`.

| Model location | load to `system_info` | chunk time | PPL estimate | logits SHA |
| --- | ---: | ---: | ---: | --- |
| `/mnt/e` (prior `ngl24`) | ~443.69 s | 25.66 s | 828674.8567 +/- 43781.96835 | `a10fcbc8672f371f069d32b149c8ccc0e5c79e402e1c22f524556dd61f19ef74` |
| `/mnt/e` (prior `ngl20`) | ~474.12 s | 27.74 s | 828674.8567 +/- 43781.96835 | `a10fcbc8672f371f069d32b149c8ccc0e5c79e402e1c22f524556dd61f19ef74` |
| native `/home` (`ngl24`) | ~31.60 s | 25.99 s | 828674.8567 +/- 43781.96835 | `a10fcbc8672f371f069d32b149c8ccc0e5c79e402e1c22f524556dd61f19ef74` |

The native pilot completed successfully (`status=0`, wrapper elapsed 62 s),
with the same PPL and logits as the `/mnt/e` pilot. Relocating the model
therefore produced a large improvement in initial load time but no material
improvement in the measured chunk pass (`+0.33 s`, about `+1.3%`). For this
configuration, the result does not support treating `/mnt/e`/drvfs as the
dominant bottleneck of chunk computation; the full-pass cost remains roughly
the same. It does support using the native path when load time matters.

This is recorded as a negative optimization result: changing `-ngl 20` to
`-ngl 24` on `/mnt/e` improved the chunk from `27.74 s` to `25.66 s`, but moving
the same `-ngl 24` model to the WSL filesystem produced `25.99 s`, not a material
improvement. The measured bottleneck is therefore not removed by either of those
levers; the working hypothesis is repeated rereading of a `53.8 GB` model whose
working set exceeds the available `47 GB` RAM. This is an interpretation of the
three measurements, not a claim that every future filesystem or cache state must
behave identically.

The native file was copied immediately before the pilot, so no explicit cache
eviction was performed and the two pilots do not establish a strictly cold-cache
A/B. This is recorded as a limitation rather than inferred away. No full KL
pass was started; chunk-count selection remains owner-pending.

The native copy was subsequently removed after the pilot. Its pre-removal size
was `53,808,408,928` bytes. Large model and logits artifacts must remain under
`/mnt/e/llm-bench-t87-runtimes/`, not under `/home` or another WSL virtual-disk
path. The actual host-mounted free space observed at cleanup was `C: 207 GB`,
`D: 91 GB`, and `E: 320 GB`; `df -h /` is not used as a host-capacity claim.
The existing pilot logits are on `/mnt/e`; each completed pilot logits file is
`508,079,116` bytes, so 100 chunks would require approximately `50,807,911,600`
bytes (`47.32 GiB`) before other outputs.

For the discarded pre-Prism plan only, 100 chunks at the measured `/mnt/e`,
`ngl24` rate estimated about `42m46s` of chunk processing, plus approximately
`7m24s` one-time model load, or about `50m10s` wall time. That estimate referred
to the invalid Codacus run and must not be used as the Prism runtime estimate.

## Bonsai F16 KL runtime validation and Prism rebase

The first 100-chunk base was invalidated after a runtime sanity check. It was
generated with the Codacus `llama-perplexity`
(`b4147ba3762a66e657927ffaf044665b9d9e06d589cad63b72dcac296eaea2dd`), while
the Bonsai artifacts require the PrismML fork. The Codacus binary loaded the F16
file without an error, but its perplexity calculation was silently wrong:

| Binary and input | PPL | Status |
| --- | ---: | --- |
| Codacus, common-control corpus | `1165154.2284 +/- 58835.51697` | invalid runtime result |
| Prism, same F16 and same corpus | `1.1045 +/- 0.00232` | runtime sanity only |
| Prism, PTQ1_0 and same corpus | `1.1035 +/- 0.00230` | runtime sanity only |
| Codacus, `.herdr` corpus, 100 chunks | `838794.2256 +/- 4485.88672` | invalid runtime result |
| Prism, `.herdr` corpus, one chunk | `5.4163 +/- 0.40838` | sanity gate passed |

The common-control corpus contains 5,472 words and is intentionally repetitive;
its low PPL is not a quality claim about Bonsai. Its SHA-256 is
`bb57074160f85d89b1f0eb0b2c470dfed528050e2296dbd8cae6ab3c199dd44d`. The first
149-token version was rejected by `llama-perplexity` because a 2,048-token
context requires at least 4,096 input tokens; it produced no PPL and is not
evidence about the model.

The Codacus PTQ1_0 sanity attempt also produced no PPL: it failed at load with
`tensor 'output.weight' has invalid ggml type 143`. The Prism build initially
had only `llama-server`; `llama-perplexity` was then compiled successfully with
the existing cache in 11 seconds. The Prism perplexity binary SHA-256 is
`1b525c0654e29c6549a64e90e7811bb39137af911febbf92eff502ec969809b6`.

This is a first-order runtime finding: for PrismML Bonsai artifacts, a model
loading successfully is not sufficient evidence that the computation is
correct. The Codacus results remain as evidence of that silent incompatibility,
not as measurements of Bonsai quality or as a KL reference.

The invalid Codacus logits file was removed after verifying its exact size
(`50,807,909,620` bytes); the historical invalid log remains at
`base-100/base-f16-ngl24-100.log`. No KL comparison was run against it. The
replacement base is now running with the Prism binary, using the original
F16, `.herdr` corpus, `--chunks 100`, `--ctx-size 2048`, `--n-gpu-layers 24`,
`--fit off`, `--load-mode mmap`, `--batch-size 512`, `--ubatch-size 256`, and
16 threads. Its output is hash-addressed separately under
`/mnt/e/llm-bench-t87-runtimes/kl-bonsai-20260919/base-100-prism/`; the first
chunk is `5.4163` and the tool estimates about 44.25 minutes of chunk work.
Comparisons against PTQ1_0 or PQ2_0 remain blocked until this Prism base
completes.

## Bonsai F16 Prism KL base and quantization comparisons

The Prism base completed successfully over 100 chunks on the `.herdr` corpus:
`PPL = 6.0012 +/- 0.04775`. The run used the Prism `llama-perplexity`, F16,
`--ctx-size 2048`, `--n-gpu-layers 24`, `--fit off`, `--load-mode mmap`,
`--batch-size 512`, `--ubatch-size 256`, and 16 threads. Its logits artifact is
`50,807,909,620` bytes at
`/mnt/e/llm-bench-t87-runtimes/kl-bonsai-20260919/base-100-prism/bonsai-f16-prism-base-100.logits`.

Both quantization comparisons completed with the same Prism runtime, corpus,
100 chunks, context, batch, and offload configuration:

| Quantization | Mean KLD | Median KLD | p99 KLD | p99.9 KLD | Maximum KLD | Same top-p |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| PTQ1_0 | `0.000368 +/- 0.000020` | `0.000184` | `0.001760` | `0.015705` | `1.546789` | `98.630 +/- 0.036%` |
| PQ2_0 | `0.000385 +/- 0.000020` | `0.000183` | `0.001725` | `0.016675` | `1.344562` | `98.593 +/- 0.037%` |

For a diagnostic threshold of `0.01` nats/token, the exact fraction above the
threshold is `unknown`: this build prints KLD quantiles and aggregate moments,
but does not expose the per-token count in its output. The printed p99 and p99.9
bound the fraction to roughly the interval between `0.1%` and `1%`, but that is
not a substitute for an exact count and is not an acceptance gate.

The curve does not show a material improvement from PQ2_0 over PTQ1_0 in this
run. Their mean and median KLD are effectively equal within the reported
uncertainty; PQ2_0 has a slightly lower p99 but a slightly higher p99.9, and a
lower same-top-p rate. Therefore PQ2_0 is not supported as a clearly better
quality point by this KL measurement alone. This is a distributional result,
not a task-quality or guardian-compatibility verdict.

The invalid Codacus base and its logits are excluded from all comparisons. The
Codacus log remains as evidence of the silent runtime incompatibility; the
Prism comparison logs are:

- PTQ1_0: `compare-ptq1-prism-100.log`, SHA-256
  `b47f6938d04b77e918957472e05653fccaa3c5cde4ebdcb4fd41c21b7ac10695`.
- PQ2_0: `compare-pq2-prism-100.log`, SHA-256
  `3c8a5d8784a15a6536021694b0db0ca3f0255494c95f4f92c529987766911dc9`.

The previously discarded qwen3-14b reference is available in the Ollama store
without a new download, according to the owner verification (about 9.3 GB and
readable as GGUF). It was not used in this KL work and its exact blob path and
SHA-256 were not independently observed here. The declared code-understanding
reference is therefore available for a later, separately hash-addressed test;
it is not silently mixed into the Bonsai KL series.

The next queued quality work is the same T1/T2 packet on Qwen3-Coder 30B-A3B,
Qwen3.6-35B-A3B, and Qwen3.8-27B, after this Bonsai KL record. Flash-Next
remains outside the current evaluation scope, not deleted.

## Candidate T1/T2 probes: Coder, a3b, and Qwen3.8

The three candidates were evaluated with the frozen input manifest
`results/guardian-probe-20260919/input-manifest.json` (SHA-256
`b9b943d0dc6301917cf7ec7cf84e71f8cf920775352015d1aeb97aa098ab7791d`),
schema v1 (SHA-256
`37d5e5e1cece7f444e7a68e5956941fcadbc06639a22d42d16cd1f983f6237ab`),
temperature `0`, top-k `20`, top-p `0.95`, seed `42`, `parallel=1`, context
`32768`, `--n-gpu-layers all`, `--fit off`, and Flash Attention. The request
endpoint in the summaries is `127.0.0.1`; it was an SSH local forward to the
dedicated llama-server on `192.168.0.125`, not the gateway or Ollama.

The runtime binary was Codacus `llama-server`, SHA-256
`1cacf346c79366cf97e591e06b1587dd49fb214afd93af20a5692af659c2df24`.
The Coder GGUF was `21,740,305,568` bytes, SHA-256
`eb331a4eee8eb6b5a8eb25f44f96f45c71b8d10f553c0a456190dd590a7ef77d`.
The a3b source was the Ollama blob whose content hash is encoded in its path:
`d372de8e934898a59e6ccfabc3368474711384d8f1fd4d22d87a3f0a45400cdc`.
The Qwen3.8-27B GGUF is `20,876,938,144` bytes, SHA-256
`8601193d3d5760c37fb8ce1b43afebc69df5fb24e1fbc5a547c32e2200305276`.

| Candidate | T1 unconstrained 8192 | T2 unconstrained 2048 | T2 explicit GBNF 2048 | T1 explicit GBNF 8192 |
| --- | ---: | ---: | ---: | ---: |
| Qwen3-Coder 30B-A3B Q5 | 2/5 valid, 5/5 stop | 2/5 valid, 5/5 stop | 2/5 valid, 5/5 stop | 2/5 valid, 5/5 stop |
| Qwen3.6-35B-A3B Q4 | 4/5 valid, 4/5 stop | 0/5 valid, 0/5 stop; 5/5 length | 0/5 valid, 4/5 stop | 0/5 valid, 4/5 stop |
| Qwen3.8-27B Q5 | 5/5 valid, 5/5 stop | 0/5 valid, 0/5 stop | not run: GPU residual gate | not run: GPU residual gate |

There were no request errors in the completed phases. The a3b GBNF phases
produced two reasoning-channel schema-valid objects in the raw summaries but
zero valid objects in the required `content` channel; they therefore remain
zero for the contract metric. The Qwen3.8 GBNF server was started but no
request was sent: after the prior Qwen server cycle, `nvidia-smi` showed
`10,526 MiB` resident with no llama-server process, and the fresh GBNF server
left only `178 MiB` free. This is an environment/context-residue block, not a
model-quality result. A WSL/GPU reset was not performed.

The speed probe used the fixed LRU prompt
`Implemente em Python um LRU cache com capacidade fixa, usando dict e lista duplamente ligada. Inclua get e put em O(1).`
(SHA-256 `6653ec984a1d4c4a798c88cd6e474d0a9bce7aab0886eaec8520bed57b686c84`),
the same explicit sampling parameters, one discarded warm-up, and three hot
generations. Server decode timings, not wall-clock request latency, were used:

| Candidate | Warm-up | Hot measurements | Median hot tok/s | Output behavior |
| --- | ---: | ---: | ---: | --- |
| Qwen3-Coder 30B-A3B Q5 | `261.89` | `265.14 / 267.86 / 270.78` | `267.86` | `885` tokens, `stop`, content present |
| Qwen3.6-35B-A3B Q4 | `235.65` | `233.30 / 232.42 / 237.16` | `233.30` | `2048` tokens, `length`, content empty, reasoning present |

These are separate series by model artifact and offload/runtime configuration;
tok/s is not a quality or task-completion verdict. The Coder and a3b detailed
phase artifacts are under
`results/guardian-probe-20260919/coder/` and
`results/guardian-probe-20260919/a3b/`; the completed Qwen3.8 artifacts are
under `results/guardian-probe-20260919/qwen38/`.

## Historical SSH measurements with weak provenance

The following owner-supplied measurements were collected through ad-hoc SSH
`curl` calls and have no local manifest, request transcript, or series_key.
They are retained as `provenance=weak-owner-ssh-curl` and must not be promoted
to canonical results when the corresponding candidate is remeasured.

| Candidate/configuration | Reported result | Provenance limitations |
| --- | --- | --- |
| Qwen3.8-27B Q5, Codacus | clean hot `63.77` tok/s; contaminated `58.76` while `build -j24` ran; `512` tokens, `content=0`, `reasoning=2060`, `finish=length` | only 3 hot calls; no declared cold run/p95; one measurement was build-contaminated |
| Bonsai PTQ1_0, Prism | about `121.3` tok/s; `2048`-token cap; `finish=length` | only 2 calls; warm-up was not declared under the formal protocol; no cold run/p95 |
| Flash-Next IQ3_XXS, Codacus `--cpu-moe` | `11.16` cold / `16.18` hot tok/s; `1047` tokens; `finish=stop` | ad-hoc SSH source; no manifest/series_key; Flash-Next is outside current evaluation scope |
| Flash-Next IQ3_XXS, Codacus `--n-cpu-moe 32` | `15.47` cold / `26.98` hot tok/s; `1533` tokens; `finish=stop` | same weak provenance; distinct offload series; no formal p95 |

The Flash-Next values remain as historical reference for the mmap/offload
class, not as an evaluated guardian candidate. The clean and contaminated
Qwen3.8 value, and the Bonsai value, are superseded for decision-making by
hash-addressed T1/T2 runs when those runs exist.

## Typed decision probe: logprobs and one-token choices

`tools/typed_decision_probe.py` was added as a self-contained probe; it does
not install local-jev or another repository. Its SHA-256 is
`00347c5b4265ccedac900258b66da35bec7af74dc863727692eda2599c674fb2`. It uses
the same five packets from the frozen manifest, sends `max_tokens=1`,
`temperature=0`, `seed=42`, `logprobs=true`, and `top_logprobs=10`, and records
four independent questions per packet: state, attention, escalation, and
confidence. It records `labels_loaded=false`; therefore it measures mechanics,
distribution shape, and latency, never accuracy.

The Coder and a3b both tokenized the plain option letters as one token each:
`A` through `E` were IDs `32` through `36`. The space-prefixed forms were also
single tokens, but had different IDs. All 20 records per model returned
logprobs and all five plain option IDs were present in the returned top-10, so
the reported outside-option mass was exact for this run.

| Model/configuration | Median latency by question | Median entropy (state / attention / escalate / confidence) | Median outside-five mass |
| --- | --- | --- | --- |
| Coder Q5 | `1.53 / 1.90 / 1.90 / 1.90 s` | `0.00028 / 0.0617 / 0.1634 / 0.0221` nats | `0 / 0 / 1.4e-8 / 0` |
| a3b Q4, `enable_thinking=false` | `1.61 / 1.54 / 1.60 / 1.54 s` | `1.3739 / 0.9705 / 1.0648 / 0.6939` nats | `4.7e-4 / 4.1e-4 / 7.2e-4 / 2.2e-4` |

The Coder is sharply concentrated on the typed choices; the a3b no-think
distribution is substantially more diffuse, especially for state. This is not
an accuracy result. The artifacts are
`results/typed-decision-probe-20260920-coder.json` and
`results/typed-decision-probe-20260920-a3b-nothink.json`.

The four-question efficiency check did not reproduce the claim that several
questions cost almost the same as one. Across packets, four sequential
questions cost about `3.7x` the latency of the first state question for both
models, although the later requests showed llama.cpp prompt-cache hits
(`cache_n` around `43`). This measures the current HTTP/request design, not a
future stateful System One implementation.

A direct a3b no-think smoke also returned `SIM` with `finish=length` (expected
for a one-token cap), `content` populated, no reasoning content, and five
top-logprob alternatives. The same `enable_thinking` test was not run on
Bonsai: searching the PTQ1_0 GGUF found no `enable_thinking` marker, so support
was not observed and the model was not promoted by assumption.

Typed decisions remove generated-text truncation and channel-selection failure,
but they cannot produce literal evidence citations. The collector must attach
`path`, line ranges, and quotes deterministically; these probe distributions
must never be read as satisfying the watcher evidence contract or as model
accuracy.
