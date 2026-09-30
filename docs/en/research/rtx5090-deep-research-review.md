# Review of the RTX 5090 deep-research report

**Review date:** September 13, 2026.  
**Disposition:** useful research leads; revisions required before using the report as an experiment runbook or adoption rationale.  
**Scope:** document review against the [research brief](rtx5090-deep-research-brief.md), corrected project documentation, and cited local evidence. No inference, model loading, service restart, or production configuration change was performed for this review.

## Reviewed artifact and limits

The downloaded artifact is `deep-research-report (2).md`, titled “Futuro da inferência local na RTX 5090 de 32 GiB: onde o software ainda pode entregar ganhos reais.” Report line numbers below refer to this exact file:

```text
SHA-256: 382ded1fb10d0f8de222431ebc5db8099326525d6f8103142de4365723c1eb41
Size: 46,081 bytes
Lines: 937
```

The downloaded original is preserved outside the repository. Its export contains opaque citation markers rather than usable source URLs. This review does not certify the report's upstream release, model-support, or performance claims. Missing references do not establish that a claim is false.

Two separately tasked reviewers inspected methodology/evidence and execution/operations. Their findings were consolidated and checked against the document; agreement between reviewers is not another experimental measurement.

Severity describes the consequence of relying on a recommendation: **High** blocks using the affected recommendation as an execution or acceptance basis; **Medium** requires correction for valid interpretation or reproducibility. An incomplete proposal is not evidence that an incident has occurred.

## Findings

### R01 — High: the reliability priorities are largely unanswered

**Report:** lines 30–32, 244–273, 522–565, 720–885.

The report prioritizes runtime performance, coding evaluation, residency, and keep-alive, while leaving the proposed quality gate unspecified. It does not provide the requested evaluation design for English accepted as a language-check tie, missed ticket promises, fabricated supporting citations, or the circular 12/12 detector comparison. These are central requirements of the brief, not peripheral improvement requests.

**Consequence:** faster execution can preserve the same false approvals. A runtime winner cannot be selected on reassuring scores without addressing what those scores miss.

**Required revision:** specify an independently labeled holdout covering these failure classes, task-level grouping, false positives and false negatives, and acceptance criteria defined before testing. Distinguish application-required human escalation from optional fallback to another model; minimizing the latter must not reward missing the former.

**Local evidence:** [findings A03–A07, A16–A17, A22–A24](../findings.md), [corrected language finding](../findings/qwen3-14b-language-template.md).

### R02 — High: the proposed deployment has no demonstrated shared-GPU budget

**Report:** lines 199–216 and 244–269.

The architecture keeps 14B and 9B resident and adds a hot speculative executor. The vLLM example specifies a 27B path, 32K context, and 0.90 GPU utilization without identifying the checkpoint's quantization or budgeting coexistence with Ollama. Different ports and Windows/WSL environments do not establish separate GPU capacity.

The recorded production pair occupies 19.66 GiB. As a conditional size check, 27 billion parameters at two bytes each require approximately 50.3 GiB for weights alone. This does **not** prove the unspecified checkpoint is unquantized; it shows why its identity and format cannot be omitted. A quantized candidate still needs a joint weights/KV/draft/buffer budget and observed residency.

**Required revision:** identify the exact checkpoint, quantization, runtime build, and allocation limits. Declare whether the runtimes are alternatives used in separate windows or simultaneous residents. Require before/after residency evidence for every affected runner and stop on unknown residency, eviction, spill, or unexpected context reduction. State the consumer integration work needed for routing; the recorded Contábil path calls Ollama/OpenRouter directly.

**Local evidence:** [q8 measurement](../benchmarks.md), [infrastructure](../infrastructure.md), [findings A37 and consumer routing](../findings.md).

The report's spill warning (lines 443–468) is appropriate, but its supplied telemetry does not implement that requirement. In the recorded speculative-model failure, `size == size_vram` could pass while omitting the target allocation. Require startup logs and layer/KV residency evidence for both target and draft, plus attributed memory observations before, during, and after the run; global used memory alone is insufficient. Missing evidence invalidates the measurement. One-second GPU polling should be labeled sampled usage rather than a guaranteed peak.

If a candidate requires exclusive GPU access, the proposal also needs a separately approved traffic-drain, targeted cleanup, and restoration procedure: unload the candidate, restore and warm the initial residents, and verify endpoint health, residency, and process state. Restore the actual initial residents, not an assumed pair from a historical snapshot. A temporary second process does not itself imply permission to displace production.

### R03 — High: the long-context proposal does not answer the discriminating question

**Report:** line 32, lines 80–96 and 760–769.

The report recognizes the unresolved cutoff but replaces the specific causal question with context recommendations and a broad parameter matrix. It does not evaluate the conditional overflow path documented in the existing proposal. In that candidate path, an input fitting within `C−1` passes intact; an overflowing input can be shortened to approximately half the context. Therefore, acceptance of 25K tokens at a 32K context would not reject that mechanism.

**Required revision:** retain the [existing proposed experiment](../plans/num-parallel-discriminating-test.md) as the starting point: approximately 40K effective input tokens, `C=32768`, matched NP=2 and NP=1 arms, identical request route and model identity, effective keep value verified in logs, and residency checks. With `K=4`, the candidate post-overflow formula predicts 16,386 tokens in both arms; a `C/N` input-limit law predicts approximately 16,384 versus approximately 32,768. The installed executable and route still need verification. These are predictions, not new measurements.

The claim that slot allocation itself is divided by NP was already contradicted by the historical log. Do not revive it as an established mechanism. Execution remains subject to Breno's explicit approval; the reviewed document supplies none.

### R04 — High: the exported references cannot support an auditable adoption decision

**Report:** citations throughout, including lines 53, 66–68, 157, 195 and 236.

Release, compatibility, and performance claims cite internal research markers without a usable source bibliography. The only HTTP URL in the exported file is the sample local API endpoint. Readers cannot trace a claim to a release, commit, model card, or benchmark from this artifact alone.

**Required revision:** recover direct primary-source URLs, access/publication dates, exact versions and model identities. For each proposed improvement, distinguish upstream support, external measurements on other hardware, and unmeasured predictions for this machine. Do not substitute agreement between summaries for verification of a mechanism.

### R05 — Medium: the sample runner loses evidence and mislabels its latency measurement

**Report:** lines 568–672.

The introduction says the runner preserves the final metrics JSON, but its return value at lines 636–647 retains only selected fields and derived rates. The final object, raw durations, termination reason, reasoning events, and tool calls are not preserved.

The `ttft_s` timer stops only when `message.content` becomes nonempty. That measures first visible content received by this client, potentially after reasoning; a tool-only response can leave it unset. The payload does not fix the thinking mode or generation budget. Repeating one identical prompt does not distinguish cached from uncached prefill. Exceptions interrupt the loop before the results file is written, so an incomplete campaign can lose its earlier file records.

**Required revision:** preserve request options, full events and final response, model/server identities, raw durations, and explicit error records incrementally. Name observed latency precisely and separate first event, reasoning, and visible content when applicable. Specify generation budgets and distinct cold, warm-uncached, and warm-cached workloads. Include residency and input-integrity validity checks before admitting runs to performance comparisons.

The snippet remains useful as a starting point: it uses a monotonic clock, separates prefill/decode/load/wall time, retains the concatenated visible response, and excludes its first repetition from medians. Those features do not make it a validated evidence harness.

### R06 — Medium: the “minimum” matrix is not a bounded discriminating plan

**Report:** lines 760–769 and 850–883.

If interpreted as a full Cartesian product, the listed factors produce `4 × 2 × 2 × 2 × 3 × 2 = 192` configurations before workload variants and repetitions. The report does not specify a reduced design, stopping rules, or an approved operational budget. Its calendar is a proposal, not established availability or measured execution cost.

**Required revision:** sequence a few experiments, each answering one decision with a fixed baseline and explicit acceptance/inconclusive criteria. Add configurations only after a result warrants them. Do not use the broad matrix to reopen all settings with existing narrow evidence.

### R07 — Medium: historical statistics and q8 evidence need narrower wording

**Report:** lines 7, 41, 335 and 771.

The reported 41% request-time improvement is described as a mean in the executive summary, while the corrected Phase 6 table reports medians. The approximate 5 GiB NP memory increase belongs to its recorded f16 setup; it is not a universal current q8 cost. The claim of “better” local quality evidence for q8 must not imply that q8 beat q4 in a local quality A/B.

**Required revision:** use “median,” preserve the measured model/context/KV/workload conditions, and say that q8 matched f16's 40/45 in the recorded subset while q4 was not validated in that comparison. Neither result establishes general quality neutrality.

**Local evidence:** [corrected Phase 6 table](../../../results/RESULTADO-fase6-numparallel-2026-09-05.md), [benchmark scope and q8 comparison](../benchmarks.md).

### R08 — Medium: installed identities and effective settings are not captured

**Report:** lines 165–177, 203–217, 475–509 and 724–750.

The examples use unpinned packages/binaries and generic model paths. The snapshot reads machine environment values, which do not prove the configuration inherited by an already-running server process. Its desired metadata schema is more complete than its example implementation.

**Required revision:** pin runtime/dependency versions and model/tokenizer/template hashes; retain exact command lines and request options. Associate each run with the serving executable, PID/start time, parent or supervisor, startup logs and resolved settings. Mark values that cannot be verified as unknown. An environment registry snapshot is useful supporting evidence, not proof that a setting took effect.

**Local evidence:** [recorded SYSTEM scheduled-task deployment](../infrastructure.md), [reproduction requirements](../methodology.md).

## Useful directions to retain

- Retaining the recorded NP=2, MAX_LOADED_MODELS=2, and q8 baseline while evaluating challengers is consistent with the scoped local evidence.
- MTP/speculative decoding is a candidate research direction. Recover its sources and compatible model/runtime identities before designing a small test of acceptance, prefill, decode, memory, and task quality. External speedups are not local estimates.
- Evaluating the complete model/template/renderer/parser combination is more useful than assuming a model name guarantees tool-call compatibility.
- Distinguishing weight quantization from KV quantization, and runtime support from measured benefit, is appropriate.
- Measuring correct task completion, queue delay, latency distributions, and cold versus cached behavior would improve the current evidence.

## Revision order and acceptance

1. Restore the references and supply the revised report in English, as requested by the brief. State the research date separately from the historical evidence period; the downloaded report lacks that field.
2. Address the reliability evaluation gaps before using task scores as a promotion gate.
3. Resolve the specific context-test design without treating it as permission to run.
4. Replace the concurrent-runtime sketch with a budgeted, reproducible, operationally bounded proposal.
5. Correct the runner and statistical wording before using either in a comparison.
6. Select one performance challenger and one workload only after the preceding requirements are satisfied.

This review changes documentation only. It does not select a new production runtime or model, modify the canonical prompt, or authorize a GPU experiment.
