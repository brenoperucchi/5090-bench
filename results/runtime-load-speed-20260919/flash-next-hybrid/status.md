# Flash-Next hybrid load probe — 2026-09-19

Status: `interrupted_by_control_channel`; no generation was issued and no
successful `/health=200` state was observed.

## Configuration

- artifact: `Qwen3.8-Flash-Next-UD-IQ3_XXS`, 3 GGUF shards
- runtime: `thecodacus/llama.cpp`, existing Codacus binary
- route: LAN `192.168.0.125:18087`
- context: `32768`
- GPU placement: `--gpu-layers auto`
- fit: `--fit on --fit-target 1024`
- flash attention: `on`
- parallel: `1`
- model server PID observed after launch: `54330`
- command: [command.txt](command.txt)

## Observed progression

The preflight had approximately `31,348 MiB` free VRAM and no llama-server
resident. The process started with `--gpu-layers auto --fit on` and remained
alive. `/health` returned `503 Loading model` during every reachable check.

The process RSS grew during loading from approximately 16 GiB to 33 GiB.
VRAM rose from approximately 1.3 GiB to 28.9 GiB used, showing that automatic
placement began using both host memory and CUDA. The last reachable log line
was:

```text
tensor overrides to CPU are used with mmap enabled - consider using --load-mode none for better performance
```

No CUDA OOM or model-load error was observed before control was lost.

After approximately five minutes, the host still answered ICMP ping but both
SSH (`:22`) and the model endpoint (`:18087`) stopped accepting connections.
The final process state, final `/health`, final VRAM/RAM residency, and safe
cleanup state are therefore `unknown`. No runtime was killed after the loss of
control.

This run demonstrates that the hybrid path starts and allocates host/CUDA
memory, but it does not establish that the model loaded successfully or that it
can generate on this configuration.

## Recheck at 2026-09-19T14:24:39Z

- LAN ping to `192.168.0.125`: successful, 0% loss.
- SSH `192.168.0.125:22`: unreachable/timeout.
- llama-server `192.168.0.125:18087`: unreachable.
- Ollama `192.168.0.125:11434`: HTTP 200, version `0.34.2`, `/api/ps` reports
  `{"models":[]}`.
- Remote PID, final GPU state, and cleanup state: still `unknown`.

## Recovery check at 2026-09-19T14:29:29Z

SSH access returned. PID `54330` no longer exists, `:18087` is closed, and
`/health` cannot connect. VRAM is back to approximately `823 MiB` used, with
the host RAM back to approximately `45 GiB` available. The remote log remains
at the CPU-override warning and contains no terminal load error. Read-only
`dmesg` and `journalctl -k` searches exposed no OOM or kill record, so the
termination cause remains `unknown`.
