# T87 P1 — labuser harness v7 rerun authorization

- status: **accepted**
- owner: **Breno**
- accepted_at: **2026-09-19T03:20:20Z**
- harness_version: `t87-p1-harness-v7`
- new generation budget: **330** (`5 × (13 + 27 + 26)`)
- prior generations excluded: **362**

## Frozen campaign conditions

- model: `qwen3.6-35b-a3b`
- runtime: `thecodacus/llama.cpp`
- route: LAN `192.168.0.125:18087`
- seeds: `1000, 1017, 1034, 1051, 1068`
- no synthetic warm-up;
- execution user: `labuser`;
- task root: `/home/labuser/lab`;
- virtual environment: `/home/labuser/venv`;
- reset before every run with `LLAMA_SERVER=http://192.168.0.125:18087`;
- GPU free-memory gate remains `8000 MiB`.

The series key must include the execution user, Python version, venv path,
requirements-lock fingerprint, installed-dependency fingerprint, setup hash,
and reset-script hash. No v4, v5, v6 or other prior campaign is comparable.

The harness uses the dedicated `.secrets/labuser_key` for runtime/sandbox SSH
and keeps the control/grader channel separate so `labuser` never receives the
hidden grader, solutions, or answer key.

No automatic retry, partial resume, extra generation, cleanup outside the
authorized lab reset, model/runtime/profile change, commit or push is allowed.
