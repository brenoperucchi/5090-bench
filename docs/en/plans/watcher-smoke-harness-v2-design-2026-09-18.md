# Watcher smoke harness-v2 design — pre-run record

Status: **implemented and validated offline; no POST executed**

This record fixes only the two instrumentation defects identified in the
previous run and changes the evidence transport contract. It does not change
`watcher-threshold-v2` (`2b32cf94991365a0449a116cb4fd9ae40009e424b16df88a3891d2315e4c2778`),
the corpus, the labels, or the prior `NO_GO` result.

## Contract changes

1. Every packet carries a deterministic `slot_status` table derived from the
   round's `metrics.json` and filesystem. Each row contains `reviewer`,
   `dispatched`, `declared_status`, and `artifact_present`. Missing artifacts
   are represented as `artifact_present: false`; when a never-dispatched
   source does not identify a reviewer, the reviewer is `unknown`.
2. The packet's operational `regime` is now normative in the prompt. A
   `single-lens` round is outside dual-reviewer classification scope and must
   return `state=null`, `abstain=true`. This is operational scope metadata, not
   a sidecar label and not a gold state.
3. Model evidence changed from `{path, quote}` to
   `{path, line_start, line_end}`. Coordinates are 1-based and inclusive.
   The harness rejects paths absent from the packet, non-integer coordinates,
   and ranges outside the file. It extracts the referenced text itself and
   records `extracted_sha256` beside the validated response.
4. `later_round_exists` is derived from a numerically larger round suffix in
   the same mode only. Manifest order and lexical ordering are not used.

## B3 meaning under harness-v2

B3 is now a structural admission guard: it verifies packet membership and
   coordinate bounds, then records the hash of the extracted text. When all
   coordinates pass, B3 is structurally satisfied by construction and is not
   informative about model citation behavior. Semantic relevance of a valid
   coordinate is explicitly **unmeasured** and is deferred to the full pilot
   with the complete corpus. No new relevance metric or threshold is introduced
   into this smoke test.

An invalid path or coordinate remains a fail-closed B3 violation. The prior
   run's `NO_GO` remains immutable; the next result is a separate pair:
`(watcher-harness-v2, qwen3:14b)`.

## Deliberate information-boundary consequences

- The B3 barrier is structural under this harness: valid coordinates are
  admitted only after path/range validation and extraction, so B3 no longer
  measures whether the model can reproduce literal evidence. Semantic
  relevance of a valid coordinate is **not measured** here.
- The `out_of_scope_abstention` floor for `single-lens` is also satisfied by
  construction: `regime=single-lens` deterministically requires
  `state=null, abstain=true`. It verifies contract compliance, not model
  discernment.
- The still-informative quality criteria are S4 detection (with `review-1` as
  the binding form), false positives in `correction-in-progress`, and false
  positives in the two normal strata. B5 still measures repeatability of the
  projected state/abstention for the eligible rounds. B1/B2/B4 remain enforced
  safety/contract barriers, not evidence of product quality.
- No new metric, floor, or threshold is introduced; `watcher-threshold-v2`
  remains unchanged.

## Scope boundary

The only authorized implementation changes are the slot table, the explicit
single-lens rule/regime field, and coordinate extraction/validation. The
`review-3` model judgment remains untouched. The VRAM gate, two-pass design,
latency scope, model, and threshold remain unchanged.

## Offline validation

- `15 passed` in `tests/test_watcher_smoke_harness.py`;
- all 17 hash-addressed rounds load successfully offline;
- `review/claude-bridge-1` exposes `artifact_present=false` for
  `claude-bridge-rev-2`;
- `ask/claude-bridge-5` and `ask/claude-bridge-6` expose `regime=single-lens`;
- the generated prompt contains `line_start`/`line_end` and no `quote` field;
- no generation call, GPU/Ollama action, cleanup, or reset was performed.

Implementation hashes before the run:

- `tools/watcher_smoke_harness.py`:
  `6a1a221c885780241d07f70a5d40a75857a301affba6cac93a9d6f242ea841bf`
- `tests/test_watcher_smoke_harness.py`:
  `06dde15d071796fad46984fd82bd27bdf76f406b57948430bfcfb19b266c7027`
