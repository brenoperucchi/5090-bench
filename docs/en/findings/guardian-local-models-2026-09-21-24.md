# Guardian synthesis on a local RTX 5090 — record, 2026-09-21 → 24

**English** | [Português (Brasil)](../../achados/REGISTRO-GUARDIAN-MODELOS-LOCAIS-2026-09-24.md)

This record consolidates four days of measurement for the **Guardian**: a
component of another project (`claude-bridge`) that reads an automatic
chronology of an agent's screen and writes a synthesis for the owner — what is
being built, what worked, what failed, what is unverified and what waits for his
decision. The llm-bench measured; the prompt and the Guardian code belong to the
other project and were never edited here.

> **What is public and what is not.** The raw evidence (chronology snapshots,
> model answers, blind rating forms, shadow lots) contains data from other
> projects — account identifiers, third-party names, credentials in context — and
> stays on the lab machine (`.gitignore`, section on Guardian evidence). This
> document carries the numbers, methods and conclusions. The tools that produced
> them are in `tools/` and are public.

## 1. Rating method (applies to everything below)

- **Rubric 4**, blind forms, two independent raters (`rev-1`, `rev-2`) per
  response; disagreements on a criterion that fails the agreement gate go to a
  third blind arbitration (`scout`), and those numbers are marked *arbitrated*.
- **Agreement gate** per criterion (`GATE-REGRAS-v3`): Cohen's κ / Gwet's AC1,
  n ≥ 7, and **A2 by Spearman ρ ≥ 0.80** (A2 is a count). The instrument gate
  passed on both axes on a never-seen sample before any campaign.
- **Only never-seen material** goes to a gate; seeds that were already rated are
  never reused (at t = 0 an answer is deterministic and was already seen).
- **Rules frozen before the data**: every experiment has a rules file written and
  hashed before the first model call; amendments are recorded, never silent.

Main criteria: **A1** polarity inversion (a `worked` item told as failed or
vice versa), **A1r** demotion of a worked item outside the gaps section, **A2**
count of `unverified` items stated as fact without a caveat, **A5** machine,
place, cause or action with no source item, **C1** pending decisions first,
**C3** three separate lists (worked / failed / unverified), **C4** no false gap.

## 2. Runtime — the same GGUF on Windows 11 and on WSL2

llama.cpp `llama-server` b11053 (commit `1af554f`), CUDA 13.4, `sm_120`, same
GGUF bytes, server-side timings, 3 repetitions × 3 prompt sizes.

| Model | Generation WSL → Windows (tok/s) | Long prefill WSL → Windows (tok/s) |
|---|---|---|
| qwen3.8-27B Q4, baseline | 74.2 → 76.2 | 3,074 → 3,494 |
| **qwen3.8-27B Q4, tuned** | 75.2 → 76.3 | 3,492 → 3,584 |
| NVFP4, baseline | 74.3 → 76.5 | 3,612 → 4,762 |
| **NVFP4 + MTP, tuned** | **126.7 → 125.8** | 3,494 → 4,275 |
| Hemmingway-1 Q4, tuned | 72.7 → 74.0 | 3,579 → 3,628 |
| **Qwen3.8-35B-A3B APEX + MTP** | **271.9 → 302.4** | 7,134 → 8,331 |

- Tuning was decided by rules frozen before measuring: `-ub 1024 -b 4096`
  adopted (+8% long prefill); `-fa on` rejected (prefill −2.6%); KV `q8_0`
  measured only (slower); **MTP `--spec-draft-n-max 2`** adopted on the NVFP4
  (+70% generation, 68% acceptance). APEX's MTP head ships as a separate file
  (`-md … --spec-type draft-mtp`), +17% (WSL) / +24% (Windows).
- **Same text on both OSes:** with identical flags, 79 of 80 synthesis answers
  were byte-identical WSL × Windows; the one exception is NVFP4 + MTP at t = 0.3
  (MTP is not fully deterministic). An apparent 8/16 mismatch earlier came from
  mixing runs with and without `-ub/-b`, which does change the text.
- MTP changes the generated text relative to no-MTP even at t = 0.
- A `llama-server.exe` started from WSL through interop keeps the SSH session
  open; the launcher must not wait for it.

## 3. Which local model for the synthesis

Prompt `atual` (the production one), 16 runs per model on WSL, then a blind
human sample of 6 per model.

| Model | A1 inversion | A2 ≥ 6 items | A5 no source | C1 |
|---|---|---|---|---|
| production `qwen3-coder-30b` (reference) | inverts a key fact in pre-screen | 8/8 (earlier round) | — | 0 |
| qwen3.8-27B Q4 | 2/6 *(arbitrated)* | 5–6/6 | 4/6 | 5/6 |
| NVFP4 + MTP | 2/6 *(arbitrated)* | 4–6/6 | 6/6 | 6/6 |
| APEX 35B-A3B + MTP | **5/6** *(arbitrated)* | 5–6/6 | 6/6 | 0/6 |

- **A2 and A5 appear with every model** — they come from the prompt, not the
  model. That redirected the work to the prompt (sections 4–6).
- Q4 and NVFP4 are equivalent on A1 in this sample; APEX is recorded as a
  **risk signal** (n = 6, decided by arbitration). APEX also loops at t = 0.3
  (2/16 answers ran to the context limit), as its author warns for greedy use.
- Also evaluated and not pursued: Ternary Bonsai (PQ2/PTQ1, needs the PrismML
  fork; failed the key fact 0/4), Xing4.0-29B-A4B (needs an unmerged llama.cpp
  PR; deleted), TAARDIS ternary, abliterated variants (no benefit for this task).

## 4. Prompt campaign: `atual` × `v2` × `v3` (production model)

18 never-seen answers (6 per arm, t = 0.3, seeds 48/49). A1r, A5 and C2 failed
the agreement gate and were arbitrated.

| | atual | v2 | v3 |
|---|---|---|---|
| A2 (sum of bands, max 18) | **13.5** | 17.0 | 15.5 |
| A5 | 6/6 | 2/6 | 2/6 |
| C1 | 0/6 | 6/6 | 6/6 |
| C3 | 0/6 | 4/6 | 4/6 |
| A1 | 3/6 | 0/6 | 0/6 |
| output tokens | 1.3k–1.6k | 5k–9k | 5k–8.7k |

**v3 does not reduce A2 and does not bring A5 back.** v2/v3 answers are 4–6×
longer and hit the 16K context on the longest slice.

## 5. Where A2 comes from

**H-LEDGER-A2** (v3 with × without the final JSON *ledger*, 9 each, A2 ρ =
0.986): without the ledger, absolute A2 falls (mean 16.2 → 13.8) but **A5 comes
back (2/9 → 8/9) and C4 drops (8/9 → 4/9)**. The ledger stays.

> **Correction.** This record first said "A2 per 1k tokens rises without the
> ledger, so the effect is length". That was a **denominator artefact**: the
> ledger is ~58% of the output and has almost no violations. Against prose only,
> A2 density is *higher* with the ledger (1.67 × 1.31 per 1k characters). The
> original reading is kept in the raw report; this is the corrected one.

**H-PROSA-A2** (attribution rule frozen first, 24 sampled violations validated
by hand, 24/24 location confirmed): **every resolved A2 violation is in the
prose, none in the ledger** — the ledger labels `unverified` correctly in 254 of
256 matched entries. Prose A2 density 5.39 / 3.14 per 1k tokens (rev-1 /
rev-2) against 0.02 in the ledger.

## 6. `v3-compact` and the context window

**H-PROSA-COMPACT**: drop the textual tree and the visual form (both already in
the ledger), everything else byte-identical. 9 per arm, A2 ρ = 0.84.

| | v3 | v3-compact |
|---|---|---|
| prose A2 (rev-1 / rev-2) | 145 / 96 | **52 / 38** |
| prose A2 per 1k tokens | 5.22 / 3.45 | **2.54 / 1.86** |
| ledger A2 | 1 / 1 | 0 / 0 |
| C1 · C3 · A5 · C4 | 9 · 5 · 2 · 4 | 9 · **7** · 2 · **6** |

Prose A2 halves in absolute and in density; no protection regresses. Per block,
~40% of v3's violations lived **only** in the textual tree or the visual form;
what remains in compact sits in the **pending-decisions block**.

**H-NCTX-COMPACT**: compact still truncated on the longest slice at 16K. KV
cache f16 = 96 KiB/token for this model → 32K costs +1.5 GiB; measured +1.43
GiB. At 32K both truncated cases end with `stop`, with no throughput loss
(226 → 229 and 224 → 232 tok/s). They are new generations, not the same text
completed. Production now runs at 32K; compact became a shadow candidate.

## 7. Deterministic desk test (A2 / A5 / C1 without humans)

| Version | Where measured | A2 Spearman rev-1 / rev-2 | C1 | Result |
|---|---|---|---|---|
| v1 | 54 rated answers | 0.276 / 0.149 | 100% | rejected |
| v2 | same 54 (in-sample) | 0.871 / 0.850 | 100% | provisional only |
| v2 | **shadow lot V1** (20 new) | 0.719 / 0.753 | 100% | **failed** |
| v3 (last) | **shadow lot V2** (20 new) | 0.752 / 0.670 | 100% | **failed** |

- v1 punished answers that list items correctly under an "Unverified"
  sub-header (the caveat lives in the header); v2 inherited the caveat and fixed
  it; v3 added the ledger tree, logical items and short items.
- On lot V2 the two humans agreed only ρ = 0.782 with each other (0.965 on V1):
  the ceiling for the test fell below its own threshold.
- **Outcome:** the desk test is an **indicator, not a gate**. C1 is reliable
  (100% on every lot). A5 by named entities is descriptive only.

## 8. Typed decisions: Laya, Jev, Eikos

Same labelled batch (27 cases, one positive per question — a direction signal,
not a fine number).

| System | `encerra`: rank of the positive | `quem_decide`: precision / acc / rank | margin right × wrong | latency |
|---|---|---|---|---|
| trivial "always no" | tie | — / 0.95 | — | — |
| Laya (22/09 and 24/09, pkg 0.3.17) | 5th | 0.06 / 0.25 / 5th | 0.37 × 0.53 (inverted) | 0.03 s |
| Jev (hosted) | 1st | 0.25 / 0.85 / 1st | 0.69 × 0.20 | 0.66 s |
| Eikos-4B (local) | 4th | 0.33 / 0.90 / 2nd | 0.60 × 0.37 | 0.11 s |
| **Eikos-27B-INT4 (local, vLLM)** | **1st** | **0.33 / 0.90 / 1st** | **0.69 × 0.21** | **0.14 s** |

- **Eikos-27B matches or beats the hosted Jev on this batch**, runs locally
  (data never leaves the machine), is deterministic and ~4.7× faster. It needs
  vLLM ≥ 0.30 (`--enforce-eager` here: CUDA-graph capture hung) and ~26 GB of
  VRAM, so it does not fit next to the production model.
- The updated `laya-multilingual` reproduced its 22/09 scores exactly (27/27).
- **Experiment 1** — the typed model only filters the desk test's A2
  candidates ("does this excerpt state the item as fact?"): no system lifts the
  desk test above 0.80 on lot V2 (Jev 0.650/0.736, Eikos-4B 0.740/0.742,
  Eikos-27B 0.746/0.715); on lot V1 every filter makes it worse. The bottleneck
  is the question, not the model.

## 9. Operational cost and lessons

- **Swapping production for Eikos-27B and back** costs ~4 min out (weights 1 min
  53 s from `/mnt/e` over WSL's 9P filesystem, vLLM profiling ~1 min 40 s) and
  ~2 min back — ~6 min without the production model.
- A stopped `llama-server` can release its port and keep 21.6 GB of VRAM; stop
  servers by the pid on the port, kill the process group, and wait until VRAM is
  actually free.
- Never `pkill -f` / `pgrep -f` with text that appears in the command itself.
- In Herdr, a dim (`ESC[2m`) line in a pane's input is a CLI suggestion, not a
  human draft; read with `--format ansi` before deciding.
- While production was down, an unknown client loaded a model on the Windows
  Ollama service, and something polled `GET /props` on the vLLM port. Service
  ownership and a pause/resume control are being taken to the gateway project.

## Tools

`tools/os_runtime_ab.py`, `tools/optimization_campaign.py`,
`tools/synthesis_wsl_campaign.py`, `tools/guardian_synthesis_bench.py`,
`tools/guardian_agreement.py`, `tools/h_prosa_attribution.py`,
`tools/h_block_attribution.py`, `tools/desk_test.py` (v1),
`tools/desk_test_v2.py`, `tools/desk_test_v3.py`,
`tools/shadow_lot_forms.py`, `tools/typification_eval.py`,
`tools/jev_hybrid_a2.py`, `tools/eikos27_window.sh`.
