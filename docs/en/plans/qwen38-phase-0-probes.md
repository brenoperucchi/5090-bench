# Phase 0 — cheap probes before the Qwen3.8 runtime program

Status: **action plan; P2/P3 read-only evidence is partial, P1 unmeasured**.
This document orders the work of
[PLANO-qwen38-expert-cache-2026-09-16.md](../../external/PLANO-qwen38-expert-cache-2026-09-16.md)
by cost instead of by narrative. It adds four probes that run before any fork is
built or any GGUF is downloaded, and it states, for each one, the result that
ends the program.

The current partial execution record is [T87 Phase 0 status — 2026-09-17](t87-phase0-status-2026-09-17.md).

The parent plan proposes eleven experiments, two `llama.cpp` forks, five
candidate models and a new judgment set. All of it rests on a single published
comparison: 17/17 for Qwen3.8-Flash-Next 125B IQ3_XXS against 14/17 for
Qwen3.6-35B-A3B on `spec-wins`. That is an **EXTERNAL CLAIM**, one run per
model, seventeen tasks, a three-task margin, with no reported variance. The
probes below either give that claim an error bar and a feasible path, or they
stop the program for a few hours of otherwise idle GPU time.

Each probe carries an explicit kill criterion. A probe whose kill criterion
fires is a result, not a failure, and gets written to `docs/achados/` like any
other finding.

## Cross-cutting gate — runtime and metric identity

The first Phase 0 reproduction uses the **thecodacus `llama.cpp` fork**, not
Ollama. Every generated record and aggregate must carry an immutable runtime
identity: repository, branch, commit, build flags, binary hash, endpoint,
model artifact hash, execution context (native Windows or WSL2/session), and
the network route as a first-class field (`route.id`, `route.host`,
`route.port`, and request path). The current P1 route is `lan` via
`192.168.0.125:18087`; the Tailnet route is a distinct series even though it
reaches the same host.

The harness must refuse to aggregate records whose runtime identity, model
artifact, execution context, route, or metric definition differs. Ollama and
`llama.cpp` values are separate series; LAN and Tailnet routes are separate
series; tokens/s, prefill, context accounting, keep-alive semantics, load time,
and residency are not silently comparable. A consumer that receives mixed
`series_key` values must fail closed rather than sum them.
Any cross-runtime comparison must be an explicit A/B with a declared metric
definition and matching workload, otherwise it is labeled
`model-plus-runtime` or `unknown`.

The prior Windows-native-versus-WSL2 observation is historical evidence only.
It does not transfer to the forked `llama.cpp`; the execution context and
session/GPU visibility must be recorded in the dedicated A/B. In particular,
the previous Session 0 versus interactive-session incident showed that equal
configuration text does not establish GPU use.

## P1 — Variance of the motivating result

**Question.** Is the 17/17 against 14/17 gap larger than the run-to-run spread
of `spec-wins` itself?

**Method.** Run the unmodified `spec-wins` suite against `qwen3.6:35b-a3b`
through the isolated, pinned thecodacus `llama.cpp` runtime, five times with
distinct seeds. Do not touch
`hidden/`, `solutions/` or `docs/answer-key.md`. Record per-task pass/fail, not
only the total, so the spread can be attributed to specific tasks. Keep every
transcript.

**Why this is first.** It is the only probe that can invalidate the premise of
the whole program, it needs no new runtime, no download and no purchase, and the
model is already resident.

**Kill criterion.** If the five totals straddle 17 — or if their spread is wide
enough that 14 and 17 are not distinguishable at this sample size — then the
published gap is not established evidence of a judgment difference, and the
125B program loses its justification in its current form. Record the finding and
stop before Phase 1.

**Caveat to record either way.** Five runs of one model bound the benchmark's
own noise. They do not bound the 125B's noise, which stays unmeasured until P4
or later.

## P2 — Provenance of the instrument

**Question.** How independent are the benchmark, the runtime and the result?

**Facts already established.** `thecodacus` authored `spec-wins`, authored the
`llama.cpp` fork on branch `perf`, and published the Qwen3.8 result obtained
with that fork on that benchmark. The parent plan treats the benchmark as a
neutral instrument (section 14.2) and the fork as a runtime to reproduce,
without recording that they share one origin.

**Method.** No execution. Read the `spec-wins` commit history and check whether
tasks or graders were added or adjusted while the fork was being developed, and
whether any task postdates the Qwen3.8 run it scores. Record dates and commit
SHAs.

**Consequence if entangled.** The parent plan's section 14.3 dispenses with a
frontier arm because "an external result already exists". That dispensation is
exactly what a shared-origin instrument does not allow. In that case add a
frontier arm by API to the Phase 6 reproduction, as an independent reading of
the instrument rather than as a competitor.

**This probe does not stop the program.** It changes what the Phase 6 numbers
are allowed to claim.

## P3 — Feasibility on paper

Three questions, none of which needs the model in hand. Any one of them can end
the program in under an hour.

**P3.1 — Does the weight footprint fit 64 GB?** IQ3_XXS runs near 3.0–3.1 bits
per weight including overhead, so 125B parameters land in the neighbourhood of
45–50 GB of weights alone, before KV cache, runtime buffers, MTP structures and
the operating system. Confirm against the actual GGUF file size rather than this
estimate; the estimate only says whether the question is tight, and it is.
This settles H5 and H6 on paper instead of in Phase 10.

The locally observed Ollama catalog entry for `qwen3.6:35b-a3b` is a separate
fact: `format=gguf`, `Q4_K_M`, `35.5B`, `size=22621314381` bytes, tag digest
`096fdbd02fe620fc10cbeb6537e080f8041aece851e5d696aed024d4f70f2e47`, and
parent model `qwen3.6-source:35b-a3b-mtp-q4_K_M-20260824`. The tag digest and
total size do not identify the standalone GGUF layer(s). Before P1, enumerate
the Ollama manifest/layers or obtain the source artifact, then record each
GGUF filename, byte size, SHA-256, and whether an MTP/draft artifact is also
required. A llama.cpp run cannot be authorized from the tag digest alone.

**P3.2 — How much RAM did the original host have?** The published run used an
RTX 3060 12 GB, which means host memory carried most of the model. If that host
had 96 or 128 GB, the ~19 tok/s figure may be unreproducible on 64 GB for a
reason unrelated to the RTX 5090. This is one question to the author, not a
phase.

**P3.3 — Does the fork build for Blackwell?** The RTX 5090 is `sm_120`.
Performance forks routinely lag upstream on new architecture support. Check the
fork's CUDA architecture list and CI before downloading tens of gigabytes of
weights.

**Kill criterion.** No public GGUF matching the described quantization; or a
weight footprint that leaves no headroom on 64 GB and the parent plan's rule
against buying RAM before measurement holds; or no `sm_120` support and no
tractable patch. Any of these stops Phase 2 and redirects the program.

## P4 — Environment snapshot

This is the parent plan's original Phase 0 (its section 8) and it stays
mandatory, but it runs after P1–P3, because a snapshot of a machine that will
never run the experiment has no consumer.

Record Windows build, NVIDIA driver, CUDA exposed by the driver, GPU, total and
free VRAM, CPU, RAM, BIOS memory speed where available, negotiated PCIe link,
Ollama version, resident models, Ollama environment variables, power limit, idle
temperature, processes holding the GPU, and the current `llm-bench` SHA. Write
to `results/runtime-next/baseline/environment.json` and the matching `.md`.

## Design correction to carry into Phase 6

Independent of the probes: the parent plan's section 14.3 names a local Qwen3.6
control arm without naming its runtime. If arm A runs on the Codacus fork and
arm B on Ollama, any quality difference is confounded with runtime, chat
template and sampling defaults. The parent plan enforces exactly this discipline
in section 16.1 and drops it in the comparison that carries the most weight.
Both arms must share a runtime, or the comparison must be labelled as
model-plus-runtime rather than model.

Note also that the parent plan's headline metric, Useful Work per Wall-Clock
Minute (its section 21), is the only metric in the document with no schema,
no formula and no defined denominator, while `pcie_tx` has one. It needs an
operational definition before Phase 6 produces numbers that are supposed to be
read through it.

## Work that does not depend on any of this

The internal judgment set (parent plan section 15, EXP-09) needs no 125B, no
fork and no download. Its seven Rails cases — callback against ADR, cross-tenant
leak, destructive migration, webhook idempotency, float money, N+1, mocked false
fix — can be built and run against the models already local. If current models
fail those traps, that is a finding of our own, on our data, available now.
Consider detaching it from this program and running it in parallel.

## Exit condition for Phase 0

Phase 0 is complete when the following are written down, whatever they say:

- the five `spec-wins` totals for Qwen3.6, per task, with transcripts kept;
- whether the 17/17 against 14/17 gap survives that spread;
- the origin entanglement of benchmark, runtime and published result, with dates;
- the GGUF's existence, exact filename, size and SHA-256, or its absence;
- the host memory of the original run, or an explicit unknown;
- whether the fork targets `sm_120`;
- the environment snapshot, if the program continues;
- a go or no-go for Phase 1, with the reason.

A no-go recorded with evidence is a successful Phase 0.
