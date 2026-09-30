# Research remediation and experiment plan

**Date:** September 13, 2026.  
**Status:** reviewed by llm-bench-rev-1 and llm-bench-rev-2; ready to guide the next offline implementation. GPU experiments are not authorized by this plan.

This plan resolves actionable issues in [report 2's review](../research/rtx5090-deep-research-report-2-review.md). The downloaded report is identified by SHA-256 `3917c9043c2f01fd3027701b0b85c8210a8b72fd3fc5f88575d20b0fecd8841d`. The original report and historical measurements remain unchanged. It is the foundation work package of the [master improvement implementation plan](improvement-implementation-plan.md), which contains every implementation measure extracted from both reports.

## Scope and sequence

The next decision is whether a trustworthy, bounded context experiment can distinguish the competing input-limit laws. It does not require choosing a new runtime or model. Work proceeds along two tracks:

1. **Measurement track:** offline stream validation and provenance → concrete context runbook → explicit execution approval → two-arm diagnostic → restore and report.
2. **Quality track:** independent annotation protocol → separate development/regression and held-out task families → frozen scoring → challenger shortlist only when supported by primary sources and a defined workload.

The context diagnostic need not wait for the entire quality holdout: it measures delivery/counts, not semantic superiority. A production model/runtime promotion does require the quality track. MTP, Gemma review, vLLM, power changes and hardware purchases are not prerequisites for answering the context question.

## Correction ledger

| Review issue | Resolution in this plan | Completion evidence / remaining work |
|---|---|---|
| Stream EOF/error admitted as normal result | Mandatory terminal/error state machine, stage M1 | Offline parser and tests; full HTTP recorder integration still required |
| Missing source links | Verified minimal source ledger below; quarantine unsupported model/performance claims | Original exported bibliography remains unavailable; recover before challenger selection |
| Context predictions omitted | Numeric predictions and interpretation below | Installed executable/request route and effective settings still unverified |
| Holdout/gate ambiguity | Independent-label protocol and explicit Boolean promotion rule | Annotation, sample collection and model comparisons not performed |
| Endpoint/residency/restore gaps | Execution admission checklist and restore criteria | Must be completed for the actual chosen processes before approval |
| Gemma role reopened without consumer | Deferred; requires specific consumer/use case and independent labels | No judge adopted or benchmark scheduled |
| Unsupported bottleneck/power history | GPU bottleneck claim is a hypothesis; 510 W report remains unattributed | Historical stock decision retained; no power intervention planned |

These are design resolutions, not claims that every implementation or empirical question is closed.

| Next deliverable | Owner | Acceptance / stopping point |
|---|---|---|
| Corrected planning interpretation | Coordinator; both named reviewers | Review findings have a disposition; no unsupported claim becomes a production fact |
| Offline parser | Coordinator / implementation delegate | Fixtures pass; parser-only limits retained |
| Network recorder adapter and regression matrix | Coordinator, next implementation step | HTTP errors/incomplete responses and saved detector cases have versioned expected outcomes; no live calls required |
| Context execution packet | Coordinator | Exact commands, endpoint/process identity, budget, route evidence, call/time ceiling and rollback are reviewable; if a field is unknown, packet is not ready |
| Context window | Breno | Explicit approval of that packet only; no implied runtime/model promotion |
| Independent labels and product tolerances | Application/domain owner and Breno | Adjudicated labels, task-family counts, uncertainty and thresholds exist before model scoring |

English is the normative language of this plan and all new deliverables. The original Portuguese download remains a preserved input, not the publishable research deliverable; a full translation is not a dependency for this bounded diagnostic. Unsupported external claims are quarantined rather than copied into an English report as verified facts.

Historical memory figures must retain their KV regime: Phase 6's NP=1/NP=2 values of 13.55/18.55 GiB used f16; the later NP=2 q8 14B record is 13.93 GiB. The report's unlabeled historical table must not be used as a q8 capacity budget. See the [model inventory](../models.md).

The report's rejected “old ~25-second reload” is not adopted as local history: its origin was not located by the reviewer. Use the recorded 0.4–4.2-second range only in its historical scenario. The report does provide a formula for Correct Tickets/hour; what remains missing is operationalization (ticket source, workload mix, labeling and timed window), not the existence of a formula. Until those inputs exist, keep it a proposed metric and report case-level contract failures and measured wall-time distributions without inventing production throughput.

## M1 — Offline measurement contract

Implement a standalone parser first, without networking. Its outputs distinguish `complete`, `api_error`, `incomplete`, and `invalid_stream`. Only an object with Boolean `done=true`, with no error and no subsequent event, establishes payload-stream completion. Missing metrics remain unknown. This does not certify HTTP transport or a correct answer: generation limited by length still needs separate quality evaluation.

Retain raw events, API errors and parser diagnostics. Reject malformed JSON/non-object events and unexpected events after termination. A valid tool-only response is complete even if it contains no visible text. Empty input and clean EOF after a partial response are incomplete.

**Acceptance fixtures:** empty stream; partial EOF; API error object; invalid JSON; non-object JSON; normal completion; tool-only completion; missing metrics; error combined with terminal marker; extra event after terminal; length termination. These run offline and neither call nor load a model.

**Before a network campaign:** add a thin recorder adapter with an explicit endpoint, request/run ID allocated before send, exact payload and top-level thinking setting, HTTP status, timestamps, per-event append, terminal object and partial-error records. Connect each record to endpoint/version/listener/PID/model digest and effective settings. Do not infer the serving binary from the client's CLI version. Use a unique campaign directory and one writer per stream. Invalid calls remain in reliability/error denominators and are excluded from performance claims.

The parser alone is not the full recorder, does not prove GPU residency or context integrity, and is not permission to run the report's sample client on port 11434.

**Current offline implementation:** [parser](../../../tools/stream_record.py) and [17 regression tests](../../../tests/test_stream_record.py). The initial 14 tests could not import the absent module; all passed after implementation. Both named reviewers checked that version. Rev-2's null/empty-error refinement then produced failing diagnostic regressions; the fix and iterator-propagation coverage bring the final passing count to 17. That is evidence for the new isolated parser, not an execution or reproduction of the downloaded HTTP client. Iterator exceptions deliberately propagate to the future adapter, which must persist them with partial state. Invalid UTF-8 bytes need explicit encoding before JSON serialization.

## M2 — Context diagnostic

The [detailed context proposal](num-parallel-discriminating-test.md) remains the starting point. Use distinct names for arms and mechanisms:

- **Control arm:** NP=2.
- **Discriminating arm:** NP=1.
- **H-slot-law:** prompt limit approximately C/N. The historical claim that slot allocation itself is divided is already contradicted by logs.
- **H-overflow:** conditional post-overflow reduction `C - max(floor((C-K)/2), 1)`.

Fix C=32768, effective K=4, approximately 40K server-tokenized input tokens, the same model digest, API/renderer/runner path, payload, q8 KV, temperature=0, thinking off and generation budget=1. Verify the actual overflow condition and context-shift/truncation flags rather than assuming all endpoints invoke the same code.

| Arm | H-slot-law prediction | H-overflow prediction |
|---|---:|---:|
| NP=2 | Approximately 16,384 | 16,386 |
| NP=1 | Approximately 32,768 (32,767 if one token reserved) | 16,386 |

If effective K is different, recompute the exact prediction before interpreting the result. Avoid arbitrary tolerances around the response counter: compare logged pre-truncation count, limit, keep and delivered token count. Sentinels are supplementary and do not establish the mechanism through answer recall alone.

The NP=2 predictions differ by two tokens, so they do not literally coincide. Record that difference; without verified BOS/keep/reserved-token conventions, it is insufficient to identify the cause. The primary planned discriminator remains the large change, or its absence, at NP=1. These two laws are not exhaustive. An unexpected value is retained as informative evidence outside the preregistered predictions, not discarded; report the diagnostic as inconclusive between these laws and design a new test before claiming a third mechanism. Do not add a post-hoc winning hypothesis to this run's confirmatory result.

**Interpretation:** reproduced control + unchanged half-context cutoff favors H-overflow in this configuration; reproduced control + approximately full-context admission at NP=1 favors H-slot-law as an input-limit law. Failure to reproduce control, different routes/settings, unknown residency, API error or unsupported counter interpretation means inconclusive. Observing deliberate truncation can be a valid diagnostic result; that same behavior fails production input integrity. Do not load the 30B automatically after an inconclusive 14B test.

### Admission and restoration

Before requesting execution approval, identify the exact endpoint, free port on both the workstation and server, executable/version/hash, store, start/stop commands, process tree and initial residents. A forwarded port is not proof of a separate server. Record which application routes actually reach the endpoint; Contábil's documented direct calls are not automatically intercepted by a gateway.

| Consumer | Documented path | Protection coverage / owner |
|---|---|---|
| Benchmark recorder | Explicit configured endpoint required | Coordinator controls recorder validity; cannot protect unrelated callers |
| Contábil | Direct Ollama/OpenRouter calls according to the recorded decision | Application owner must identify/integrate its actual client; a gateway-only guard gives no demonstrated coverage |
| HERD or other gateway clients | Per-consumer endpoint inventory not yet supplied | Unknown until mapped; do not claim protection or alter routing |

The auxiliary strategy requires a model-specific joint weights/KV/buffer budget and observed headroom. Approximately 25.20 GiB for two 14B copies is an estimate, not admission proof; retaining the 9B adds approximately 5.73 GiB and may invalidate that budget. Do not unload a resident to make it fit without that action being explicitly approved.

After approval, preload the intended configuration and verify both target and draft, where present, with startup/layer/KV logs plus attributed memory observations before, during and after each request. Global memory and `/api/ps` alone cannot certify the recorded speculative-model case. Stop on unknown residency, unexpected eviction, spill, context reduction, endpoint mismatch or request failure. Store evidence even for invalid rounds.

Cleanup must stop only the auxiliary process tree. Restore the actual initial configuration/residents, warm them if they were initially warm and were displaced within the approved procedure, verify endpoint health and final process/residency state, and report discrepancies. Do not use the existing broad process-name restart script for auxiliary cleanup. If restoration cannot be verified, stop further experiments and report the incident; do not call the campaign complete.

**Cost:** auxiliary mode has zero planned restart downtime but can increase latency. Its 40K prefill duration is unmeasured. If auxiliary admission fails, stop; a production restart alternative requires separate approval. The historical five-minute window is a planning allowance, not a measured cost or upper bound. No automatic switch to that alternative is allowed.

### M3 — Separate diagnosis from mitigation

The NP comparison can resolve a tested input-limit law; it does not repair truncation. Any later mitigation needs a separate proposal: for example, observable rejection when input cannot fit or explicit application-managed reduction that preserves the required evidence. Test its contract on both fitting and overflowing inputs, verifying actual delivered tokens and error behavior. Do not change the system prompt, production NP, renderer or global context merely because the diagnostic favored one mechanism. The next execution packet covers M2 only unless Breno explicitly approves a broader scope.

## Q1 — Independent quality evaluation

First create a versioned offline regression matrix from the saved language ties and missed promise wording. Compare current and proposed detector outputs, inspect false alarms and preserve the old scores. This is detector repair, not improved generation or independent model validation. Do not overwrite the historical JSONs or silently change the meaning of `auto_score`; keep any revised evaluator version separate until reviewed. The known cases and corrected interpretation are in [findings A03–A07](../findings.md).

Use the historical corpus as a development/regression set, not as proof of independent generalization. Freeze a separate set of new task families and labels before candidate outputs are inspected. Proposed first scope: bilingual support and tool contracts only; coding and generic reviewer roles require their own later evaluation.

1. Define the application contract from documented requirements. Include required human escalation, prohibited escalation, promised action/token consistency, language, all tool arguments and sequence, supported citations and reasoning exposure.
2. Have two domain-qualified annotators independently label the input and required behavior without seeing detector decisions or model identity. Adjudicate disagreements using documented rules. If qualified independent annotation is unavailable, label the set a regression suite and do not claim an independent holdout.
3. Keep related PT/EN variants and paraphrases in the same task-family split. Include difficult negative examples: legitimate escalation that resembles a leak and valid technical English terms in otherwise Portuguese responses.
4. Before collecting outputs, record proposed task counts per family, acceptable uncertainty, critical-error tolerance, false-escalation limit and latency target. Derive sample size from those requirements; do not invent a universal pass percentage or promise statistical power from repeated seeds.
5. Version and hash labels, split, prompt, detector and runner. Once holdout results influence a detector or prompt fix, retire that holdout from confirmatory use and build a fresh one for the next claim. Model judges must not provide the reference labels being used to validate themselves.
6. Compare paired outcomes by task family, preserving every error and retry. Report per-family FP/FN, human escalation recall, false escalation, contract failures, citation failures, context-integrity failures and useful completion time. Uncertainty must account for task grouping; repeated seeds are not new questions.

**Promotion rule:**

```text
all_predeclared_quality_integrity_and_operational_gates
AND
(useful_throughput_gain OR acceptable_frontier_fallback_reduction)
```

Every quality gate remains mandatory in both branches. Zero newly introduced critical errors is necessary but does not excuse existing critical failures; the workload must explicitly exclude unsupported cases or resolve them. Observed zero failures does not establish a universal zero rate. Human escalation recall, false-escalation limits, noninferiority margins and latency bounds must be set before evaluation. The report's 20–30% MTP gain is only a proposed economic threshold, not an accepted SLO or measured prediction.

## P1 — Conditional performance challenger

Only after a workload and evaluation exist, choose at most one compatible MTP candidate. Recover its official checkpoint, revision, tokenizer/template, quantization, license, draft/target memory, runtime commit and actual MTP enable/disable semantics. Do not silently identify an archive alias as a current official model.

Start with MTP off versus a single pinned draft setting on the same checkpoint/build. Add another draft setting only if the first comparison or upstream evidence motivates it. Use distinct cold, warm-uncached and warm-cached regimes and randomized arm order; record acceptance, prefill, decode, complete-task latency, queueing, quality and memory. A changed nonce is not proof of zero prefix reuse.

That within-candidate comparison isolates the MTP effect; promotion additionally requires a paired comparison against the incumbent on the chosen workload. The workload contract and reference results come before the candidate campaign, including an executable coding goldset if coding is the target.

An exclusive window and verified restoration are prerequisites if coexistence has not been demonstrated. This plan does not reserve a window or select a production replacement. vLLM, TensorRT-LLM, aggressive KV quantization, Gemma judge work and hardware changes remain deferred.

## Minimal primary-source ledger

Sources checked September 13, 2026 for this plan, independently of the lost research citations:

| Source | Supported statement | Limit |
|---|---|---|
| [Ollama streaming API](https://docs.ollama.com/api/streaming) | NDJSON streaming with a terminal done event | Living documentation; verify installed behavior in adapter acceptance |
| [Ollama API errors](https://docs.ollama.com/api/errors) | Mid-stream errors can be JSON error events without changing HTTP status | HTTP 200 alone is insufficient |
| [Ollama v0.33.3 completion implementation](https://github.com/ollama/ollama/blob/v0.33.3/llm/llama_server.go) | Candidate conditional overflow implementation used in the existing proposal | Does not identify the installed executable or active request route |

This closes the source requirement for the immediate recorder specification and supplies a versioned starting point for the diagnostic. It does not restore report 2's missing MTP/CUDA/model bibliography. Those claims are excluded from immediate adoption decisions.

## Completion checklist

- [x] Both named Herdr reviewers return findings and review the consolidated plan; both accepted the next offline scope.
- [x] Offline parser regression cases pass; scope and missing adapter are documented (17 tests after review refinements).
- [x] Every accepted finding has a correction, a verification condition or an explicitly deferred dependency; implementation and empirical acceptance are tracked separately.
- [ ] Concrete live execution packet identifies processes, routes, commands, budget, stop criteria and restoration; Breno approves that packet before inference or configuration changes.
- [ ] Independent quality labels and acceptance requirements are supplied before challenger promotion.

The coordinator owns documentation, offline evidence and experiment packaging. Breno owns production-window approval and product acceptance requirements. Required application-owner/domain input is listed here; no messages to additional operators are authorized or sent by this plan.

## Review outcome

`llm-bench-rev-1` approved this plan for the next offline implementation and verified the parser tests. Its terminology correction (payload-stream completion, not transport completion) was applied. `llm-bench-rev-2` also found no blocking gaps for that scope; its additional parser diagnostics/iterator-test and context-interpretation refinements were accepted. The same reviewers' follow-up is not another independent experimental sample.

Two first-round objections from rev-2 were retracted after checking the complete evidence: 1,191 logical lines was correct despite 1,190 newline characters; Correct Tickets/hour has a formula in the report, although operational inputs remain missing. Neither objection is recorded as a report defect. The downloaded research itself is not certified, and neither reviewer authorized production execution.
