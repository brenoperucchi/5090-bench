# Lifecycle and spill evidence contracts

This page defines the offline contracts for the operational checks in I4.3 and
I4.4. The code only validates supplied evidence or builds a non-executable
runbook. It does not start or stop processes, call an endpoint, inspect
`/api/ps`, read GPU memory, or load a model.

## Lifecycle packet and restoration

`tools/lifecycle_contract.py:build_lifecycle_packet()` creates a
`lifecycle-packet-v1` runbook with `can_execute: false`. It names the intended
production and auxiliary endpoints, a bounded timeout, the observation and
cleanup steps, stop conditions, and restoration requirements. It intentionally
contains no shell command, process name wildcard, signal, or default endpoint.

The six steps are:

1. Capture the initial process identities, endpoint health, and residency.
2. Start the auxiliary process only after a separately approved packet.
3. Check the exact endpoint and process identity.
4. Run one bounded request, retaining invalid evidence.
5. Stop only the owned auxiliary process tree.
6. Verify the original identities, endpoint health, residency, and absence of
   auxiliary processes.

`validate_lifecycle_evidence()` accepts captured `initial`, `auxiliary`, and
`final` phases. Each process identity requires a positive PID, non-empty start
time and executable, and a SHA-256 executable hash. `detect_orphans()` compares
identity sets without touching the PIDs. `evaluate_restoration()` returns:

| Status | Meaning |
| --- | --- |
| `restored` | Initial and final identities match, the endpoint is healthy, no auxiliary PID remains, and residency is known healthy. |
| `failed` | An orphan, identity mismatch, unhealthy endpoint, or unhealthy final residency is observed. |
| `unknown` | Required residency evidence is missing or unknown. |
| `invalid` | The evidence itself violates the JSON or lifecycle contract. |

An `unknown` or `invalid` result cannot be treated as restoration. A live
packet must still identify the actual executable, process tree, ports, owners,
and rollback commands before Breno can approve execution.

## Spill and residency evidence

`tools/spill_evidence.py` defines `spill-evidence-v1`. A role is represented by
`roles.target` and, when applicable, `roles.draft` with:

- model identity;
- expected and observed GPU layer counts;
- KV location (`gpu`, `cpu`, `mixed`, or `unknown`);
- attributed memory bytes (or `null` when unavailable); and
- named evidence sources such as `startup_log`, `runner_log`, `api_ps`, or
  `gpu_sample`.

`classify_spill_evidence()` returns `verified_no_spill` only when every required
role has all expected layers on GPU, KV on GPU, non-null attributed memory,
and at least one startup or runner source. Global memory or `/api/ps` alone is
not enough. It returns `spill_detected` for an offloaded layer or CPU/mixed KV,
`residency_unknown` for missing attribution, unknown KV, or weak sources, and
`invalid` for malformed evidence. Pass `required_roles=("target", "draft")`
when a draft model is expected; the default only requires the target and never
infers a draft.

This closes the offline classification boundary. It does not prove that an
installed runner emits the fields, that `/api/ps` attributes memory correctly,
or that a model is resident on the GPU. Those require an approved live capture
with before/during/after observations and restoration proof.

## Acceptance and blocked work

The synthetic tests cover a non-executable packet, missing phases, identity
validation, orphan detection, successful and failed restoration, unknown
residency, complete target/draft proof, layer and KV spill, missing attribution,
global-memory false confidence, and malformed role data. They do not call a
server, process, model, network, or GPU.

I4.3 and I4.4 are therefore **implemented offline**. I4.1/I4.2 remain live
capacity and cache experiments requiring GPU/server approval. The live packet
and negative lab validation remain pending; this document does not authorize
either action.
