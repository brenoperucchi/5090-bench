# Strata on the RTX 5090

Dedicated track for [Strata](https://github.com/Niko1221/Strata), the purpose-built engine that runs
**Qwen3.8-Flash-Next** (and its Swift 1.5 fine-tune) split across VRAM, RAM and SSD. It started on 2026-09-30,
when Strata replaced the WSL llama.cpp server as the local production backend.

## Current state (2026-09-30)

- **Production (provisional):** Swift 1.5 IQ2_XS on Strata v0.1.30, Windows 11 native, `127.0.0.1:18199`,
  32K context, 1 slot, calibrated (`--pcie-frac 0.55 --spec-min-p 0.70`), `STRATA_IQ_MT_MIN=1`.
- **Installed side by side:** Flash-Next IQ2_XS, Flash-Next IQ3_XXS, Swift 1.5 IQ3_XXS.
- **Hardware:** RTX 5090 32 GB, Ryzen 9 5950X (AVX2, DDR4), 64 GB RAM, NVMe.

## Headline numbers

| | Generation | Source |
|---|---|---|
| Flash-Next on llama.cpp (Codacus fork, UD-IQ3_XXS, experts on CPU), 2026-09-19 | 16–27 tok/s hot | `docs/en/findings/flash-next-context-probe-2026-09-19.md` |
| Flash-Next IQ2_XS on Strata v0.1.30, calibrated | 155–172 tok/s | `results/strata-20260930/` |
| Swift 1.5 IQ2_XS on Strata, Guardian synthesis (long answers) | 219 tok/s median | same |

Desk-test indicator (A2 = unverified items stated as fact, mean over 12 answers, lower is better; indicator only,
ρ ≈ 0.7 with human raters): Swift IQ2_XS 4.00 · Swift IQ3_XXS 4.58 · Flash-Next IQ3_XXS 4.92 ·
qwen3-coder-30b 5.64 · Flash-Next IQ2_XS 9.75. The first three are equivalent within noise.

## Where things are

- **Full record (pt-BR), day log with every version, calibration and model:**
  [`results/strata-20260930/README.md`](../../results/strata-20260930/README.md)
- **Report "software × hardware" (pt-BR, 5 parts), written for the weekly LLM-vs-GPU discussion:**
  [`results/strata-20260930/relatorio/`](../../results/strata-20260930/relatorio/00-LEIA-PRIMEIRO.md)
- **Raw speed measurements** (server timings, `tools/os_runtime_ab.py`): `results/strata-20260930/*.json`
- **Calibration log:** `results/strata-20260930/calibrate-v0.1.30.log`
- **Desk test per model:** `tools/desk_test_by_model.py`

Guardian answers, chronology snapshots and rating forms stay on the lab machine (git-ignored), as in the rest of
the repository; scenarios are labelled S1–S4 in public files.

## Open items

1. Human blind evaluation (or a larger sample) to separate Swift IQ2_XS, Swift IQ3_XXS and Flash-Next IQ3_XXS.
2. Read the Swift Open License 1.0 before using Swift beyond internal tests.
3. Non-determinism at temperature 0 (output length varies between repeats even with `STRATA_IQ_MT_MIN=1`).
4. Gateway ↔ Strata connection (owned by llm-gateway) and Guardian ↔ gateway (owned by claude-bridge).
5. Per-model calibration (the IQ3_XXS and Swift configs inherited the IQ2_XS calibration).
