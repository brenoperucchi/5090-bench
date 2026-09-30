# T18 execution record — 2026-09-18

Status: **offline evidence refreshed; owner gate remains pending**

This record executes the technical/documentary portion of T18 without treating
gateway reachability as product acceptance. It preserves the parent T18 and
children T18a/T18b/T18c as open until the application/product owner supplies
and accepts the required decisions.

## Identity and scope

- Executor: `llm-bench-exec`, attested through `HERDR_ENV=1 herdr agent get`.
- Gateway coordinator: `llm-exec`, attested in `/home/brenoperucchi/Devs/llm-gateway`.
- Scope: read-only inspection of the T18 packet plus the gateway's recorded
  internal-network change.
- No benchmark, generation call, cleanup, PID stop, Ollama/GPU action, commit,
  or push was performed by this record.

## Technical evidence observed

Source artifact: `/home/brenoperucchi/Devs/llm-gateway/docs/RESULTADO-rede-interna-ollama-2026-09-18.md`

Source SHA-256:

`3cc83c9c1665ca55e58b66b8c128b855587d879e8c349d3bc015e771eddc80dc`

The gateway record reports:

- effective Ollama endpoint changed from `http://100.88.95.78:11434` to
  `http://192.168.0.125:11434`;
- no fallback to Tailnet or loopback;
- gateway bind remains `127.0.0.1:8080`;
- `/health` and `/v1/models` returned HTTP 200 after the service restart;
- Ollama `/api/version` returned `0.34.2` over the LAN endpoint;
- provider/config tests passed: `14 passed`, with the documented warning;
- no generation or benchmark was executed for this configuration change.

This proves a current technical route and connectivity observation only. It
does **not** prove that any application consumer is covered, that the route is
required by a product, or that a product owner accepted a promotion policy.

## T18 gate audit

| Gate | Current evidence | Decision |
|---|---|---|
| T18a / I1.3 consumer inventory | Offline inventory exists in `gateway-consumer-coverage-and-product-acceptance.md`; direct and gateway paths are separated, but consumer owners and classifications remain `unknown` | **Blocked — owner input required** |
| T18b / I1.4 + I1.5 product criteria | Repository-derived criteria are documented, but no owner-selected scope, labels, holdout, thresholds, or tolerances are accepted | **Blocked — product-owner input required** |
| T18c / I3.3 enforcement | Gateway route exists and is technically reachable, but the actual consumer-side enforcement owner and code path are not accepted | **Blocked — depends on T18a** |

The technical route therefore updates evidence for the endpoint column; it does
not change any classification to `covered` and does not authorize migration or
promotion.

## Required owner completion

T18 still requires an owner-completed form at
`docs/en/plans/t18-owner-acceptance-form.md` containing:

1. owner identity, scope, decision ID/date, and acceptance decision;
2. one classification per consumer: `covered`, `explicitly excluded`, or
   `unknown`, with reason and exception/migration disposition;
3. product criteria and thresholds for escalation, false escalation, promised
   actions, language, tools, provenance, reasoning, input integrity,
   latency/resources, and fallback/cost;
4. independent label, adjudication, task-family, holdout, uncertainty, and
   regression-corpus decisions;
5. the actual consumer-side enforcement owner and code path;
6. required gateway routes, explicit exclusions, promotion decision, and next
   approved gate.

Until these fields are supplied and accepted, T18 remains an executed offline
packet with a pending owner gate, not a completed product-acceptance task.
