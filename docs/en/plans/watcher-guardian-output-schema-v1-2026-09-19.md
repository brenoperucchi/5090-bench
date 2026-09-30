# Watcher guardian output contract v1

This schema is frozen for review before T2 execution. It is a model-output
contract, not an action contract: the model has no tools, callbacks, write
access, or interruption authority. `escalation_requested` is only a
structured suggestion consumed by an external deterministic rule.

Required fields:

- `agent_session`: the observed pane/session identifier supplied in the input
  packet;
- `suggested_state`: `normal`, `correction-in-progress`, `stalled`,
  `out-of-scope`, or `unknown`;
- `abstain`: explicit boolean;
- `evidence`: zero or more relative file references with line bounds and the
  literal quote; the harness checks path existence, line bounds, and exact
  substring equality;
- `confidence.score`: numeric 0–1;
- `confidence.band`: operational band: `low` for score `<0.7`, `review` for
  `0.7 <= score < 0.9`, and `high` for score `>=0.9`;
- `confidence.tier`: fixed to `heuristic` for this version;
- `escalation_requested`: boolean suggestion only.

The deterministic consumer uses the confidence band as follows: `low` is not
actionable; `review` may be placed in a review queue but cannot notify or
interrupt; `high` is only eligible for the external deterministic rule to
consider an owner notification when the state/evidence gates also pass. The
model never calls that rule and never performs the notification itself.

The schema uses `additionalProperties: false` and rejects absolute paths,
parent traversal, invalid states, confidence outside 0–1, and unknown fields.
The schema file is
`watcher-guardian-output-schema-v1-2026-09-19.json`.

T2 must run twice on the same frozen input packet: unconstrained JSON mode and
the equivalent GBNF grammar. The comparison records schema-valid responses and
does not infer semantic correctness from validity alone.
