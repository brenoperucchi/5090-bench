# Strata on the RTX 5090

Dedicated track for [Strata](https://github.com/Niko1221/Strata), the purpose-built engine that runs
**Qwen3.8-Flash-Next** (and its Swift 1.5 fine-tune) split across VRAM, RAM and SSD. It started on 2026-09-30,
when Strata replaced the WSL llama.cpp server as the local production backend.

## Current state (2026-10-02)

- **Production:** Swift 1.5 IQ3_XXS on Strata v0.1.31, Windows 11 native, `127.0.0.1:18199`, 32K context, 1 slot,
  recalibrated for this model (`--pcie-frac 0.20 --spec-min-p 0.70`), `STRATA_IQ_MT_MIN=1`.
- **Also installed:** Flash-Next IQ2_XS / IQ3_XXS / IQ3_S, Swift 1.5 IQ2_XS, Coder IQ1_M, Unsloth UD-Q4_K_XL;
  Strata 0.1.32, 0.1.33 and 0.1.34 in separate folders for side-by-side tests.
- **Hardware:** RTX 5090 32 GB, Ryzen 9 5950X (AVX2), **96 GB DDR4-3200** since 2026-10-01 (was 64 GB @2400), NVMe.

## Headline numbers

| | Generation | Source |
|---|---|---|
| Flash-Next on llama.cpp (Codacus fork, UD-IQ3_XXS, experts on CPU), 2026-09-19 | 16–27 tok/s hot | `docs/en/findings/flash-next-context-probe-2026-09-19.md` |
| Flash-Next IQ2_XS on Strata v0.1.30, calibrated | 155–172 tok/s | `results/strata-20260930/` |
| Swift 1.5 IQ3_XXS on Strata v0.1.31 (production) | 157–163 tok/s, prompt read ~4,150 tok/s | same |
| Unsloth UD-Q4_K_XL on Strata v0.1.31, 96 GB (everything in VRAM+RAM) | 58–67 tok/s | same |

### Strata versions, same model (Swift 1.5 IQ3_XXS, same config, 96 GB)

Server timings, median of 5 runs, 256 output tokens; prompts of 2,671 (medium) and 5,952 (long) tokens.

| Engine | Generation medium / long | Prompt read, long | Desk-test A2 (12 answers) |
|---|---|---|---|
| 0.1.31 | 163 / 157 | 4,175 | 6.67 |
| 0.1.32 | 166 / 161 | 4,123 | 5.50 |
| 0.1.33 | 165 / 160 | 4,144 | 5.50 |
| 0.1.33 + old stager (`STRATA_STAGER_THREADS=4 STRATA_STAGER_RING=16`) | 170 / 164 | 4,126 | 5.08 |
| 0.1.34 | 167 / 161 | 4,147 | 7.33 |
| 0.1.34 + `--prefill auto:32768` | 166 / 160 | 4,147 | 5.58 |

The four versions tie: speed within 2–4%, A2 within its noise (the same 0.1.31 setup scored 4.58 and 6.67 on two
days). A private comprehension benchmark from a consumer project (not published) also showed no change between
versions; on that benchmark, enabling the model's reasoning mattered far more than any engine version.

### Long prompts: `--prefill auto:32768` (0.1.34, PR #440 upstream)

Swift IQ3_XXS, public prompts from the Strata community benchmark, median of 3 runs:

| | Prompt read 14.7K | Prompt read 28.9K | Min. free VRAM |
|---|---|---|---|
| 0.1.34 default | 4,704 | 4,790 | 779 MiB |
| 0.1.34 + `auto:32768` | 5,525 (+17%) | 6,226 (+30%) | 771 MiB |

No gain below ~15K tokens, generation unchanged. Production traffic (gateway log, 8,918 requests) has a median prompt of
433 tokens and a maximum of 10,129, so production stays on 0.1.31 until long prompts or a larger context are needed.

Desk-test indicator across models (A2 = unverified items stated as fact, mean over 12 answers, lower is better;
indicator only, ρ ≈ 0.7 with human raters): Swift IQ2_XS 4.00 · Swift IQ3_XXS 4.58 · Flash-Next IQ3_XXS 4.92 ·
qwen3-coder-30b 5.64 · Flash-Next IQ3_S 6.08 · Flash-Next IQ2_XS 9.75. Only the last one is clearly worse.

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

1. Human blind evaluation (or a larger sample) to rank the IQ3-class models; A2 only separates the clearly bad.
2. Read the Swift Open License 1.0 before using Swift beyond internal tests.
3. Determinism: fixed upstream in 0.1.34 (#410) with `--prompt-cache 0 --adapt-swaps 0 --pcie-frac 0` and
   `STRATA_IQ_MT_MIN=1`; use it for byte-identical A/B, not for speed or production.
4. Long context: the model handled 262K on a 5090 upstream (PR #440); not measured on this machine yet.
