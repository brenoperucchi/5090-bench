# Measured models and usage limits

**English** | [Português (Brasil)](../rtx5090/modelos.md) · [English index](README.md)

> **Historical operational snapshot — through 2026-09-12.**
> This document describes the earlier Windows/Ollama production baseline.
> For the current Guardian research campaign and the WSL/llama.cpp environment,
> see [the current public record](findings/public-record-llm-bench-2026-09-20.md).

Documentary inventory through the [September 12, 2026 handoff](../history/handoff-2026-09-12.md). This is neither a list of current market recommendations nor a live inventory. Tags are preserved as they appear in the artifacts. A model being available, researched, or mentioned in a plan does not mean it was measured. Historical source reports remain in Portuguese.

## Recorded decision

`qwen3:14b` remains the default; `qwen3.5:9b` is the planned second resident in the [production decision](decisions.md), documented in the [historical source](../../results/DECISAO-producao-2026-09-09.md). At the handoff snapshot, only `qwen3:14b` is explicitly confirmed resident. No LLM judge was adopted. The coding goldset remains pending: support results do not select a model for writing code.

## RTX 5090 — generation and support

The two speed columns are **different experiments**: “bench” uses three prompts without a system prompt × two runs, in the first September 4 measurement; “chat” is the average from the indicated canonical support round. Do not combine them to calculate a single ranking. No `auto_score` ranking is published: its denominator changed on September 10, and one pass per case does not estimate robustness.

| Measured model/tag | Bench, tok/s | Chat, tok/s | Observed quality/use and limit |
|---|---:|---:|---|
| `qwen3:14b` | 127.77 | 135.2 | Default retained. 40/45 on the 9 critical cases; QuickBooks LEAK in addition to pricing. Corrected multi-round result 5/5. PT→EN in the three Portuguese step-by-step cases: 15/15. Not defect-free. |
| `qwen3.5:9b` | 162.23 | 183.2 | 38/45 on critical cases, defects in 3 cases. Corrected multi-round result 0/4 on the full contract because of citations/protocol; its single-shot 8/8 should not be treated as a guarantee for chains. |
| `qwen2.5:14b` | 128.37 | 138.5 | Native tool 1/8; JSON in the prompt 8/8. Same template block as the control; cause not isolated. Do not confuse a good support round with robustness under the native transport. |
| `qwen3:8b` | 198.10 | — | Measured for speed, OS/CUDA A/B, and residency configurations. No 5090 quality round equivalent to Phase 0 was located. |
| `qwen3:30b-a3b` | — | 293.4 | Reasoning exposed in 18/18 responses despite `think:false`. Two tested interventions did not resolve it; content after any removal was not systematically revalidated. |
| `qwen3-coder:30b` | — | 265.2 | QuickBooks LEAK 4/5. Tested on support and long-context handoffs; no completed coding goldset exists. |
| `laguna-xs-2.1` | — | 258.5 | QuickBooks LEAK 4/5; a high initial-pass score hid the defect. Coding specialist tested outside its domain. |
| `glm-4.7-flash` | — | 204.4 | QuickBooks LEAK 2/5 in selected resampling. No promotion recorded. |
| `gpt-oss:20b` | — | 259.8 | Wrong-numbers escalation MISS 2/5 (3/5 correct), not 3/5 failures. Response fabricated specific troubleshooting. |
| `qwen3.8:27b` | — | 126.0 | 38/45 on critical cases, 4 defective cases including MISS; corrected multi-round contract 5/5. No demonstrated advantage that prompted replacing the default. |
| `deepseek-r1:32b` | — | 68.6 | The 18-case round contains 1 HTTP 500; a chat average does not turn 17 responses into 18 successes. No equivalent resampling or completed Phase 7. |
| `llama3.2:latest` | 319.30 | — | Generation and judging measured; speed does not establish support quality. |
| `gemma3n:e2b` | 197.18 | — | Generation and judging measured; insufficient evidence of judging ability in this sample. |
| `ministral-8b:latest` | 206.19 | — | Tag present in the generation benchmark. Judge report uses `ministral-8b`; digest identity cannot be inferred from the name alone. |
| `hf.co/bartowski/Ministral-8B-Instruct-2410-GGUF:Q4_K_M` | 202.49 | — | Distinct tag in the benchmark. Do not merge the two Ministral rows without a digest proving equivalence. |

Sources: [bench with hardware and averages](../../results/bench_20260904_043001.json); [Phase 0](../../results/chat_raw.gpu5090-baseline.json); [new MoEs](../../results/chat_raw.gpu5090-novos.json); [27B](../../results/chat_raw.gpu5090-qwen38.json); [R1 32B](../../results/chat_raw.gpu5090-deepseekr1.json); [corrected Phase 2](../../results/RESULTADO-fase2-modelos-novos-2026-09-04.md); [incumbent resampling](../../results/RESULTADO-reamostra-qwen3-14b-2026-09-08.md); [Phase 4 and missing raw data](../../results/RESULTADO-fase4-toolcalling-qwen35-2026-09-05.md); [corrected Phase 7](../../results/RESULTADO-fase7-multirodada-schema-2026-09-07.md); [PT→EN](../../results/reamostra_pt_escalacao_1789114271.json).

## RTX 5090 — models as escalation judges

This is a different task: judging 196 labeled pairs from 9 questions, containing 12 defects. It does not measure generation of customer responses. The table uses the round without response clipping, with a supplement for the single HTTP error.

| Judge | Defects detected / 12 | False positives | Supported reading |
|---|---:|---:|---|
| `llama3.2:latest` | 8 | 126 | Flags 134/196; no signal beyond chance. |
| `gemma3n:e2b` | 4 | 121 | No signal in this sample. |
| `deepseek-r1:8b-llama-distill-q4_K_M` | 3 | 26 | Actual documented tag; report abbreviates the name. Needs a budget for `thinking`; no demonstrated signal. |
| `ministral-8b` | 0 | 0 | Approves all 196; detects no defects. |
| `qwen3.5:9b` | 7 | 0 | 100% precision across seven flags; catches only LEAK, none of the three MISS cases. |
| `qwen3:14b` | 3 | 1 | 75% precision; per-question test gives p=0.069, not significant under that adjustment. |
| `gemma4:26b` | 11 | 3 | 79% precision; catches 9/9 LEAK and 2/3 MISS. Cannot coexist with the default in VRAM. |
| `run_auto` check (not an LLM) | 12 | 0 | Labels already specify whether escalation was expected. Retained solution for this goldset, without inference/GPU. |

Clustering matters: one question accounts for 8/12 defects. Size and family vary together, so there is no proof that size **causes** the difference. Do not interpret 0 FP among 61 legitimate escalations as a zero population rate: those cover only four questions. [Full report](../../results/RESULTADO-juiz-familia-2026-09-10.md), [valid measurement](../../results/juiz_grande_1789065587.json), [supplement](../../results/juiz_grande_1789065587_complemento.json), [check × judge](../../results/comparacao-check-vs-juiz-2026-09-10.json).

## Memory and coexistence: configuration is part of the number

| Model/pair | Documented measurement | Consequence |
|---|---|---|
| `qwen3:14b` | 13.55 GiB with f16/NP=1; 18.55 with f16/NP=2 in Phase 6; 13.93 GiB in the later q8_0 state | Do not treat VRAM as a model constant. Context, parallelism, and KV must accompany the number. |
| `qwen3.5:9b` | 5.73 GiB with q8_0 | Paired with `qwen3:14b`: 19.66 GiB in the documented configuration, below the ~30.3 usable. |
| `qwen3.8:27b` | 16.33 GiB documented | The combined 30.26 GiB with the 14B was deemed to leave no operating margin in the decision; do not claim safe coexistence from the rounded sum. |
| `gemma4:26b` | ~17.5 GiB, 25.23B target + 419.71M draft | Combined with the default, ~31.4 GiB; loading it evicted `qwen3:14b`. `/api/ps` reports only the draft's ~1.38 GiB and is insufficient evidence of full residency. |

Sources: [Phase 6 rerun after fixes](../../results/RESULTADO-fase6-numparallel-2026-09-05.md), [historical decision](../../results/DECISAO-producao-2026-09-09.md), [corrected capacity in the judge report](../../results/RESULTADO-juiz-familia-2026-09-10.md). Loading large models is an operation on the shared GPU, not an automatic consequence of consulting this catalog.

## Hardware separation and historical data

- **i7-14700KF CPU:** [chat_raw.gemma4.json](../../results/chat_raw.gemma4.json) and the [gemma4 table](../../results/chat_table.gemma4.md), 16.9 tok/s and a historical 99% score, belong to the CPU run identified by the [preserved earlier README](../history/README-before-organization.md). These are not RTX 5090 figures. `gemma4:26b` was measured on the 5090 **as a judge** in September, using a different task and instrument. The consolidated CPU report is referenced in the archive as a file in another project; it is not included here.
- **RTX 3080 Ti:** the [preserved baseline](../../baseline-3080ti/baseline-3080ti.md) contains production telemetry for `qwen3:14b` (63.9–68.0 tok/s) and `qwen3:8b` (100.5 tok/s), with total duration in the denominator. No dedicated decode benchmark for that GPU is recoverable; do not compare as if it used the same method as the 5090 bench.
- **Proposals and third-party figures:** the [initial model and configuration study](../../rtx5090-modelos-parametrizacao.md) contains candidates, hardware limits, and benchmarks published by third parties. Inclusion in that study does not place a model in the tables of our own measurements above.

Missing raw data, invalidated versions, and pending phases are collected in the [experiment catalog](benchmarks.md).
