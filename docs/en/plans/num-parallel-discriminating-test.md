# Proposed NUM_PARALLEL discriminating test

[English index](../README.md) · [Open questions](../open-questions.md)

**Status: proposal with a partial live attempt.** With Breno's explicit approval,
the NP=2 arm ran on 2026-09-16; the NP=1 discriminator did not run because a
second 14B copy exhausted the GPU budget. The live artifact is
`RESULTADO-live-5090-2026-09-16.md` (`RESULTADO-live-5090-2026-09-16.md`, kept local: not in the public repository).
The result is inconclusive, Breno accepted that disposition, and production
remains at `NUM_PARALLEL=2`; no repeat is authorized.

## Recorded live attribution boundary — 2026-09-16

During the 03:41–03:45 observation window, PID `38344` on `:63361` was the
production NP=2 runner and a child of Ollama PID `18636`. The later 04:23 health
check recorded PID `17272` on `:59987` as the newly created production NP=2
runner. These are time-bound observations, not a permanent runner identity.
The separate NP=1 runner PID `34288` remained on `:58852`.

The runner behind the post-stop `/api/ps` residency is **unknown**. PID `34288`
may have served that reported residency, but that possibility is unverified and
must not be stated as an attribution. The `/api/ps` versus global GPU readings
cannot be attributed solely to WDDM accounting; exact per-runner VRAM
restoration remains unknown.

The planned auxiliary Ollama endpoint is `127.0.0.1:11435`. The separate
llama-server runner observed in the 2026-09-16 attempt was on `:58852`.
`NO_LISTENER port=11435` therefore does not establish cleanup of PID `34288` or
any other runner on `:58852`. This historical distinction does not authorize a
repeat or a process stop.

## 1. Can the cheaper 14B variant discriminate?

**Use the 14B as the first candidate, but increase the input from about 25,000
to about 40,000 effective tokens with `num_ctx=32768`.**

The [Ollama 0.33.3 source](https://github.com/ollama/ollama/blob/v0.33.3/llm/llama_server.go#L261-L310)
contains a relevant condition: in this completion path, an input fitting within
`num_ctx−1` is passed through intact. Only an overflowing input is shortened to
approximately half the context. Accepting 25,000 tokens at a 32,768-token
context therefore does **not** refute this mechanism.

The source computes the post-overflow limit as:

```text
limit = C - max(floor((C - K) / 2), 1)
```

For `C=98304` and effective `K=4`, this gives 49,154, matching the historical
warning. This identifies a candidate implementation with an explicit trigger;
it is not verification that the installed executable uses that exact path.

There is no demonstrated need to require the 30B model initially. The 14B must
first reproduce the truncation through the same processing path. Different
models or APIs can select different renderers and runners. Being resident also
does not guarantee reuse: changing context or parallelism can require a reload.

## 2. Is a second instance feasible?

It is plausible **if only the production 14B is resident**, but the recorded
memory budget does not support retaining the 9B as well.

| Allocation | Recorded value or conditional estimate |
|---|---:|
| Production 14B, NP=2, q8 KV | 13.93 GiB recorded |
| Second 14B, NP=1, context 32,768 | Approximately 11.27 GiB estimated |
| Both 14B copies | Approximately 25.20 GiB estimated |
| Both copies plus the 9B | Approximately 30.93 GiB estimated |
| Documented usable capacity | Approximately 30.3 GiB |

The second-copy estimate halves the recorded two-slot KV allocation while
holding other costs constant. It is **not a coexistence measurement** and
excludes any unexpected additional allocation. Sources: the
[judge report](../../../results/RESULTADO-juiz-familia-2026-09-10.md),
[Phase 1](../../../results/RESULTADO-fase1-contexto-maxloaded-2026-09-04.md),
and [production decision](../../../results/DECISAO-producao-2026-09-09.md).

A [previous two-endpoint test](../../../results/seed_ab_instancia_1788916205.json)
used production on port 11434 and an isolated 14B on 11437. Its context was
8,192, and it did not record enough residency evidence to certify that both
copies were fully on the GPU.

Sharing a model store avoids duplicate disk files; it does not remove the
second GPU allocation. Separate endpoints still compete for GPU memory and
compute. Zero restart does not imply zero impact on production latency.

Do not silently unload the 9B to make this plan fit. If it is resident and
memory is insufficient, stop and present the alternative for approval.

## 3. Final experimental design

The literal claim that the allocated context is divided between slots has
already been contradicted by the [Phase 6b log](../../../results/RESULTADO-fase6b-numparallel-contexto-longo-2026-09-12.md).
Hypothesis A below is retained only as a **law for the input limit**, not as
that disproven allocation mechanism.

Fix the same model, digest, version, runner path, API, template, payload, and
KV format in both arms. Use `num_ctx=32768`, approximately 40,000 effective
input tokens, `temperature=0`, `think=false`, `num_predict=1`, and
`num_keep=4`. Confirm the effective keep value in the log.

The offline builder emits the same API body for both arms and stores the arm's
`process_num_parallel` only in local packet metadata. It records a SHA-256 of
the canonical serialized API body, a deterministic sentinel prefix/count with
first and last markers, and explicit `null` counters for server tokenization,
delivered input, and truncation. Those nulls remain unknown until a permitted
run supplies evidence; the builder never tokenizes or sends the prompt.

| Arm | A: input limit C/N | B: post-overflow reduction |
|---|---:|---:|
| NP=2 — control | Approximately 16,384 | 16,386 if effective K=4 |
| NP=1 — discriminator | Approximately 32,768, or 32,767 with one token reserved | 16,386 if effective K=4 |

The predictions are approximately equal at NP=2, but differ by two tokens
under the stated conventions. Record that difference without treating it as
causal identification before verifying BOS, keep and reserved-token handling.
**The large changed prediction at NP=1 is the primary discriminator.** A
matching number in the control alone does not verify the mechanism.

The source inspection supports using the completion path that emits the
historical warning. The exact request route must be recorded and kept fixed;
do not silently substitute chat, raw generation, or a different rendering path
between arms. If the matching path cannot be established, stop before treating
the 14B as a reproduction of the 30B incident.

### Procedure after approval (design only; no execution or repeat is authorized)

The steps below remain a retained design for a separately authorized future
campaign. They do not override the status at the top of this document or the
owner decision: this campaign must not be repeated and production
`NUM_PARALLEL` must not be changed under the current disposition.

1. Record process IDs, executable/version and model identities, server settings,
   resident models, and free GPU memory. Confirm that the planned port 11435 is
   available, record every actual listener and owning PID separately, and do not
   treat an absent listener on 11435 as cleanup proof for another port. Confirm
   that the intended context does not silently change the production runner.
2. Preload the auxiliary runner with a short request using the intended context
   and settings. Confirm slot count, context, layers, and KV residency for both
   instances before sending a long prompt. If preloading changes production
   residency, stop and restore it. Then run the NP=2 control on production and
   the NP=1 discriminator on the temporary instance, sequentially. Do not run
   test requests concurrently.
3. Before and after each request, capture `/api/ps`, global GPU memory, and
   offload logs. Verify all expected layers and KV on the GPU for **both**
   instances. Spill, unknown residency, automatic context reduction, or request
   errors invalidate the round.
4. Save the full payload and response, prompt hash, server-side token count
   before truncation, limit, keep value, tokens delivered to the runner, and
   `prompt_eval_count`. Do not estimate tokens from characters. Do not infer
   truncation from the response counter alone or from proximity to a limit.
5. Stop only the auxiliary process tree and verify restoration of the initial
   process and residency state. Investigate any discrepancy before calling
   the experiment complete.

The two overflow arms are the minimum comparison. A 25,000-token control is
optional if the overflow trigger itself remains uncertain; it must be labeled
as a separate check, not substituted for the overflow discriminator.

`tools/context_packet.py` marks every generated packet `can_execute=false` and
contains no HTTP client, process control, or GPU operation. Its tests verify the
wire-body hash, fixed options, sentinels, counters, predictions, and the fact
that NP=1 and NP=2 differ only in local arm metadata.

### What changes on the machine

The preferred variant adds one temporary Ollama process listening on
`127.0.0.1:11435`, with process-scoped NP=1, the same model store and KV format,
separate logs, and a temporary GPU allocation. It does not alter machine-level
environment variables or the production scheduled task.

The planned endpoint and an observed runner port are separate facts. In the
2026-09-16 attempt, the surviving separate NP=1 llama-server was PID `34288` on
`:58852`; the `:11435` negative check did not cover it. Keep that historical
distinction when describing cleanup, attribution, or restoration.

Do not use [ollama-restart.ps1](../../../ollama-restart.ps1) to manage the
parallel instance. It changes multiple machine-level variables, clears values
for omitted arguments, and kills Ollama/llama-server processes by name across
the machine. Auxiliary startup and cleanup must instead target its own process tree.

### Interpretation

- If NP=2 reproduces the cut and NP=1 still cuts to approximately half, the
  result favors the conditional B mechanism in this tested configuration.
- If NP=2 reproduces the cut, all validity checks pass, and NP=1 admits
  approximately the full context, the result favors A as an input-limit law.
  It does not restore the disproven claim about dividing slot allocation.
- If the control does not reproduce the phenomenon, the runner changes, the
  effective settings are wrong, or residency is not verified, report the test
  as inconclusive. Do not automatically escalate to loading the 30B.

## 4. Cost and restart alternative

**Auxiliary instance:** zero planned production downtime, but load and prefill
may increase production latency. Processing 40,000 fresh input tokens has not
been timed here. Phase 6's short reported prefill times may include prefix cache
and cannot supply that estimate.

**If memory does not fit (design only):** a future campaign would stop and
obtain explicit approval for the restart alternative. Preserve all settings,
temporarily change only NP from 2 to 1, run the test, then restore NP=2 and the
original residents. This is not authorization to repeat the current campaign.

If a future campaign is authorized, reserve a **five-minute operational
window** for that alternative. This is a
planning allowance, not a measured duration or guaranteed upper bound. The
pause covers draining traffic, two restarts, reloads, and the experiment. The
[migration runbook](../../../MIGRACAO-windows-nativo-2026-09-04.md) records one
historical downtime of 7.1 seconds; it does not establish the cost of this procedure.

The NP=2 arm was executed under explicit approval on 2026-09-16; its counter is
retained as an observation, but the round is invalid for causal interpretation
because layer/KV/runner residency evidence was unavailable. The NP=1 arm remains
unexecuted. The measured Phase 6 benefit remains valid for its workload, and
production NP=2 remains the adopted configuration.
