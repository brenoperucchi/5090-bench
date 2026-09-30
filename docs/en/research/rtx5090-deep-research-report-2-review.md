# Review of deep-research-report-2.md

**Date:** September 13, 2026.  
**Disposition:** substantially improved research proposal; still requires corrections before execution or adoption.  
**Scope:** static document/code review against the [brief](rtx5090-deep-research-brief.md), [previous review](rtx5090-deep-research-review.md), and corrected repository evidence. No downloaded code or inference requests were executed.

## Artifact identity

The requested `deep-research-report 2.md` was found under the new name `deep-research-report-2.md` in Downloads. Its hash matches the file previously identified by the user:

```text
SHA-256: 3917c9043c2f01fd3027701b0b85c8210a8b72fd3fc5f88575d20b0fecd8841d
Bytes: 58,021
Logical lines (splitlines): 1,191; newline characters (wc -l): 1,190
```

It is distinct from the first report, whose hash starts `382ded1f`. Line references below refer exclusively to this second report. The original remains unchanged outside the repository. Two separately tasked reviewers examined methodology and execution; their agreement is not additional experimental evidence. Upstream compatibility claims are not certified by this document review.

## What this revision fixes

| Previous issue | Change in report 2 | Assessment |
|---|---|---|
| Reliability was subordinate to speed | Explicit P0 and failure-class holdout, lines 424–455 | Meaningful improvement; independent labeling and acceptance procedure still needed |
| Human escalation and frontier fallback were combined | Separate metrics and explanation, lines 442–455 | Conceptual correction |
| Second runtime appeared to coexist without a memory budget | Exclusive first test; drain/unload/restore and conditional coexistence, lines 271–305 | Correct direction; concrete runbook still pending |
| Generic context matrix replaced the discriminating question | About 40K tokens at C=32768, NP=2 versus NP=1, lines 615–647 | Correct starting design recovered; interpretation table still missing |
| Runner discarded final events | Stores raw events and final object, separate event/reasoning/content timing, lines 833–960 | Better recorder, but terminal-event validation regressed |
| Campaign errors could erase earlier results | JSONL append after each request; catches request exceptions | Improved ordinary error handling; not durable streaming persistence |
| Cache regimes were mixed | Separate cold, warm-uncached and warm-cached campaigns, lines 968–996 | Better definitions; actual cache reuse still needs verification |
| 192-configuration matrix | Sequential questions, lines 1011–1169 | Improved scope; calendar remains proposed |
| Means substituted for medians | Correct medians, lines 79–92 | Corrected |
| No research date | Explicit date and historical snapshot distinction, line 5 | Corrected |
| Unusable external references | Still opaque citation markers | Unresolved |

## Findings requiring revision

### R2-01 — High: an incomplete or error stream can produce an ordinary result

**Report lines 862–935.** The recorder treats the last parsed event as the final response, or `{}` when no event exists. It never requires `done=true` and does not classify an event containing `error`. A clean EOF after a partial event therefore follows the ordinary return path; missing counters become zero. Raw events remain available, but there is no explicit invalid/completion status to prevent downstream acceptance.

This is a regression from the first sample's check for a final event. An HTTP exception is caught; a semantically incomplete stream need not raise one.

**Correction:** explicitly classify complete, API-error, incomplete and transport-error outcomes. Require a valid terminal event; retain missing metrics as unknown rather than silently inventing zero. Preserve payload, partial timings, events and error details on every outcome, and exclude invalid runs from performance comparisons while retaining them in reliability/error denominators.

**Offline acceptance cases for a future implementation:** empty body; partial content followed by EOF; API error event; malformed JSON; HTTP error; normal completion; tool-only completion. These tests are proposed, not executed here.

### R2-02 — High: the export still cannot substantiate external claims

**Throughout; especially lines 141–160, 308–364 and 1189.** The only HTTP URL in the artifact is `http://127.0.0.1:11434`. Its citation markers do not identify retrievable sources. Listing canonical organizations and repository filenames does not restore the missing release, benchmark or model-card URLs.

**Correction:** supply direct primary-source links with date, exact model revision/quantization, runtime commit and applicable hardware/backend. Mark MTP model compatibility, recommended draft counts and projected optimizations as unverified until those sources are recovered. Missing citations do not prove the claims false, but they cannot support adoption as delivered.

### R2-03 — Medium: the context design is restored but is not self-contained

**Lines 615–647.** The 40K/32K experiment now exercises overflow, but the report omits each mechanism's predicted count and explicit inconclusive outcomes. It also does not clearly distinguish deliberate truncation in this diagnostic experiment from a failed production integrity test: observing the cutoff can be a valid experimental result even though the input was not preserved.

**Correction:** incorporate the [existing proposal](../plans/num-parallel-discriminating-test.md). For effective K=4, the candidate conditional-overflow rule predicts 16,386 in both arms; a C/N input-limit law predicts approximately 16,384 at NP=2 and approximately 32,768 at NP=1. Verify the exact installed route, pre-truncation tokens, keep value, logs and residency. Sentinel answers alone cannot prove which tokens were delivered. Failure to reproduce the control or verify settings is inconclusive. These remain source-derived predictions, not measurements or execution approval.

### R2-04 — Medium: the holdout and promotion gate remain underspecified

**Lines 426–455 and 1125–1141.** The report names the right failure classes but does not define independent annotation/adjudication, task counts, uncertainty or acceptable regression margins. The final AND/OR layout can be read as allowing reduced frontier fallback to bypass mandatory quality conditions.

**Correction:** explicitly use `all_quality_and_integrity_gates AND (useful_throughput_gain OR acceptable_fallback_reduction)`. Define materiality and latency/resource constraints before measuring. Separate detector-development examples from an independently labeled, frozen evaluation set; tuning until the same holdout passes would recreate the circularity problem. Report task-level outcomes, warranted human escalation recall and false-escalation rates separately. Sample-level zero failures is not a universal guarantee.

**Evidence:** [findings A04, A06–A07, A13, A22–A24](../findings.md).

### R2-05 — Medium: exclusive operation is now explicit, but verification remains a proposal

**Lines 293–305, 320–364, 508–590 and 966.** The revised document no longer assumes that ports provide GPU isolation. However, the sample snapshot and recorder still do not implement target/draft residency checks, effective configuration verification, or a complete restore procedure. A field named `effective_settings` in an example schema is not a measurement. The client still targets port 11434 while isolated-server examples use 11435 or 11436.

**Correction:** make the endpoint explicit; verify server/process/model identities and model store before inference. Correlate the endpoint's version with its listener, PID and logs: a local CLI version alone does not identify the server answering a different port. Specify the approved traffic-drain and targeted cleanup procedure, then restore and warm the actual initial residents and verify health. Retain target/draft layer and KV logs with memory observations; `/api/ps` plus total GPU usage is insufficient for the documented speculative-model blind spot. Unknown residency must invalidate the benchmark. Pin the executable and GGUF before filling the command placeholders.

**Evidence:** [infrastructure](../infrastructure.md), [findings A37](../findings.md), [existing isolated-test procedure](../plans/num-parallel-discriminating-test.md).

### R2-06 — Medium: Gemma reviewer work is reopened without a new evaluation basis

**Lines 240, 1060 and 1157.** The report correctly avoids adopting Gemma as a production judge, but uses the existing 11/12 result to prioritize a new unlabelled review/escalation benchmark. That result does not establish general semantic review ability. The deterministic 12/12 was measured against labels generated by the same check; it is not independent truth.

**Correction:** keep this as an optional proposal with a named consumer, distinct target errors and independently adjudicated examples. State the new evidence needed to reopen the recorded no-judge decision, and define benefit over existing checks and human review. Do not treat a proposed different use case as an already justified operational priority.

**Evidence:** [findings A19–A24 and settled decision](../findings.md).

### R2-07 — Medium: some local-history claims exceed the supplied evidence

**Lines 9, 36, 1000–1009.** The opening says the GPU has ceased to be the system's main bottleneck. The recorded narrow experiments do not locate the dominant bottleneck across actual production traffic. The approximately 510 W observation and its stated causal role in the user's decision have no source identified in this review's repository evidence. The stock decision itself is documented in the [parameter plan](../../../PLANO-parametrizacao-2026-09-04.md), and a historical 600 W cap appears in the [hardware record](../../../rtx5090-modelos-parametrizacao.md); those are not missing facts.

**Correction:** present the bottleneck statement as a hypothesis requiring workload telemetry. Attribute the power observation and decision to their original record if available, or mark them externally reported/unverified. They may come from context given to the researcher that is unavailable here; absence from this review's evidence is not proof they were invented. Do not change power settings to investigate a documentation gap.

Similarly, the description of the 9B as an excellent worker for simple tasks (lines 234–238) should be a role hypothesis until the allowed task class is defined and evaluated. Small size and speed do not establish quality for an unspecified workload.

## Remaining recorder limitations

The example is explicitly minimal, so it need not implement the entire proposed schema. Before using it as benchmark evidence, however:

- Error records need the actual payload and elapsed/partial timings, not only its hash and events.
- All events currently remain in RAM until the request returns. JSONL append protects earlier completed requests from ordinary later exceptions; it does not preserve an in-flight request across process termination. Allocate the run ID before sending and append events as they arrive if crash recovery is required.
- Thinking mode is not an explicit top-level request parameter; the caller's options map alone does not describe all generation behavior. Keep generation and cache controls explicit.
- A changed nonce does not by itself prove zero prefix reuse; verify the rendered prefix and backend behavior.

## Recommended next step

Use this revision as the planning base, retaining the corrections above and the original research brief's boundaries. Recover the external bibliography, specify independent quality evaluation, and fix terminal-stream validation before relying on new scores. Keep the existing NUM_PARALLEL proposal as the authoritative starting design. MTP remains a candidate for a bounded, separately authorized experiment, not a measured improvement.

The report is still in Portuguese despite the brief's English requirement. This review is in English and does not replace or alter the original. No production action, benchmark, commit or publication is implied by this review.

## Named Herdr review follow-up

On September 13, the user explicitly requested review by `llm-bench-rev-1` (Codex) and `llm-bench-rev-2` (Claude). Both inspected this report/review and returned findings independently. This is a separate review from the native subagents mentioned above.

Their first-round additions are addressed in the [remediation plan](../plans/research-remediation-plan.md): preserve f16 versus q8 memory conditions; separate detector repair from model validation; inventory actual consumers; distinguish diagnosis from mitigation; compare a candidate with the incumbent as well as MTP off/on; and give each deliverable an owner and acceptance condition. The plan and new offline parser were then submitted to the same named reviewers for follow-up. A second pass by the same reviewers is refinement, not a second independent sample.

Both named reviewers accepted the plan for the next offline implementation and verified the initial 14 parser tests. Their nonblocking refinements were applied; the final local suite has 17 passing tests. This acceptance does not approve the downloaded report as an executable runbook, a production change, or a GPU window.

The standalone [stream parser](../../../tools/stream_record.py) closes the terminal-event classification defect within its offline scope. It does not implement the report's complete HTTP recorder, GPU checks, or independent quality evaluation. Historical scores and downloaded source documents remain unchanged.
