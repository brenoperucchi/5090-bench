# T87 P1 — protected-suite harness v8 authorization

- status: **accepted**
- owner: **Breno**
- accepted_at: **2026-09-19T04:30:01Z**
- harness_version: `t87-p1-harness-v8`
- new generation budget: **330** (`5 × (13 + 27 + 26)`)
- prior generations excluded: **all v7 and earlier generations**

## Frozen campaign conditions

- model: `qwen3.6-35b-a3b`
- runtime: `thecodacus/llama.cpp`
- route: LAN `192.168.0.125:18087`
- seeds: `1000, 1017, 1034, 1051, 1068`
- no synthetic warm-up;
- execution user: `labuser`;
- task root: `/home/labuser/lab`;
- virtual environment: `/home/labuser/venv`;
- protected suite: `/opt/spec-wins`, mode `0700`, owner `root:root`;
- reset before every run: `LLAMA_SERVER=http://192.168.0.125:18087 sudo -n /opt/spec-wins/scripts/reset-lab.sh`;
- grading after every task: `sudo -n /opt/spec-wins/scripts/verify-lab.sh <task>`;
- GPU free-memory gate remains `8000 MiB`.

The control channel runs only the two allowlisted root wrappers. The model
continues to receive only the writable task copy under `/home/labuser/lab` and
cannot read `/opt/spec-wins`, `hidden/`, `solutions/`, or
`docs/answer-key.md`. The reset-script hash is recorded as `unknown` because
the protected script is intentionally not readable through the allowlist.

The series key includes the execution user, Python version, venv path,
requirements-lock fingerprint, installed-dependency fingerprint, setup hash,
protected-suite identity, privileged reset/grader commands, and harness
version. No v4, v5, v6, v7, or other prior campaign is comparable.

No automatic retry, partial resume, extra generation, cleanup outside the
authorized lab reset, model/runtime/profile change, commit, or push is allowed.
