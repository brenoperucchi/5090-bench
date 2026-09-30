# llm-bench — RTX 5090 benchmarks

**English** | [Português (Brasil)](README.pt-BR.md)

## Documentation epochs

> **CURRENT RESEARCH CAMPAIGN — 2026-09-20+**
> Guardian / WSL Arch / CUDA / llama.cpp forks (Codacus, PrismML) / typed decisions / T87.
> Latest campaign record: [Guardian synthesis on a local RTX 5090, 2026-09-21 → 24](docs/en/findings/guardian-local-models-2026-09-21-24.md)
> Previous record: [Public findings record (English)](docs/en/findings/public-record-llm-bench-2026-09-20.md)
>
> **HISTORICAL PRODUCTION BASELINE — snapshot 2026-09-12**
> Windows native / Ollama / `qwen3:14b` + `qwen3.5:9b`.

A collection of performance, quality, and behavioral measurements of local
LLMs running on **a 32 GB RTX 5090 with Ollama**. It brings together the
experiments, raw results, scripts, findings, decisions, and corrections
recorded by this lab in September 2026.

This project covers customer support in Portuguese and English, tool
calling, multi-turn research, concurrency, and long-context processing.
Results apply to the configurations and samples described in their sources.

## Start here

| What you want to read | Document |
|---|---|
| Ready-to-use assignment for external deep research | [RTX 5090 research brief](docs/en/research/rtx5090-deep-research-brief.md) |
| Review of the downloaded research report | [Findings and required revisions](docs/en/research/rtx5090-deep-research-review.md) |
| Review of the second research report | [Corrections and remaining gaps](docs/en/research/rtx5090-deep-research-report-2-review.md) |
| Remediation sequence and experiment gates | [Research remediation plan](docs/en/plans/research-remediation-plan.md) |
| Every improvement measure and its implementation gate | [Master improvement implementation plan](docs/en/plans/improvement-implementation-plan.md) |
| Experiments, results, and evidence by phase | [Benchmark catalog](docs/en/benchmarks.md) |
| Tested models and comparison limits | [Models](docs/en/models.md) |
| All 40 consolidated findings and caveats | [Findings](docs/en/findings.md) |
| Guardian synthesis: runtime, models, prompts, desk test, typed decisions (21–24/09) | [Guardian local-model record](docs/en/findings/guardian-local-models-2026-09-21-24.md) |
| Detailed public record of the September campaign | [Public findings record (English)](docs/en/findings/public-record-llm-bench-2026-09-20.md) |
| English answers to Portuguese questions | [PT→EN finding](docs/en/findings/qwen3-14b-language-template.md) |
| Adopted decisions and withdrawn recommendations | [Decisions](docs/en/decisions.md) |
| Metrics, methodology, and reproduction | [Methodology](docs/en/methodology.md) |
| Lab setup and operating constraints | [Infrastructure](docs/en/infrastructure.md) |
| Unanswered questions | [Open questions](docs/en/open-questions.md) |
| Source history and file integrity | [Provenance](docs/en/provenance.md) |
| Proposed NUM_PARALLEL discriminating test | [Test proposal — not executed](docs/en/plans/num-parallel-discriminating-test.md) |
| Lifecycle and spill evidence contracts | [Offline lifecycle/residency contracts](docs/en/plans/lifecycle-and-spill-evidence.md) |
| Coding evaluation sandbox contract | [Offline coding task/result contract](docs/en/plans/coding-evaluation-sandbox.md) |
| Documenting a new experiment | [Experiment template](docs/en/templates/experiment.md) |

## How to interpret the results

- **Quality and speed are separate dimensions.** The recorded decision kept
  `qwen3:14b` as the default and `qwen3.5:9b` as the second resident model.
  Read the [decision's scope](docs/en/decisions.md) before applying it to another workload.
- **`auto_score` changed on September 10, 2026:** the denominator went from
  5–6 to 6–7 checks. Aggregate scores before and after that change are not
  directly comparable.
- **Concurrency:** `NUM_PARALLEL=2` reduced batch wall time by 28% and time
  per request by 41% in the corrected experiment with `qwen3:14b` and a
  2,108-token prompt. The proposed long-context experiment has not been run.
- **Labeled goldset:** the deterministic check caught 12/12 escalation defects
  with no false positives in the judge-comparison dataset. This does not
  establish universal error detection in production.
- **The handoff is a starting source.** Inspection of the raw PT→EN results
  contradicted parts of that summary; the [dedicated finding](docs/en/findings/qwen3-14b-language-template.md)
  records the supported counts and limits.

The benchmark and findings catalogs link each claim to its supporting evidence.

## English documentation, original evidence

The English pages translate the consolidated Portuguese documentation. Their
language links lead to the corresponding Portuguese pages. Historical reports,
raw model responses, prompts, dataset labels, and scripts retain their original
content and filenames. References to those files may therefore open Portuguese
text or mixed-language data.

This preserves the evidence: translating a measured response or prompt in place
would change the experiment's inputs or outputs. The English catalogs explain
those sources without modifying them. See [provenance](docs/en/provenance.md) for the
translation and maintenance policy.

## Repository layout

```text
docs/en/                English documentation and navigation
docs/rtx5090/           Portuguese benchmark, model, and findings catalogs
docs/achados/           Detailed findings in Portuguese
docs/history/           Preserved handoff and previous README
docs/templates/         Portuguese experiment template
results/                Original reports and JSON results
prompts/                Canonical prompt, backup, and historical experiments
baseline-3080ti/         Earlier GPU baseline and historically located scripts
artifacts/manifest.json Evidence inventory with SHA-256 hashes
tools/inventory.py      Offline archive validation
tools/json_safety.py    Shared finite-JSON safety boundary
run_chat.py             Quality evaluation using a PT/EN goldset
bench.py                Generation throughput
bench_engine_ab.py      Alternating comparison of two endpoints
goldset_chat.json       18 cases with expectations and rubrics
```

Several scripts used for the **5090** remain under `baseline-3080ti/repro/`
because they resolve repository paths relative to that location. The
[benchmark catalog](docs/en/benchmarks.md) identifies their experiments; directory
names alone do not establish the GPU used.

## Verify the archive without a GPU

Run from the repository root with Python 3.10 or later. No additional
dependencies are needed:

```bash
python3 tools/inventory.py check
```

This checks the evidence inventory, sizes, hashes, JSON files, and local links
in the new documentation, including the English pages. GitHub Actions runs the
same check. File integrity does not validate scientific conclusions.

Read the [methodology](docs/en/methodology.md) before running inference scripts: they
send real requests to Ollama, and some historical tools depend on this lab or
modify remote processes.

## Historical archive

- [Original consolidated report](RELATORIO-FINAL-2026-09-04.md) —
  Portuguese historical synthesis with later corrections and caveats.
- [RTX 3080 Ti baseline](baseline-3080ti/README.md) — historical
  production metrics include prefill and do not equal isolated decode throughput.
- [Starting handoff](docs/history/handoff-2026-09-12.md) — Portuguese session
  summary preserved with its limitations.
- [Source sessions](SESSOES.md) — provenance references; full transcripts
  and local Herdr state are not included in the public repository.

The dedicated 3080 Ti throughput benchmark mentioned in the old README was
not preserved. This archive does not contain a controlled comparison of the two GPUs.
