# Decisions and scope limits

**English** | [Português (Brasil)](../decisoes.md) · [English index](README.md)

> **Historical operational snapshot — through 2026-09-12.**
> This document describes the earlier Windows/Ollama production baseline.
> For the current Guardian research campaign and the WSL/llama.cpp environment,
> see [the current public record](findings/public-record-llm-bench-2026-09-20.md).

State documented through September 12, 2026. This is not a live server query.
Primary source: the [production decision](../../results/DECISAO-producao-2026-09-09.md),
read together with the [handoff](../history/handoff-2026-09-12.md) and the report corrections.

| Topic | Recorded decision | Evidence and limit |
|---|---|---|
| Customer support default | Keep `qwen3:14b` | 40/45 in the resampling of 9 critical cases; escalation defects concentrated in one case. This does not imply an absence of language failures or general coverage. |
| Second resident model | `qwen3.5:9b` | Fits alongside the default; 0/4 on the corrected full contract for multi-round research, so that role requires further evaluation. |
| KV cache | `q8_0` | Recorded reduction of 4.62 GiB for `qwen3:14b`; 40/45 on the same nine cases under f16 and q8. Neutrality beyond this sample has not been demonstrated. |
| Concurrency | `NUM_PARALLEL=2` | [Phase 6](../../results/RESULTADO-fase6-numparallel-2026-09-05.md), with one model at a time and 2,108-token prompts. |
| Residency | `MAX_LOADED_MODELS=2` | [Phase 1](../../results/RESULTADO-fase1-contexto-maxloaded-2026-09-04.md); measured effect on reloading, not on two resident models serving requests simultaneously. |
| Flash Attention | Variable unset | On/off A/B had no observable effect; it does not isolate whether the feature was actually enabled internally. |
| Judge on the goldset | Do not use | [Labeled comparison](../../results/comparacao-check-vs-juiz-2026-09-10.json): check 12/12, 0 FP; best judge 11/12, 3 FP. |
| Judge in production | Possible, not implemented | The measurement enables an option; no consumer requested it. There is no judge to turn off. |
| Judge against rubrics | Do not measure with this design | [Probe and check extensions](../../results/RESULTADO-juiz-familia-2026-09-10.md): largely redundant, with no automatic ground truth for the remainder. |
| Canonical prompt | Preserve | [Correction attempts](../../ACHADO-qwen3-14b-pricing-leak-2026-09-04.md) v1/v2/v3 did not resolve the full set of issues; v2 lost the token in 50% of legitimate `qwen2.5:14b` escalations in the cited measurement. |
| Long context | Mechanism unresolved; no configuration change | [Phase 6b correction](../../results/RESULTADO-fase6b-numparallel-contexto-longo-2026-09-12.md): does not demonstrate a benefit from changing `NUM_PARALLEL` to 1. |

## Withdrawn recommendations

**Guard based on literal escalation text:** matching the prompt block does not
distinguish LEAK from legitimate escalation. In the resampling, the same 267 bytes
occurred in 5 errors and 20 legitimate escalations; the guard would have had 20%
precision. The signal depends on the question and its expected behavior.
[Retraction record](../../results/DECISAO-producao-2026-09-09.md).

**Offline judge and claims about model families:** the first recommendation
confounded family with size, and another version used responses truncated by the
harness itself. The corrected remeasurement is preserved; the labeled check
removes the justification for an offline judge.
[Report with corrections](../../results/RESULTADO-juiz-familia-2026-09-10.md).

**“`NUM_PARALLEL` divides each slot's context”:** the log records 98,304 tokens
per slot and 196,608 in total with two slots. Truncation occurs, but this
allocation explanation was contradicted. Two hypotheses predict the same value
in the observed scenario.
[Causal correction](../../results/RESULTADO-fase6b-numparallel-contexto-longo-2026-09-12.md).

## Open questions that qualify the decision

The 196 judge-evaluation pairs come from nine questions, and one accounts for
eight of the twelve defects. Applying this grouping criterion to the model
selection itself remains an open question. The documentation preserves the
operational decision and the statistical limitation; it does not declare an
overall winner. See [open questions](open-questions.md) and [models](models.md).
