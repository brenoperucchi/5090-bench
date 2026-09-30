# T87 P1 — harness v5 hardening and rerun authorization

- status: **accepted**
- owner: **Breno**
- accepted_at: **2026-09-18T20:18:10Z**
- harness_version: `t87-p1-harness-v5`
- supersedes execution scope only: the failed v4 attempt consumed 35 generations and contributes no score
- new_generation_budget: **330** (`5 × (13 + 27 + 26)`)
- total_day_accounting: **365** (35 lost + 330 newly authorized)

## Authorized hardening

The following measurement-neutral changes are authorized before the new
campaign:

- append-only, fsync-backed checkpoint after each POST;
- immediate persistence of request, response and generation counter;
- capture of SSH/bwrap wrapper diagnostics, exit code, signal, stdout and stderr when the marker is not observed;
- SSH keepalive and connection diagnostics;
- unchanged prompts, seeds, turn caps, model, runtime, route, server flags, sandbox binds, permissions and `--die-with-parent`.

Automatic command retry, task resumption, sandbox permission/bind changes,
removal of `--die-with-parent`, protocol changes and extra generations are not
authorized.

## New campaign boundary

- model: `qwen3.6-35b-a3b`
- runtime: `thecodacus/llama.cpp`, fork commit `27c54b4bbcefadedcec6397477cc2e866c1db716`
- route: `id=lan`, `http://192.168.0.125:18087/v1/chat/completions`
- benchmark commit: `776e799c7e0a24271e021aca2ea4b1c1b1f10017`
- GGUF SHA-256: `d372de8e934898a59e6ccfabc3368474711384d8f1fd4d22d87a3f0a45400cdc`
- binary SHA-256: `37acf8e80c85f91794d9fa0268d34b40dbfa2f4286527a92bdd13dfefdab689b`
- seeds: `1000, 1017, 1034, 1051, 1068`
- harness series key includes `harness_version=t87-p1-harness-v5`
- prior v4 partial run is preserved as diagnostic evidence and excluded from the five-run statistic

The campaign must be re-attested with the preparation and instrument hashes
before any POST. If a later sandbox failure occurs, report its captured cause
before spending more budget; no automatic retry or resume is allowed.
