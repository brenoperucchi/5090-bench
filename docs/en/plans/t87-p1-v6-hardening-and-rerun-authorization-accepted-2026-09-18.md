# T87 P1 — harness v6 hardening and rerun authorization

- status: **accepted**
- owner: **Breno**
- accepted_at: **unknown** (the current owner direction did not provide a timestamp)
- harness_version: `t87-p1-harness-v6`
- prior generations excluded from the statistic: **55** (v4/v5 partial runs)
- new generation budget: **330** (`5 × (13 + 27 + 26)`)
- day accounting after this campaign: **385** (`55` prior loss + `330` new)

## Authorized measurement-neutral hardening

- each campaign run uses a fresh, collision-checked remote directory;
- the persistent sandbox evaluates the model command as one quoted command,
  so a non-zero or shell-syntax failure is returned as a tool result with
  stderr and does not terminate the persistent session;
- append-only, fsync-backed checkpoints remain in place;
- request/response and generation counters remain persisted immediately;
- SSH/bwrap diagnostics retain exit code, signal, stdout and stderr on EOF;
- SSH keepalive and connection diagnostics remain enabled;
- every turn records GPU memory and compute-process state before and after the
  model/tool turn;
- a free-memory gate of `8000 MiB` is fail-closed: below threshold marks the
  run `contaminated_gpu` and stops it; an unobservable reading stops it as
  `failed_gpu_gate`.

## Frozen measurement inputs

Prompts, seeds, turn caps, model, runtime, route, server flags, sandbox binds,
permissions, `--die-with-parent`, sampling and protocol remain unchanged from
v5. The v6 `series_key` is distinct from v4 and v5 and includes the harness
version and GPU gate threshold; no prior partial run is included in the
five-run statistic.

No automatic retry, task resumption, extra generation, cleanup/reset, gateway
or profile change, or commit/push is authorized by this record.
