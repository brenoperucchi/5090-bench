# T87 P1 runtime packet v3 — corrected prompt preservation

Status: `owner_confirmation_required`; no generation POST has been sent under
this packet.

This is a correction retry packet. The first v2 campaign is retained as
`invalidated_before_grading` in
`results/t87-p1-v2-2026-09-18-preparation-7/`: the parser dropped the task
headings, every session guessed paths until its cap, and no grader ran. The
v2 raw 330 generations are not a P1 score and do not transfer to v3.

## Proposed retry scope

The retry keeps the accepted v2 measurement shape unchanged:

- five complete executions of the unmodified `spec-wins` source;
- fresh `t1_ratelimit`, `t2_metrics`, and `t3_pipeline` sessions per execution;
- seeds `1000, 1017, 1034, 1051, 1068`;
- 17 grader checks per execution (`7 + 8 + 2`);
- maximum 330 model generations using reference caps `13/27/26`;
- no synthetic warm-up generation.

The only harness correction is preservation of the published task heading as
`Task — cd ~/lab/<task>` in each user prompt. The corrected parser was tested
against all three task blocks and the tool boundary accepted the corresponding
`ssh lab 'cd ~/lab/<task> && ...'` command shape.

## Hashes

- Protocol: `t87-p1-protocol-v2-2026-09-18.md`, SHA-256
  `e4c19e5d691cf6aa781dc66c0ba9e1925f459c52eaac397470596d455903ab20`.
- Harness: `tools/t87_spec_wins_harness.py`, SHA-256
  `bc3463618f712e708fd35edfed6833300b1895bcaeb725b446d3c9fc3310bf16`.
- Preparation: `results/t87-p1-v2-2026-09-18-preparation-8/preparation.json`,
  SHA-256
  `7ad1a98182145afbbd89ad63b456c432a0d42f12bf1f7ab03c287e4b8b0c9139`.
- Benchmark commit: `776e799c7e0a24271e021aca2ea4b1c1b1f10017`.
- Runtime commit: `27c54b4bbcefadedcec6397477cc2e866c1db716`.
- Runtime binary SHA-256:
  `37acf8e80c85f91794d9fa0268d34b40dbfa2f4286527a92bdd13dfefdab689b`.
- GGUF SHA-256:
  `d372de8e934898a59e6ccfabc3368474711384d8f1fd4d22d87a3f0a45400cdc`.
- Dependency bundle SHA-256:
  `7293488bdf2c6ae0d9cdaef39dd8ef019c841f84641026624d8bc1263176aa7f`.

Sampling, server context (`32768`), persistent sandbox, grading boundary and
interpretation remain exactly those recorded in the v2 runtime packet. The
preparation GET at `2026-09-18T16:08:57Z` saw the expected model and
`NVIDIA GeForce RTX 5090, 22749 MiB, 32607 MiB, 0 %, 616.64`.

## Gate

Owner confirmation is required before `tools/t87_spec_wins_harness.py run`
is invoked with this packet. A confirmation authorizes only the bounded v3
retry above; it does not authorize any gateway/Ollama change, Herdr
cleanup/reset, production traffic, commit or push.

