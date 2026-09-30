# Coding evaluation and sandbox contract

I5.1 cannot run in the current environment: no product-owned coding workload,
independent labels, or approved isolated executor is available. This page
prepares the offline contract without executing model-produced code or patches.

## Task packet

`tools/coding_eval_contract.py` validates `coding-task-v1` definitions. Each
task has a stable ID, a task family, a language, a prompt, an expected outcome
mode/value, and an explicit sandbox budget. The initial families are:

- `functional`: execute a generated function or program against fixed inputs;
- `api_hallucination`: exercise a documented API and detect invented imports or
  attributes;
- `instruction_adherence`: inspect a constrained patch or file result; and
- `tool_flow`: validate a prescribed tool name, argument, and order trace.

These are task-family labels, not quality claims. The expected value remains
independent reference data and must be frozen before model outputs are seen.

The packet builder emits `coding-eval-packet-v1` with `can_execute: false`. A
future runner may consume the packet only after a separate approval and after
it supplies an isolated executor. The builder contains no command, code
execution, model call, or filesystem operation.

## Required sandbox proof

Every future result must include `coding-result-v1` evidence and a candidate
hash. Its `sandbox_proof` must explicitly prove:

- network access was blocked;
- the filesystem was ephemeral and discarded after the task;
- a timeout was enforced; and
- a memory limit was enforced.

`classify_coding_result()` refuses to treat missing or false proof as usable.
Network or filesystem failure is `sandbox_failed`; missing timeout or memory
proof is `sandbox_unproven`; runner errors and unsupported observations remain
`inconclusive`. A `pass` status without complete proof never becomes an accepted
coding result.

The eventual executor must use a disposable workspace, deny network by
default, enforce CPU/time/memory limits, cap output, and clean up even when a
candidate hangs or exits abnormally. Applying a model-generated patch to the
repository is outside this contract and requires a separate reviewable step.

## What remains blocked

Before I5.1 can become a runnable evaluation, Breno/application owners must
provide a target workload, task-family labels, independent expected outcomes,
acceptable error severity and a reviewed sandbox implementation. The current
artifact and its synthetic tests only prove schema and fail-closed behavior;
they do not execute code, compare models, or establish a promotion threshold.
