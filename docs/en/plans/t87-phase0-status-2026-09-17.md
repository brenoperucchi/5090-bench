# T87 Phase 0 status — 2026-09-17

Status: **partial; no Phase 1 go/no-go yet**.

This record started as the low-cost provenance and feasibility record. On
2026-09-18, the owner accepted the bounded P1 authorization and the isolated
runtime was built and loaded, but no generation call has been made yet. No
cleanup, PID stop, production change, Ollama configuration change, commit, or
push was performed.

## P2 — provenance of the motivating instrument

The public `thecodacus/spec-wins` repository was inspected at main commit
`776e799c7e0a24271e021aca2ea4b1c1b1f10017`. Its visible history contains the
initial lab commit `ef55084` on 2026-09-06 and the rename commit `776e799` on
2026-09-06. The Qwen3.8 result file is present at blob
`89940897e044b22eed4cc216781a8217b47dc2e2` and describes the run as
2026-09-05, with 17/17 on Qwen3.8-Flash-Next 125B IQ3_XXS.

The benchmark, the published result, and the runtime author are not an
independent instrument chain: the repository identifies the lab as built for
the Codacus video, and the runtime used for the result is the Codacus fork.
The available history does not provide a pre-run snapshot proving whether
tasks or graders changed before the 2026-09-05 run. Therefore the result stays
an external claim with entangled provenance. A future reproduction must use a
frontier/control arm in the same runtime, or label the comparison explicitly
as model-plus-runtime.

## P3 — paper feasibility

- **P3.1, exact GGUF:** no `.gguf` file or exact Qwen3.8 125B filename/SHA-256
  was found under `/home/brenoperucchi`. The external result supplies only the
  `IQ3_XXS` label. Public availability of a matching file is therefore
  `unknown`, not proven absent; no large download is justified yet.
- **P3.2, original host RAM:** `unknown`. The current execution environment
  reports `MemTotal: 98646600 kB` (about 94 GiB), but that is not evidence about
  the original RTX 3060 host or the target Windows/RTX 5090 machine. The
  original host's RAM must be obtained from its author or a source snapshot.
- **P3.3, Blackwell build support:** the Codacus `llama.cpp` `perf` branch was
  built on the target WSL2 environment at commit
  `27c54b4bbcefadedcec6397477cc2e866c1db716`. The build used CUDA 12.8.93,
  GCC 13.3.0, and `120a-real`; the resulting `llama-server` SHA-256 is
  `37acf8e80c85f91794d9fa0268d34b40dbfa2f4286527a92bdd13dfefdab689b`.
  CUDA 12.8's isolated header compatibility patch and linker flags are
  recorded in the runtime packet; the project source was not patched.

- **P3.4, existing Qwen3.6 artifact:** a read-only GET of the Ollama catalog
  at the internal LAN endpoint returned `qwen3.6:35b-a3b` as `format=gguf`,
  `Q4_K_M`, `35.5B`, total size `22621314381` bytes, tag digest
  `096fdbd02fe620fc10cbeb6537e080f8041aece851e5d696aed024d4f70f2e47`, and
  parent `qwen3.6-source:35b-a3b-mtp-q4_K_M-20260824`. This is evidence that
  the installed Ollama package is GGUF-backed, not evidence that its tag
  digest is a standalone llama.cpp file hash. The effective text GGUF was
  copied to the dedicated P1 directory and verified as
  `d372de8e934898a59e6ccfabc3368474711384d8f1fd4d22d87a3f0a45400cdc`.

## P1 gate

P1 remains **not measured**: valid generation count is `0`; the original
v1 shape was `0/85`, while the corrected v2/v4 retry is bounded at 330
generations. The earlier local-Ollama
failure is a historical environment incident, not the current P1 verdict. The
owner authorization is accepted in
[t87-p1-authorization-accepted-2026-09-18](t87-p1-authorization-accepted-2026-09-18.md),
and the runtime is hash-addressed in
[t87-p1-runtime-packet-2026-09-18](t87-p1-runtime-packet-2026-09-18.md).
The original `0/85` execution shape was not started. Inspection of the pinned
instrument found three agentic task sessions (`t1_ratelimit`, `t2_metrics`,
`t3_pipeline`) and 17 hidden grader checks, so 17 synthetic model prompts
would not be a faithful P1. The corrected protocol is recorded in
`t87-p1-protocol-v2-2026-09-18.md`: five complete three-session executions,
with all intermediate turns retained and a bounded reference budget of 330
model generations across the campaign. No generation has been sent under v2.

The five seeded runs, per-task transcripts, and variance verdict remain
unavailable because the first v2 campaign was invalidated before grading.
The v2 packet recorded the isolated dependency bundle, GPU gate, persistent
sandbox boundary and exact sampling payload.

Correction: the first v2 campaign did send 330 POSTs, but its output is
`invalidated_before_grading`. The harness dropped the published task headings,
so the model never received the required task-directory instruction; every
session exhausted its cap while guessing paths, and no task was graded. The
raw transcripts remain at
`results/t87-p1-v2-2026-09-18-preparation-7/`; the assessment is
`invalidated-assessment.json`. This is not a P1 score or a model verdict. A
retry requires a new harness hash and runtime packet.

The corrected retry packet is
`docs/en/plans/t87-p1-runtime-packet-v4-2026-09-18.md`, currently
`owner_confirmation_required`; it preserves the same bounded 330-generation
scope, includes the task-heading correction, and fixes the measurement route
to the explicit LAN series `192.168.0.125:18087`. No v4 generation has been
sent. Runtime, model, protocol, and route are recorded in every preparation,
preflight, run, and transcript artifact; mixed `series_key` values are
rejected rather than aggregated.

The watcher smoke's `/v1/chat/local` path is not an implicit P1 harness: its
observed contract did not expose caller-selected seed. P1 must use a
controlled endpoint/runtime that accepts and records five distinct seeds, or
the result must be marked unable to answer the variance question. P4 remains
pending and must not be run until P1–P3 justify continuing.

## Current decision

The Qwen3.8 program is **not yet a go** and is not rejected. P2 changes the
claim boundary; P3 leaves the original-host feasibility unknown. The first
reproduction uses the isolated thecodacus `llama.cpp` fork, with runtime
identity and metric series separated from Ollama. The dedicated server is
healthy at the selected LAN endpoint `http://192.168.0.125:18087`, with
`22,817 MiB / 32,607 MiB` in use by the P1 process at the LAN preparation
snapshot and Ollama `/api/ps` empty. The next gate is owner review of the
immutable v4 runtime packet before the bounded P1 calls; no P1 result or
adoption decision exists yet.
